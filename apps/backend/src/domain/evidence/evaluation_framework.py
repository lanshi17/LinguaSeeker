"""
PS3/BS3 评估框架工具函数。

实现内容:
1. 四步法证据强度判定（对应文档中的 determine_evidence_strength 逻辑）
2. OddsPath -> 通用强度分级
3. 文本抽取结果评估指标计算
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from loguru import logger

from src.domain.enums import EvidenceStrength


NO_PS3_BS3 = "No PS3/BS3"
SUPPORTING = "Supporting"
MODERATE = "Moderate"
STRONG = "Strong"
VERY_STRONG = "Very Strong"

DEFAULT_MATCH_FIELDS: Tuple[str, ...] = (
    "gene",
    "variant",
    "disease",
    "assay_type",
)


@dataclass(frozen=True)
class ExtractionEvaluationMetrics:
    benchmark_total: int
    model_output_total: int
    correct_count: int
    false_assertions: int
    field_omissions: int
    accuracy: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark_total": self.benchmark_total,
            "model_output_total": self.model_output_total,
            "correct_count": self.correct_count,
            "false_assertions": self.false_assertions,
            "field_omissions": self.field_omissions,
            "accuracy": self.accuracy,
        }


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {
            "1",
            "true",
            "t",
            "yes",
            "y",
            "clear",
            "approved",
            "pass",
        }
    return False


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_dict(raw: Any) -> Dict[str, Any]:
    return raw if isinstance(raw, dict) else {}


def _normalize_token(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return "|".join(sorted(_normalize_token(item) for item in value))
    if isinstance(value, dict):
        return "|".join(
            f"{k}:{_normalize_token(v)}" for k, v in sorted(value.items(), key=lambda item: item[0])
        )
    return str(value).strip().lower()


def _read_nested(item: Mapping[str, Any], field_path: str) -> Any:
    current: Any = item
    for segment in field_path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(segment)
    return current


def evaluate_assay_validity_approved(data: Mapping[str, Any]) -> bool:
    step2 = _get_dict(data.get("ps3_step_2"))
    assay_suitable = (
        data.get("assay_suitable")
        or data.get("approved_assay")
        or step2.get("assay_suitable")
    )
    if isinstance(assay_suitable, str):
        return assay_suitable.strip().lower() == "yes"
    return _as_bool(assay_suitable)


def evaluate_assay_validity_control(data: Mapping[str, Any]) -> bool:
    step3 = _get_dict(data.get("ps3_step_3"))
    checkpoint_3a = _get_dict(step3.get("checkpoint_3a"))
    checkpoint_3b = _get_dict(step3.get("checkpoint_3b"))

    controls_present = _as_bool(
        data.get("basic_controls_present", checkpoint_3a.get("basic_controls_present"))
    )
    replicates_used = _as_bool(data.get("replicates_used", checkpoint_3a.get("replicates_used")))
    method_validated = _as_bool(data.get("method_validated", checkpoint_3b.get("method_validated")))

    # 3a 通过即可继续；3a 不足时允许 3b 通过作为替代路径。
    return (controls_present and replicates_used) or method_validated


def evaluate_assay_contains_known_variants(data: Mapping[str, Any]) -> bool:
    step3 = _get_dict(data.get("ps3_step_3"))
    checkpoint_3c = _get_dict(step3.get("checkpoint_3c"))
    explicit = data.get("known_variants_present")
    if explicit is not None:
        return _as_bool(explicit)
    if checkpoint_3c:
        return _as_bool(checkpoint_3c.get("positive_controls_used"))
    pathogenic_count, benign_count = count_pathogenic_benign_variants(data)
    return (pathogenic_count + benign_count) > 0


def count_pathogenic_benign_variants(data: Mapping[str, Any]) -> Tuple[int, int]:
    step4 = _get_dict(data.get("ps3_step_4"))
    control_count_data = _get_dict(step4.get("control_count_data"))

    pathogenic_count = _safe_int(
        control_count_data.get("pathogenic_count", data.get("pathogenic_count", 0))
    )
    benign_count = _safe_int(control_count_data.get("benign_count", data.get("benign_count", 0)))

    if pathogenic_count == 0 and benign_count == 0:
        known_controls = data.get("known_control_variants")
        if isinstance(known_controls, list):
            for item in known_controls:
                if isinstance(item, dict):
                    cls = str(item.get("classification", "")).strip().lower()
                    if cls in {"pathogenic", "likely_pathogenic", "p", "lp"}:
                        pathogenic_count += 1
                    elif cls in {"benign", "likely_benign", "b", "lb"}:
                        benign_count += 1
    return pathogenic_count, benign_count


def _calculate_oddspath_from_p1_p2(data: Mapping[str, Any]) -> Optional[float]:
    p1 = _safe_float(data.get("P1"))
    p2 = _safe_float(data.get("P2"))
    if p1 is None or p2 is None:
        return None
    if p1 <= 0 or p1 >= 1 or p2 <= 0 or p2 >= 1:
        return None
    return (p2 * (1 - p1)) / ((1 - p2) * p1)


def calculate_oddpath(
    data: Mapping[str, Any],
) -> Tuple[bool, Optional[float], bool]:
    step4 = _get_dict(data.get("ps3_step_4"))
    oddspath_data = _get_dict(step4.get("oddspath_data"))

    computable = oddspath_data.get("computable")
    oddspath = _safe_float(oddspath_data.get("oddspath"))
    is_perfect_binary = _as_bool(oddspath_data.get("is_perfect_binary"))

    if computable is None and oddspath is not None:
        computable = True

    if computable is not None and not _as_bool(computable):
        return False, None, is_perfect_binary

    if oddspath is None:
        oddspath = _safe_float(data.get("oddspath"))
    if oddspath is None:
        oddspath = _calculate_oddspath_from_p1_p2(oddspath_data) or _calculate_oddspath_from_p1_p2(data)

    can_calculate = oddspath is not None
    return can_calculate, oddspath, is_perfect_binary


def determine_strength_by_oddpath(
    odds_path: float,
    is_perfect_binary: Optional[bool] = None,
) -> str:
    """基于 OddsPath 值和条件确定证据强度（通用分级）。"""
    if odds_path < 0:
        logger.warning("OddsPath={} is invalid, fallback to Supporting", odds_path)
        return SUPPORTING

    if (odds_path < 0.0029) or (odds_path > 350):
        return VERY_STRONG
    if (0.0029 <= odds_path < 0.053) or (18.7 < odds_path <= 350):
        return STRONG
    if (0.053 <= odds_path < 0.23) or (4.3 < odds_path <= 18.7):
        return MODERATE

    # 其余区间（含 0.23~4.3）默认为 Supporting。
    if is_perfect_binary is True and odds_path in {0.0, float("inf")}:
        return VERY_STRONG
    return SUPPORTING


def _resolve_direction(data: Mapping[str, Any], odds_path: Optional[float]) -> str:
    for key in ("functional_evidence_aim", "evidence_direction", "direction"):
        raw = data.get(key)
        if not isinstance(raw, str):
            continue
        token = raw.strip().lower()
        if token in {"pathogenic", "ps3", "p"}:
            return "pathogenic"
        if token in {"benign", "bs3", "b"}:
            return "benign"

    if odds_path is not None:
        if odds_path > 1:
            return "pathogenic"
        if odds_path < 1:
            return "benign"

    return "pathogenic"


def _map_generic_to_directional_strength(
    generic_strength: str,
    direction: str,
) -> str:
    if generic_strength == NO_PS3_BS3:
        return NO_PS3_BS3

    if direction == "benign":
        return {
            SUPPORTING: EvidenceStrength.BS3_SUPPORTING.value,
            MODERATE: EvidenceStrength.BS3_MODERATE.value,
            STRONG: EvidenceStrength.BS3.value,
            VERY_STRONG: EvidenceStrength.BS3_VERY_STRONG.value,
        }[generic_strength]

    return {
        SUPPORTING: EvidenceStrength.PS3_SUPPORTING.value,
        MODERATE: EvidenceStrength.PS3_MODERATE.value,
        STRONG: EvidenceStrength.PS3.value,
        VERY_STRONG: EvidenceStrength.PS3_VERY_STRONG.value,
    }[generic_strength]


def determine_evidence_strength(data: Mapping[str, Any]) -> Dict[str, Any]:
    """
    四步法总控流程:
    1) 方法适用性
    2) 对照/重复有效性
    3) 已知变异对照
    4) OddsPath 或对照变异计数
    """
    if not evaluate_assay_validity_approved(data):
        return {
            "use_ps3_bs3": False,
            "strength": NO_PS3_BS3,
            "directional_strength": NO_PS3_BS3,
            "path": "not_applicable",
            "reason": "assay_not_approved",
        }

    if not evaluate_assay_validity_control(data):
        return {
            "use_ps3_bs3": False,
            "strength": NO_PS3_BS3,
            "directional_strength": NO_PS3_BS3,
            "path": "not_applicable",
            "reason": "controls_or_replicates_insufficient",
        }

    if not evaluate_assay_contains_known_variants(data):
        direction = _resolve_direction(data, odds_path=None)
        directional_strength = _map_generic_to_directional_strength(SUPPORTING, direction)
        return {
            "use_ps3_bs3": True,
            "strength": SUPPORTING,
            "directional_strength": directional_strength,
            "path": "no_known_variants",
            "reason": "known_variants_missing",
        }

    can_calculate_oddpath, oddspath, is_perfect_binary = calculate_oddpath(data)
    if not can_calculate_oddpath or oddspath is None:
        pathogenic_count, benign_count = count_pathogenic_benign_variants(data)
        total_count = pathogenic_count + benign_count
        strength = MODERATE if total_count > 10 else SUPPORTING
        direction = _resolve_direction(data, odds_path=None)
        directional_strength = _map_generic_to_directional_strength(strength, direction)
        return {
            "use_ps3_bs3": True,
            "strength": strength,
            "directional_strength": directional_strength,
            "path": "control_count",
            "reason": "oddspath_not_computable",
            "pathogenic_count": pathogenic_count,
            "benign_count": benign_count,
            "total_count": total_count,
        }

    strength = determine_strength_by_oddpath(oddspath, is_perfect_binary)
    direction = _resolve_direction(data, oddspath)
    directional_strength = _map_generic_to_directional_strength(strength, direction)
    return {
        "use_ps3_bs3": True,
        "strength": strength,
        "directional_strength": directional_strength,
        "path": "oddspath",
        "reason": "oddspath_computed",
        "oddspath": oddspath,
        "is_perfect_binary": is_perfect_binary,
    }


def evaluate_extraction_metrics(
    benchmark_items: Sequence[Mapping[str, Any]],
    model_items: Sequence[Mapping[str, Any]],
    match_fields: Sequence[str] = DEFAULT_MATCH_FIELDS,
) -> ExtractionEvaluationMetrics:
    """
    计算抽取任务基础指标:
    - benchmark_total
    - model_output_total
    - correct_count
    - false_assertions
    - field_omissions
    - accuracy
    """
    def _signature(item: Mapping[str, Any]) -> Tuple[str, ...]:
        values = tuple(_normalize_token(_read_nested(item, field)) for field in match_fields)
        return values

    benchmark_signatures = {_signature(item) for item in benchmark_items}
    model_signatures = {_signature(item) for item in model_items}

    # 删除全空签名，避免空对象影响统计。
    empty_signature = tuple("" for _ in match_fields)
    benchmark_signatures.discard(empty_signature)
    model_signatures.discard(empty_signature)

    benchmark_total = len(benchmark_signatures)
    model_output_total = len(model_signatures)
    correct_count = len(benchmark_signatures & model_signatures)
    false_assertions = max(0, model_output_total - correct_count)
    field_omissions = max(0, benchmark_total - correct_count)
    accuracy = (correct_count / benchmark_total) if benchmark_total else 0.0

    return ExtractionEvaluationMetrics(
        benchmark_total=benchmark_total,
        model_output_total=model_output_total,
        correct_count=correct_count,
        false_assertions=false_assertions,
        field_omissions=field_omissions,
        accuracy=round(accuracy, 4),
    )
