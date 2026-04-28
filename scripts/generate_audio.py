#!/usr/bin/env python3
"""Generate audio-typography attacks from a manifest of (video, target).

Manifest format: one JSON object per line, e.g.

    {"video": "clips/cat_001.mp4", "target": "horse"}
    {"video": "clips/cat_002.mp4", "target": "horse", "output": "out/cat_002_attack.mp4"}

If ``output`` is omitted it defaults to ``<output_dir>/<stem>_audio_<target>.mp4``.
"""

import argparse
import os

import _common  # noqa: F401  (sys.path side-effect)
from typography.audio import AudioAttackConfig, inject_audio_typography
from typography.utils import (
    derive_output_path,
    ensure_dir,
    load_jsonl,
    save_jsonl,
)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--manifest", required=True, help="Input manifest (jsonl).")
    p.add_argument("--output-dir", required=True, help="Where attacked videos are written.")
    p.add_argument("--annotations", default=None, help="Output annotations jsonl path.")
    p.add_argument("--tts-cache", default=None, help="TTS wav cache dir (default: <output-dir>/tts_cache).")
    p.add_argument("--num-proc", type=int, default=8)

    p.add_argument("--voice", default="en-US-JennyNeural")
    p.add_argument("--gain", type=float, default=1.0)
    p.add_argument("--leading-silence", type=float, default=0.3)
    p.add_argument("--no-loudnorm", action="store_true")
    p.add_argument("--no-repeat", action="store_true",
                   help="Do not tile speech to match video duration.")
    p.add_argument("--max-repeat", type=int, default=20)
    p.add_argument("--no-compress", action="store_true")
    p.add_argument("--insertion-start", type=float, default=None,
                   help="Optional start offset (seconds) for the injected speech.")
    return p.parse_args()


def make_config(args) -> AudioAttackConfig:
    return AudioAttackConfig(
        voice=args.voice,
        gain=args.gain,
        leading_silence=args.leading_silence,
        loudnorm=not args.no_loudnorm,
        repeat_to_duration=not args.no_repeat,
        max_repeat=args.max_repeat,
        compress=not args.no_compress,
        insertion_start_sec=args.insertion_start,
    )


def build_task(record: dict, output_dir: str) -> dict:
    video = record["video"]
    target = record["target"]
    output = record.get("output") or derive_output_path(video, output_dir, target, "audio")
    return {"video": video, "target": target, "output": output, "meta": record}


def worker(task_and_cfg):
    task, cfg, tts_cache = task_and_cfg
    if os.path.isfile(task["output"]):
        return {"output": task["output"], "skipped": True, "task": task}
    result = inject_audio_typography(
        video_in=task["video"],
        target_text=task["target"],
        video_out=task["output"],
        tts_cache_dir=tts_cache,
        config=cfg,
    )
    return {
        "output": result.output_video,
        "speech_wav": result.speech_wav,
        "repeat_count": result.repeat_count,
        "task": task,
    }


def main():
    args = parse_args()
    ensure_dir(args.output_dir)
    tts_cache = args.tts_cache or os.path.join(args.output_dir, "tts_cache")
    ensure_dir(tts_cache)
    cfg = make_config(args)

    records = load_jsonl(args.manifest)
    tasks = [(build_task(r, args.output_dir), cfg, tts_cache) for r in records]
    print(f"[audio] {len(tasks)} videos | output -> {args.output_dir}")

    annotations = []
    failures = []
    from _common import run_parallel

    for result, err in run_parallel(worker, tasks, args.num_proc):
        if err is not None:
            failures.append(err)
            continue
        task = result["task"]
        annotations.append({
            "video_in": task["video"],
            "target": task["target"],
            "output": result["output"],
            "speech_wav": result.get("speech_wav"),
            "repeat_count": result.get("repeat_count"),
            "exp_type": "audio_typography",
            "voice": cfg.voice,
            "gain": cfg.gain,
            "leading_silence": cfg.leading_silence,
            "compress": cfg.compress,
            "source_record": task["meta"],
        })

    out_anno = args.annotations or os.path.join(args.output_dir, "annotations_audio.jsonl")
    save_jsonl(annotations, out_anno)
    print(f"[audio] wrote {len(annotations)} annotations -> {out_anno}")
    if failures:
        print(f"[audio] {len(failures)} failures")
        for f in failures[:10]:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
