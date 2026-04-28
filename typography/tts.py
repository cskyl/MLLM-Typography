"""Text-to-speech synthesis and post-processing.

Edge-TTS is the default backend. To plug in a different engine, replace
``synthesize_tts`` or pass a pre-rendered wav into the pipeline.
"""

import asyncio
import os
from typing import Optional

from .utils import ensure_dir, get_duration, run_checked


DEFAULT_VOICE = "en-US-JennyNeural"


def synthesize_tts(
    text: str,
    out_path: str,
    voice: str = DEFAULT_VOICE,
    rate: Optional[str] = None,
    pitch: Optional[str] = None,
) -> None:
    """Render ``text`` to a wav at ``out_path`` using edge-tts."""
    import edge_tts

    ensure_dir(os.path.dirname(os.path.abspath(out_path)))
    text = text.replace("_", " ").strip()

    async def _run():
        kwargs = {}
        if rate is not None:
            kwargs["rate"] = rate
        if pitch is not None:
            kwargs["pitch"] = pitch
        communicate = edge_tts.Communicate(text, voice, **kwargs)
        await communicate.save(out_path)

    asyncio.run(_run())


def normalize_and_pad(
    wav_in: str,
    wav_out: str,
    leading_silence: float = 0.3,
    loudnorm: bool = True,
) -> None:
    """Apply EBU R128 loudness normalization and prepend leading silence."""
    delay_ms = int(max(0.0, leading_silence) * 1000)
    chain = []
    if loudnorm:
        chain.append("loudnorm")
    if delay_ms > 0:
        chain.append(f"adelay={delay_ms}|{delay_ms}")
    af = ",".join(chain) if chain else "anull"
    run_checked(f'ffmpeg -y -i "{wav_in}" -af "{af}" "{wav_out}"')


def tile_to_duration(
    wav_in: str,
    target_duration: float,
    wav_out: str,
    max_repeat: int = 20,
) -> int:
    """Repeat ``wav_in`` end-to-end until it covers ``target_duration``.

    Returns the actual repeat count used.
    """
    speech_dur = get_duration(wav_in)
    if speech_dur <= 0:
        raise RuntimeError(f"non-positive speech duration: {speech_dur}")

    repeat = min(max_repeat, int(target_duration // speech_dur) + 1)
    repeat = max(1, repeat)

    list_file = wav_out + ".concat"
    abs_in = os.path.abspath(wav_in).replace("'", "'\\''")
    with open(list_file, "w") as f:
        for _ in range(repeat):
            f.write(f"file '{abs_in}'\n")

    try:
        run_checked(
            f'ffmpeg -y -f concat -safe 0 -i "{list_file}" '
            f'-c:a pcm_s16le "{wav_out}"'
        )
    finally:
        if os.path.isfile(list_file):
            os.remove(list_file)

    return repeat
