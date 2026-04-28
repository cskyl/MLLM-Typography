#!/usr/bin/env python3
"""Generate combined audio+visual typography attacks.

Manifest format (jsonl):

    {"video": "...", "audio_target": "horse", "visual_target": "horse"}
    {"video": "...", "audio_target": "horse", "visual_target": "dog"}    # conflicting

If ``audio_target`` / ``visual_target`` are missing, ``target`` is used for both
(aligned attack).
"""

import argparse
import os

import _common  # noqa: F401
from typography.audio import AudioAttackConfig
from typography.multimodal import inject_multimodal_typography
from typography.utils import (
    derive_output_path,
    ensure_dir,
    load_jsonl,
    save_jsonl,
)
from typography.visual import VisualAttackConfig


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--manifest", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--annotations", default=None)
    p.add_argument("--tts-cache", default=None)
    p.add_argument("--num-proc", type=int, default=4)

    # Audio
    p.add_argument("--voice", default="en-US-JennyNeural")
    p.add_argument("--gain", type=float, default=1.0)
    p.add_argument("--leading-silence", type=float, default=0.3)
    p.add_argument("--no-loudnorm", action="store_true")
    p.add_argument("--no-repeat", action="store_true")
    p.add_argument("--max-repeat", type=int, default=20)
    p.add_argument("--no-compress", action="store_true")

    # Visual
    p.add_argument("--position", choices=["center", "top", "bottom"], default="center")
    p.add_argument("--moving", action="store_true")
    p.add_argument("--font-scale", type=float, default=1.5)
    p.add_argument("--duration-mode", choices=["full", "seconds", "ratio"], default="full")
    p.add_argument("--duration-sec", type=float, default=1.0)
    p.add_argument("--duration-ratio", type=float, default=0.35)
    p.add_argument("--start-mode", choices=["start", "center", "end", "random"], default="start")
    return p.parse_args()


def make_audio_config(args) -> AudioAttackConfig:
    return AudioAttackConfig(
        voice=args.voice,
        gain=args.gain,
        leading_silence=args.leading_silence,
        loudnorm=not args.no_loudnorm,
        repeat_to_duration=not args.no_repeat,
        max_repeat=args.max_repeat,
        compress=not args.no_compress,
    )


def make_visual_config(args) -> VisualAttackConfig:
    return VisualAttackConfig(
        position=args.position,
        moving=args.moving,
        font_scale=args.font_scale,
        duration_mode=args.duration_mode,
        duration_sec=args.duration_sec,
        duration_ratio=args.duration_ratio,
        start_mode=args.start_mode,
    )


def build_task(record: dict, output_dir: str) -> dict:
    video = record["video"]
    audio_target = record.get("audio_target") or record.get("target")
    visual_target = record.get("visual_target") or record.get("target")
    if audio_target is None or visual_target is None:
        raise ValueError(f"manifest record missing target(s): {record}")
    suffix = f"A-{audio_target}_V-{visual_target}"
    output = record.get("output") or derive_output_path(video, output_dir, suffix, "av")
    return {
        "video": video,
        "audio_target": audio_target,
        "visual_target": visual_target,
        "output": output,
        "meta": record,
    }


def worker(task_pack):
    task, a_cfg, v_cfg, tts_cache = task_pack
    if os.path.isfile(task["output"]):
        return {"output": task["output"], "skipped": True, "task": task}
    result = inject_multimodal_typography(
        video_in=task["video"],
        audio_text=task["audio_target"],
        visual_text=task["visual_target"],
        video_out=task["output"],
        tts_cache_dir=tts_cache,
        audio_config=a_cfg,
        visual_config=v_cfg,
    )
    return {
        "output": result.output_video,
        "speech_wav": result.audio.speech_wav,
        "repeat_count": result.audio.repeat_count,
        "task": task,
    }


def main():
    args = parse_args()
    ensure_dir(args.output_dir)
    tts_cache = args.tts_cache or os.path.join(args.output_dir, "tts_cache")
    ensure_dir(tts_cache)

    a_cfg = make_audio_config(args)
    v_cfg = make_visual_config(args)

    records = load_jsonl(args.manifest)
    tasks = [(build_task(r, args.output_dir), a_cfg, v_cfg, tts_cache) for r in records]
    print(f"[multimodal] {len(tasks)} videos | output -> {args.output_dir}")

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
            "audio_target": task["audio_target"],
            "visual_target": task["visual_target"],
            "output": result["output"],
            "speech_wav": result.get("speech_wav"),
            "exp_type": "multimodal_typography",
            "aligned": task["audio_target"] == task["visual_target"],
            "voice": a_cfg.voice,
            "gain": a_cfg.gain,
            "position": v_cfg.position,
            "source_record": task["meta"],
        })

    out_anno = args.annotations or os.path.join(args.output_dir, "annotations_multimodal.jsonl")
    save_jsonl(annotations, out_anno)
    print(f"[multimodal] wrote {len(annotations)} annotations -> {out_anno}")
    if failures:
        print(f"[multimodal] {len(failures)} failures")
        for f in failures[:10]:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
