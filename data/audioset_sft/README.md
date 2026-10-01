# AudioSet data for the fine-tuning defense

This directory contains the annotations for the **998 training videos** used
in the paper's clean and attacked fine-tuning conditions. Both conditions use
the same videos, prompts, original sound labels, and row order. In the attacked
condition, a spoken sentence names a different sound class; the training answer
remains the original class.

| File | Contents |
| --- | --- |
| [`train_manifest.jsonl`](train_manifest.jsonl) | 998 source IDs, segment times, labels, wrong targets, spoken sentences, and per-video mixing parameters |
| [`train_clean.jsonl`](train_clean.jsonl) | 998 clean training conversations |
| [`train_attack.jsonl`](train_attack.jsonl) | 998 attacked training conversations |
| [`dataset_info.json`](dataset_info.json) | Dataset column and role mappings for the training loader |
| [`classes.json`](classes.json) | The 61 answer options, in prompt order |
| [`speech_recipe.json`](speech_recipe.json) | Recorded TTS, timing, volume, and encoding settings |
| [`dataset_summary.json`](dataset_summary.json) | Counts, model revision, exclusions, and source-file checksums |

These files preserve the final training export. Only the machine-specific
media paths in the conversations have been replaced with relative paths.
The answer vocabulary has 61 classes; 60 occur as true labels in the final
998-video subset. `Gears` remains an answer option and can be an attack target.
The separate development set is not included here.

## Obtaining the media

[Download the complete SFT ZIP from Google Drive](https://drive.google.com/file/d/1JUMbSyF3r3pskxYcdpf1zGp8rcmDQQaJ/view).

The archive contains all **1,996 processed MP4 files** (998 clean/attacked
pairs), the training annotations, speech settings, and per-file checksums.
It is 4.40 GB (4,400,189,869 bytes). GitHub hosts the annotations; the video
archive is hosted on Drive. See [archive_download.json](archive_download.json)
for the archive's SHA-256 and exact size.

Extract it into a separate directory and verify the files with:

```bash
unzip typography_audioset_sft_998_20261001.zip
cd audioset_sft
sha256sum -c SHA256SUMS
```

Each manifest row records the source YouTube URL and the AudioSet segment's
`start_seconds` and `end_seconds`. See the
[AudioSet metadata page](https://research.google.com/audioset/download.html)
for the source dataset. Source-video availability can change.

The relative paths have this layout, with `media/` resolved from this directory:

```text
media/train/clean/<source_video_id>.mp4
media/train/attack/<source_video_id>_speechMix_<attack_target>.mp4
```

The clean files in the archive are processed controls: their audio has the same
resampling and peak scaling as the attacked files. Original downloads should
not be renamed as these controls. The SFT media renderer and training launcher
are not included in this release; the repository's generic attack command does
not by itself reproduce this SFT recipe.

## Training and speech settings

The exact prompts and original-label answers are stored in both conversation
files. Each video is also passed as the audio source, so `videos` and `audios`
point to the same MP4.

The attack uses Piper's `en_US-amy-medium` voice to say
`This is {wrong class}.` once, starting at one second. The exact spoken text,
including underscores in class names, is stored in `speech_text`. Speech volume
is scaled so that its active-speech RMS equals the original soundtrack's
full-clip RMS. Both conditions then receive the same peak-safe scale. The audio
is mono at 22,050 Hz with lossless ALAC encoding; video frames are copied.

See the [fine-tuning settings](../../docs/reproduction.md#fine-tuning-settings)
for the model and optimization parameters. These training annotations are
separate from the MMA-Bench and WorldSense evaluation manifests.
