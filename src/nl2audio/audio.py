from __future__ import annotations

from pydub import AudioSegment, effects, silence


def normalize(seg: AudioSegment, target_dbfs: float = -16.0) -> AudioSegment:
    change = target_dbfs - seg.dBFS if seg.dBFS != float("-inf") else 0
    return seg.apply_gain(change)


def trim_silence(
    seg: AudioSegment, threshold: float = -35.0, padding_ms: int = 150
) -> AudioSegment:
    start_end = silence.detect_nonsilent(
        seg, min_silence_len=200, silence_thresh=threshold
    )
    if not start_end:
        return seg
    start = max(0, start_end[0][0] - padding_ms)
    end = min(len(seg), start_end[-1][1] + padding_ms)
    return seg[start:end]
