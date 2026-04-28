"""Multi-Modal Typography pipeline.

Submodules:

- ``typography.audio``      — audio typography (TTS injection)
- ``typography.visual``     — visual typography (text overlay)
- ``typography.multimodal`` — combined audio + visual perturbation
- ``typography.tts``        — text-to-speech and post-processing helpers
- ``typography.utils``      — ffmpeg / ffprobe wrappers and IO helpers

Submodules are imported lazily so ``import typography`` does not require every
optional dependency to be present (e.g. opencv-python is only needed for
visual attacks).
"""

import importlib
from typing import TYPE_CHECKING

__version__ = "0.1.0"

_LAZY = {
    "synthesize_tts": ("typography.tts", "synthesize_tts"),
    "normalize_and_pad": ("typography.tts", "normalize_and_pad"),
    "tile_to_duration": ("typography.tts", "tile_to_duration"),
    "inject_audio_typography": ("typography.audio", "inject_audio_typography"),
    "inject_visual_typography": ("typography.visual", "inject_visual_typography"),
    "inject_multimodal_typography": ("typography.multimodal", "inject_multimodal_typography"),
}


def __getattr__(name):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module 'typography' has no attribute {name!r}")


if TYPE_CHECKING:  # for editor autocomplete only
    from .audio import inject_audio_typography  # noqa: F401
    from .multimodal import inject_multimodal_typography  # noqa: F401
    from .tts import normalize_and_pad, synthesize_tts, tile_to_duration  # noqa: F401
    from .visual import inject_visual_typography  # noqa: F401


__all__ = list(_LAZY.keys())
