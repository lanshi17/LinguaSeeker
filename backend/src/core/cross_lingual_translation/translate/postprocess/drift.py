"""Post-processing: dedup, quality flagging, language check, block building."""

from __future__ import annotations

from typing import List


from ...contracts import (
    SegmentDrift,
)

def compute_translation_drift(
    source_segments: List[str],
    translated_parts: List[str],
) -> List[SegmentDrift]:
    """Compute character drift between source and translated segments.

    For each segment pair, tracks the offset positions and length changes.
    """
    drifts: list[SegmentDrift] = []
    source_offset = 0
    translated_offset = 0

    for idx in range(max(len(source_segments), len(translated_parts))):
        src = source_segments[idx] if idx < len(source_segments) else ""
        tr = translated_parts[idx] if idx < len(translated_parts) else ""
        src_len = len(src)
        tr_len = len(tr)
        length_drift = tr_len - src_len

        drifts.append(
            SegmentDrift(
                segment_index=idx,
                source_start=source_offset,
                source_end=source_offset + src_len,
                translated_start=translated_offset,
                translated_end=translated_offset + tr_len,
                source_length=src_len,
                translated_length=tr_len,
                length_drift=length_drift,
                source_text=src[:200],  # Truncate for JSON readability
                translated_text=tr[:200],
            )
        )
        source_offset += src_len + 2  # +2 for "\n\n" joiner
        translated_offset += tr_len + 2

    return drifts
