# Multi-Modal Typography

Code for **A Systematic Study of Cross-Modal Typographic Attacks on Audio-Visual
Reasoning**. The repository contains the data-generation pipeline used in the
paper, written as a small, dataset-agnostic library so it can be applied to any
video benchmark.

The pipeline produces three families of attacks:

- **Audio typography** — synthesize a misleading spoken phrase with text-to-speech
  and mix it into the original soundtrack.
- **Visual typography** — render a misleading text label as a persistent overlay
  on the video frames.
- **Multi-modal typography** — apply both perturbations on the same clip
  (with either *aligned* or *conflicting* targets).

The project page (`index.html`) and paper (`paper.pdf`) live in this same
repository.

## Install

```bash
pip install -r requirements.txt
# ffmpeg / ffprobe must be on PATH
ffmpeg -version
```

`edge-tts` is the default text-to-speech backend. Any backend works as long as
it produces a wav file — see `typography/tts.py`.

## Quick start

The pipeline is **manifest-driven**: each row in a JSONL manifest describes one
attack. A manifest looks like

```jsonl
{"video": "clips/cat_001.mp4", "target": "horse", "true_class": "cat"}
{"video": "clips/dog_002.mp4", "target": "piano", "true_class": "dog"}
```

This makes the code agnostic to dataset structure. If your data is laid out as
class-named folders, `scripts/build_manifest.py` will generate a manifest for
you.

### 1. Build a manifest from class folders (optional)

```bash
python scripts/build_manifest.py \
    --source-root /path/to/dataset \
    --output manifests/audio.jsonl \
    --mode single \
    --include-true-class
```

`--mode multimodal-aligned` and `--mode multimodal-conflict` produce manifests
with `audio_target` / `visual_target` fields for the multi-modal scripts.

### 2. Audio typography

```bash
python scripts/generate_audio.py \
    --manifest manifests/audio.jsonl \
    --output-dir outputs/audio \
    --voice en-US-JennyNeural \
    --gain 1.0 \
    --num-proc 8
```

Useful flags:

| Flag | Effect |
| --- | --- |
| `--gain` | Volume multiplier on the injected speech (paper sweep: 0.5×–8×). |
| `--leading-silence` | Padding before the speech, in seconds. |
| `--no-repeat` | Inject the cue once instead of tiling it to the video duration. |
| `--max-repeat` | Cap on the tile count (paper sweep: 1–50). |
| `--insertion-start` | Start offset for the injection (used in temporal-position ablations). |
| `--no-loudnorm` / `--no-compress` | Disable EBU R128 loudness normalization / dynamic-range compression. |

### 3. Visual typography

```bash
python scripts/generate_visual.py \
    --manifest manifests/visual.jsonl \
    --output-dir outputs/visual \
    --position center \
    --num-proc 8
```

Useful flags:

| Flag | Effect |
| --- | --- |
| `--position` | `center` / `top` / `bottom` anchor. |
| `--moving` | Bouncing-text overlay (paper's moving-text ablation). |
| `--duration-mode` | `full` / `seconds` / `ratio` — controls how long the text is on screen. |
| `--start-mode` | `start` / `center` / `end` / `random` — when the overlay starts. |
| `--frame-indices` | Sparse-frame mode: only the listed frames carry text. |

### 4. Multi-modal typography

```bash
python scripts/generate_multimodal.py \
    --manifest manifests/multimodal.jsonl \
    --output-dir outputs/multimodal \
    --gain 1.0 \
    --position center \
    --num-proc 4
```

Each manifest row supplies `audio_target` and `visual_target`. Setting them
equal reproduces the *aligned* attack; making them differ reproduces the
*conflicting* attack.

### 5. Build a QA file (optional)

`build_qa.py` turns an annotations file into the audio-grounded / visually-grounded
QA pairs used in the paper. It expects each manifest row to carry a `true_class`
field (or pass `--options "cat, dog, …"` explicitly).

```bash
python scripts/build_qa.py \
    --annotations outputs/audio/annotations_audio.jsonl \
    --output outputs/audio/qa.jsonl
```

## Library API

You can call the building blocks directly:

```python
from typography import (
    inject_audio_typography,
    inject_visual_typography,
    inject_multimodal_typography,
)
from typography.audio import AudioAttackConfig
from typography.visual import VisualAttackConfig

inject_audio_typography(
    video_in="clip.mp4",
    target_text="horse",
    video_out="clip_audio.mp4",
    tts_cache_dir="cache/tts",
    config=AudioAttackConfig(gain=2.0, leading_silence=0.3),
)

inject_visual_typography(
    video_in="clip.mp4",
    target_text="horse",
    video_out="clip_visual.mp4",
    config=VisualAttackConfig(position="center", moving=False),
)
```

`render_speech` (in `typography/audio.py`) is exposed if you only need the
intermediate spoken wav.

## Repository layout

```
typography/        # library: audio.py, visual.py, multimodal.py, tts.py, utils.py
scripts/           # CLI entry points + manifest / QA helpers
examples/          # example manifests
assets/            # project-page figures
index.html         # project page
paper.pdf          # camera-ready PDF
```

## Citation

```bibtex
@article{chen2026systematic,
  title={A Systematic Study of Cross-Modal Typographic Attacks on Audio-Visual Reasoning},
  author={Chen, Tianle and Ghadiyaram, Deepti},
  journal={arXiv preprint arXiv:2604.03995},
  year={2026}
}
```
