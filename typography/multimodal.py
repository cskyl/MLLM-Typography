"""Multi-modal typography: combine audio and visual perturbations on a single video."""

import os
from dataclasses import dataclass, field
from typing import Optional

from .audio import (
    AudioAttackConfig,
    AudioAttackResult,
    mix_speech_into_video,
    render_speech,
)
from .utils import ensure_dir, get_duration, safe_remove
from .visual import (
    VisualAttackConfig,
    VisualAttackResult,
    overlay_text_on_video,
)


@dataclass
class MultimodalAttackResult:
    output_video: str
    audio: AudioAttackResult
    visual: VisualAttackResult


def inject_multimodal_typography(
    video_in: str,
    audio_text: str,
    visual_text: str,
    video_out: str,
    tts_cache_dir: str,
    audio_config: Optional[AudioAttackConfig] = None,
    visual_config: Optional[VisualAttackConfig] = None,
    tmp_dir: Optional[str] = None,
) -> MultimodalAttackResult:
    """Apply audio injection followed by visual overlay.

    Audio and visual targets can be the same (an *aligned* attack) or different
    (a *conflicting* attack); the API does not distinguish between the two.
    """
    a_cfg = audio_config or AudioAttackConfig()
    v_cfg = visual_config or VisualAttackConfig()

    tmp_dir = tmp_dir or os.path.join(os.path.dirname(video_out) or ".", "_tmp")
    ensure_dir(tmp_dir)

    duration = get_duration(video_in) if a_cfg.repeat_to_duration else None
    speech_wav, repeats = render_speech(audio_text, tts_cache_dir, duration, a_cfg)

    mixed = os.path.join(
        tmp_dir, os.path.basename(video_out) + ".audiomix.mp4"
    )
    mix_speech_into_video(video_in, speech_wav, mixed, a_cfg)

    try:
        v_result = overlay_text_on_video(mixed, visual_text, video_out, v_cfg, tmp_dir)
    finally:
        safe_remove(mixed)

    a_result = AudioAttackResult(
        output_video=os.path.abspath(video_out),
        speech_wav=os.path.abspath(speech_wav),
        repeat_count=repeats,
        config=a_cfg,
    )
    return MultimodalAttackResult(
        output_video=os.path.abspath(video_out),
        audio=a_result,
        visual=v_result,
    )
