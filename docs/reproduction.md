# Reproduction materials for the updated manuscript

[Latest manuscript PDF](../paper.pdf) · [arXiv record](https://arxiv.org/abs/2604.03995)

The existing release provides audio, visual, and combined attack generators,
MMA-Bench and WorldSense attack manifests, QA labels, and a prediction-scoring
script. See the [main README](../README.md) for commands.

| Material | Location |
| --- | --- |
| Attack-generation library | [`typography/`](../typography/) |
| Generation and scoring commands | [`scripts/`](../scripts/) |
| MMA-Bench: 658 clips, 1,316 audio/visual questions | [`benchmarks/mma_bench/`](../benchmarks/mma_bench/) |
| WorldSense: 1,585 questions and fixed wrong targets | [`benchmarks/worldsense/`](../benchmarks/worldsense/) |
| AudioSet SFT: 998 paired clean/attacked training annotations | [`data/audioset_sft/`](../data/audioset_sft/) |
| Complete SFT video archive: 1,996 MP4 files and annotations, 4.40 GB | [Google Drive ZIP](https://drive.google.com/file/d/1JUMbSyF3r3pskxYcdpf1zGp8rcmDQQaJ/view) |
| Fine-tuning settings reported in the paper | [Settings below](#fine-tuning-settings) |

The benchmark manifests above are evaluation data. They are separate from the
AudioSet training subset used for the fine-tuning defense.

`scripts/evaluate.py` is a generic scoring helper: it uses normalized substring
matching and scores only questions with a supplied prediction. The updated
paper uses benchmark-specific parsing and complete evaluation sets. Its reported
results should therefore not be compared with arbitrary free-text outputs scored
by this helper.

## Fine-tuning settings

These settings summarize the updated paper's “Training Data and Fine-Tuning
Settings” subsection. This is a reference specification, not a runnable training
configuration. The [SFT data directory](../data/audioset_sft/) provides the exact
training conversations, source IDs and segment times, labels, attack targets,
and mixing parameters. The processed clean and attacked videos are available
in the linked Drive ZIP. The SFT media renderer, training launcher, and
attention analysis scripts are not included in this release.

| Setting | Value |
| --- | --- |
| Model | Qwen2.5-Omni-7B |
| Training data | 998 AudioSet videos, 10 seconds each; 61 answer options, 60 represented training labels |
| Training conditions | Clean videos; the same videos with misleading speech |
| Training target | Original sound class in both conditions |
| Training cue | Piper speech: `This is {wrong class}.`, once at 1 second |
| Training speech level | Scaled to the RMS level of the original soundtrack |
| LoRA rank / scale / dropout | 8 / 16 / 0.05 |
| Frozen components | Vision encoder and projector |
| Learning rate / schedule | 1e-4 / cosine |
| Warmup ratio | 0.1 |
| Batch size / gradient accumulation | 1 / 8 |
| Optimizer updates | 375, approximately three passes over the training set |
| Evaluated checkpoint | Final checkpoint |

WorldSense evaluation uses a different speech recipe: Edge-TTS
`en-US-JennyNeural`, volume 2, repeated over the clip, with the cue
`The answer is: {wrong option text}.` The paper evaluates clean and attacked
inputs on the same 1,585 questions. Training uses no WorldSense questions or
answers.

## Attention analyses

The updated paper includes three distinct analyses:

- **Attack-window attention on MMA-Bench:** attention within the attacked
  modality during a 25% or 50% temporal window, including correct/incorrect
  comparisons, prompt hints, and held-out-class prediction of correctness.
- **Layer-wise answer scores on WorldSense:** the change in the wrong target's
  score relative to the other wrong options on 113 questions. This uses the
  model's output projection rather than a trained probe.
- **Speech position on AudioSet:** attention from the last prompt position in
  layers 20, 24, and 27, evaluated on 100 videos with early, middle, or late cues.

These measurements use different inputs and aggregations. Their implementation
and preprocessing details are described in the paper's appendix.

## Data sources and attribution

Original benchmark videos remain with their providers; this repository supplies
attack manifests and provenance rather than redistributing those videos. See
the per-benchmark READMEs for acquisition instructions. The fine-tuning study
uses [AudioSet](https://research.google.com/audioset/), and the model is
[Qwen2.5-Omni-7B](https://huggingface.co/Qwen/Qwen2.5-Omni-7B).
