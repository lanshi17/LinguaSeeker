"""Analyze backend logs with drain3 template clustering.

Clusters structurally-identical log lines (masking variable tokens like
timestamps, UUIDs, request IDs, numbers) into templates, then reports the
dominant WARNING/ERROR patterns, their source code locations, and an optional
root-cause bucket grouping.  Output goes to stdout (text table) and/or a JSON
report for later diffing.

The loguru line format is::

    YYYY-MM-DD HH:MM:SS.mmm | LEVEL     | module:func:line | message [rid=...]

Only the LEVEL and message are fed to drain3; the ``module:func:line`` part is
kept separately for per-location hotspot aggregation.

Usage (run from project root, backend env provides drain3)::

    cd backend
    uv run python ../scripts/data/analyze_logs.py
    uv run python ../scripts/data/analyze_logs.py --logs ../logs --levels WARNING ERROR --top 40
    uv run python ../scripts/data/analyze_logs.py --json reports/log-analysis-20260623.json
    uv run python ../scripts/data/analyze_logs.py --since 2026-06-23

The script is read-only and works against ``logs/*.log`` and ``logs/*.log.gz``.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

# scripts/data/analyze/analyze_logs.py → repo root is 4 levels up.
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LOG_DIR = REPO_ROOT / "logs"

# Loguru format: 'YYYY-MM-DD HH:MM:SS.mmm | LEVEL | module:func:line | message'
_LOGURU_RE = re.compile(
    r"^(?P<ts>\S+\s\S+)\s\|\s(?P<level>\w+)\s+\|\s(?P<loc>[^|]+)\|(?P<msg>.*)$"
)

# Default root-cause buckets.  A template is assigned to the first bucket whose
# any keyword (lowercased) appears in the mined template string.  Templates that
# match no bucket fall into "其他".
ROOT_CAUSE_BUCKETS: list[tuple[str, list[str]]] = [
    ("trace pairing 轨迹配对跳过", ["non-standard track", "no original/translated track"]),
    ("Snippet 定位失败 SOURCE_INVALID", ["not found in document", "source_invalid"]),
    ("LLM API 余额不足/鉴权 (403/401)", ["balance is insufficient", "auth error", "401 unauthorized"]),
    ("special_evidence 结构化输出失败", ["special_evidence chunk", "failed structured output"]),
    ("JSON-mode 429 (response_format 不兼容)", ["429", "response_format", "must contain the word 'json'"]),
    ("Phase3 语义匹配连接失败 (inference service)", ["all connection attempts failed", "semantic matching service error"]),
    ("LLM 超时", ["timed out", "request timed out", "timeout"]),
    ("inference service 401 未授权", ["client error '401 unauthorized'"]),
    ("LLM 格式化长度不匹配", ["length mismatch"]),
    ("Pipeline 阶段失败/取消", ["phase ", "failed, stopping pipeline", "cancelled"]),
    ("心跳失败", ["heartbeat failed"]),
    ("API 限流", ["ratelimit"]),
    ("JSON 解析/校验错误", ["invalid control character", "validation"]),
]


@dataclass
class TemplateStat:
    """Frequency stat for one drain3 cluster."""

    cluster_id: int
    count: int
    level: str
    template: str
    samples: list[str] = field(default_factory=list)
    top_locations: list[tuple[str, int]] = field(default_factory=list)
    bucket: str = "其他"


def _open_log(path: Path) -> Iterator[str]:
    """Yield lines from a .log or .log.gz file, tolerant of decode errors."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            yield line


def iter_log_files(log_dir: Path) -> list[Path]:
    """Return sorted .log and .log.gz files under ``log_dir``."""
    files = sorted(log_dir.glob("*.log")) + sorted(log_dir.glob("*.log.gz"))
    return files


def _file_date(path: Path) -> date | None:
    """Extract the date from a log filename like '2026-06-23_195603.log'."""
    stem = path.name.split("_", 1)[0]
    try:
        return datetime.strptime(stem, "%Y-%m-%d").date()
    except ValueError:
        return None


def _classify_bucket(template: str) -> str:
    lower = template.lower()
    for label, keywords in ROOT_CAUSE_BUCKETS:
        if any(kw in lower for kw in keywords):
            return label
    return "其他"


def parse_log_line(line: str) -> tuple[str, str, str] | None:
    """Split a loguru line into ``(level, location, message)``.

    Returns ``None`` for lines that do not match the structured format.
    """
    m = _LOGURU_RE.match(line.rstrip("\n"))
    if not m:
        return None
    return m.group("level").strip(), m.group("loc").strip(), m.group("msg").strip()


def analyze(
    log_dir: Path,
    levels: set[str],
    *,
    top: int = 30,
    since: date | None = None,
    sim_th: float = 0.5,
    depth: int = 5,
    max_children: int = 100,
    max_samples: int = 3,
) -> tuple[list[TemplateStat], dict[str, int], Counter, Counter, dict[str, int]]:
    """Cluster WARNING/ERROR log lines with drain3.

    Args:
        log_dir: Directory containing ``*.log`` / ``*.log.gz``.
        levels: Log levels to include (e.g. ``{"WARNING", "ERROR"}``).
        top: Number of top templates to keep fully populated.
        since: Optional earliest date (filename-based) to include.
        sim_th: drain3 similarity threshold (lower => more aggressive merge).
        depth: drain3 tree depth.
        max_children: drain3 max children per node.
        max_samples: Max raw sample messages per template.

    Returns:
        ``(stats, level_counts, bucket_counts, location_counts, total_lines)``
    """
    # Import lazily so the script's --help works without drain3 installed.
    from drain3 import TemplateMiner
    from drain3.template_miner_config import TemplateMinerConfig

    config = TemplateMinerConfig()
    config.drain_sim_th = sim_th
    config.drain_depth = depth
    config.drain_max_children = max_children
    config.drain_extra_delimiters = ["|"]
    # Mask standalone numeric/hex tokens (IDs, line numbers, counts) so that
    # structurally-identical lines cluster together regardless of their values.
    config.parametrize_numeric_tokens = True
    miner = TemplateMiner(config=config)

    stat: dict[int, TemplateStat] = {}
    loc_counter: dict[int, Counter] = defaultdict(Counter)
    level_counts: dict[str, int] = defaultdict(int)
    total_lines = 0

    for path in iter_log_files(log_dir):
        if since is not None:
            fdate = _file_date(path)
            if fdate is None or fdate < since:
                continue
        for line in _open_log(path):
            total_lines += 1
            parsed = parse_log_line(line)
            if parsed is None:
                continue
            level, loc, msg = parsed
            if level not in levels:
                continue
            level_counts[level] += 1
            if not msg:
                continue
            result = miner.add_log_message(msg)
            cid = result["cluster_id"]
            if cid not in stat:
                cluster = next(c for c in miner.drain.clusters if c.cluster_id == cid)
                template = " ".join(cluster.log_template_tokens)
                stat[cid] = TemplateStat(
                    cluster_id=cid,
                    count=0,
                    level=level,
                    template=template,
                    bucket=_classify_bucket(template),
                )
            entry = stat[cid]
            entry.count += 1
            # Keep the dominant level if a template spans both.
            if level == "ERROR" and entry.level != "ERROR":
                entry.level = level
            if len(entry.samples) < max_samples:
                entry.samples.append(msg)
            loc_counter[cid][loc] += 1

    for cid, entry in stat.items():
        entry.top_locations = loc_counter[cid].most_common(3)

    ranked = sorted(stat.values(), key=lambda e: (-e.count, e.level))
    bucket_counts = Counter(e.bucket for e in ranked)
    location_counts: Counter = Counter()
    for entry in ranked:
        for loc, cnt in entry.top_locations:
            location_counts[loc] += cnt

    return ranked, dict(level_counts), bucket_counts, location_counts, {"total_lines": total_lines}


def _fmt_row(count: int, level: str, text: str, width: int) -> str:
    text = " ".join(text.split())
    return f"{count:>6}  {level:<7}  {text[:width]}"


def render_text(
    stats: list[TemplateStat],
    level_counts: dict[str, int],
    bucket_counts: Counter,
    location_counts: Counter,
    meta: dict[str, int],
    *,
    top: int,
) -> str:
    """Render a human-readable text report."""
    lines: list[str] = []
    lines.append(f"总扫描行数: {meta['total_lines']}")
    lines.append("级别分布 (筛选范围内): " + ", ".join(
        f"{lvl}={cnt}" for lvl, cnt in sorted(level_counts.items(), key=lambda x: -x[1])
    ))
    lines.append("")

    lines.append("=== 根因分类 (合并子簇后) ===")
    lines.append(f"{'条数':>6}  根因")
    lines.append("-" * 80)
    for bucket, cnt in bucket_counts.most_common():
        lines.append(f"{cnt:>6}  {bucket}")
    lines.append("")

    lines.append(f"=== Top {min(top, len(stats))} 模板 ===")
    lines.append(f"{'条数':>6}  {'级别':<7}  模板 (<*> = 被屏蔽的变量 token)")
    lines.append("-" * 110)
    for entry in stats[:top]:
        lines.append(_fmt_row(entry.count, entry.level, entry.template, 110))
    lines.append("")

    lines.append("=== 热点源码位置 (module:func:line) ===")
    lines.append(f"{'条数':>6}  {'级别':<7}  位置")
    lines.append("-" * 110)
    # Re-derive level per location is lossy; show location + aggregate count.
    for loc, cnt in location_counts.most_common(20):
        lines.append(f"{cnt:>6}  {'W/E':<7}  {loc}")
    lines.append("")

    lines.append("=== 模板详情 (前 12) ===")
    for entry in stats[:12]:
        lines.append(f"\n--- {entry.level} count={entry.count} bucket={entry.bucket} ---")
        lines.append(f"模板: {entry.template}")
        for loc, cnt in entry.top_locations:
            lines.append(f"  位置: {cnt:>4}  {loc}")
        for sample in entry.samples[:2]:
            sample = " ".join(sample.split())
            lines.append(f"  样本: {sample[:200]}")
    return "\n".join(lines)


def render_json(
    stats: list[TemplateStat],
    level_counts: dict[str, int],
    bucket_counts: Counter,
    location_counts: Counter,
    meta: dict[str, int],
) -> str:
    """Render a JSON report (templates + buckets + locations)."""
    payload = {
        "meta": {
            **meta,
            "level_counts": level_counts,
            "template_count": len(stats),
        },
        "buckets": [
            {"bucket": b, "count": c} for b, c in bucket_counts.most_common()
        ],
        "top_locations": [
            {"location": loc, "count": c} for loc, c in location_counts.most_common(20)
        ],
        "templates": [
            {
                **asdict(entry),
                "top_locations": entry.top_locations,
            }
            for entry in stats
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze backend logs with drain3 template clustering"
    )
    parser.add_argument(
        "--logs",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help=f"Log directory (default: {DEFAULT_LOG_DIR})",
    )
    parser.add_argument(
        "--levels",
        nargs="+",
        default=["WARNING", "ERROR"],
        help="Log levels to include (default: WARNING ERROR)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=30,
        help="Number of top templates/locations to display (default: 30)",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Earliest log date (YYYY-MM-DD, filename-based) to include",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Write a JSON report to this path in addition to stdout",
    )
    parser.add_argument(
        "--sim-th",
        type=float,
        default=0.5,
        help="drain3 similarity threshold, lower merges more (default: 0.5)",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=5,
        help="drain3 tree depth (default: 5)",
    )
    args = parser.parse_args()

    if not args.logs.is_dir():
        print(f"error: log directory not found: {args.logs}", file=sys.stderr)
        sys.exit(1)

    since = None
    if args.since:
        try:
            since = datetime.strptime(args.since, "%Y-%m-%d").date()
        except ValueError:
            print(f"error: --since must be YYYY-MM-DD, got {args.since!r}", file=sys.stderr)
            sys.exit(1)

    stats, level_counts, bucket_counts, location_counts, meta = analyze(
        args.logs,
        set(args.levels),
        top=args.top,
        since=since,
        sim_th=args.sim_th,
        depth=args.depth,
    )

    report = render_text(
        stats, level_counts, bucket_counts, location_counts, meta, top=args.top
    )
    print(report)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            render_json(stats, level_counts, bucket_counts, location_counts, meta),
            encoding="utf-8",
        )
        print(f"\nJSON report written to {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
