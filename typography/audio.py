"""Audio typography: inject a synthesized spoken cue into a video soundtrack."""

import os
from dataclasses import dataclass, field
from typing import Optional

from .tts import (
    DEFAULT_VOICE,
    normalize_and_pad,
    synthesize_tts,
    tile_to_duration,
)
from .utils import ensure_dir, get_duration, run_checked, safe_remove


@dataclass
class AudioAttackConfig:
    voice: str = DEFAULT_VOICE
    gain: float = 1.0
    leading_silence: float = 0.3
    loudnorm: bool = True
    repeat_to_duration: bool = True
    max_repeat: int = 20
    compress: bool = True
    compress_threshold_db: float = -10.0
    compress_ratio: float = 4.0
    insertion_start_sec: Optional[float] = None
    audio_codec: str = "aac"
    audio_bitrate: str = "128k"
    video_codec: str = "copy"

    @property
    def speech_filter(self) -> str:
        parts = [f"volume={self.gain}"]
        if self.compress:
            parts.append(
                f"acompressor=threshold={self.compress_threshold_db}dB:"
                f"ratio={self.compress_ratio}"
            )
        if self.insertion_start_sec is not None and self.insertion_start_sec > 0:
            ms = int(self.insertion_start_sec * 1000)
            parts.append(f"adelay={ms}|{ms}")
        return ",".join(parts)


@dataclass
class AudioAttackResult:
    output_video: str
    speech_wav: str
    repeat_count: int
    config: AudioAttackConfig = field(default_factory=AudioAttackConfig)


def render_speech(
    text: str,
    out_dir: str,
    target_duration: Optional[float],
    config: AudioAttackConfig,
    cache_key: Optional[str] = None,
) -> tuple:
    """Synthesize -> normalize -> (optionally) tile. Returns (final_wav, repeat_count)."""
    ensure_dir(out_dir)
    key = (cache_key or text).replace(" ", "_").replace("/", "_")[:96]

    raw = os.path.join(out_dir, f"{key}__raw.wav")
    norm = os.path.join(out_dir, f"{key}__norm.wav")
    tiled = os.path.join(out_dir, f"{key}.wav")

    if os.path.isfile(tiled):
        return tiled, 0

    synthesize_tts(text, raw, voice=config.voice)
    normalize_and_pad(
        raw,
        norm,
        leading_silence=config.leading_silence,
        loudnorm=config.loudnorm,
    )

    if config.repeat_to_duration and target_duration is not None:
        repeats = tile_to_duration(
            norm, target_duration, tiled, max_repeat=config.max_repeat
        )
    else:
        os.replace(norm, tiled)
        repeats = 1

    safe_remove(raw)
    if os.path.abspath(norm) != os.path.abspath(tiled):
        safe_remove(norm)
    return tiled, repeats


def mix_speech_into_video(
    video_in: str,
    speech_wav: str,
    video_out: str,
    config: AudioAttackConfig,
) -> None:
    """Mix a speech track into the video's existing audio and re-mux."""
    ensure_dir(os.path.dirname(video_out) or ".")
    cmd = (
        f'ffmpeg -y -i "{video_in}" -i "{speech_wav}" '
        f'-filter_complex "[1:a]{config.speech_filter}[s];'
        f'[0:a][s]amix=inputs=2:dropout_transition=0[a]" '
        f'-map 0:v -map "[a]" '
        f'-c:v {config.video_codec} '
        f'-c:a {config.audio_codec} -b:a {config.audio_bitrate} '
        f'-shortest "{video_out}"'
    )
    run_checked(cmd)


def inject_audio_typography(
    video_in: str,
    target_text: str,
    video_out: str,
    tts_cache_dir: str,
    config: Optional[AudioAttackConfig] = None,
) -> AudioAttackResult:
    """Synthesize ``target_text`` and mix it into ``video_in``'s soundtrack."""
    cfg = config or AudioAttackConfig()
    duration = get_duration(video_in) if cfg.repeat_to_duration else None
    speech_wav, repeats = render_speech(target_text, tts_cache_dir, duration, cfg)
    mix_speech_into_video(video_in, speech_wav, video_out, cfg)
    return AudioAttackResult(
        output_video=os.path.abspath(video_out),
        speech_wav=os.path.abspath(speech_wav),
        repeat_count=repeats,
        config=cfg,
    )
