#!/usr/bin/env python3
"""Generate visual-typography attacks from a (video, target) manifest."""

import argparse
import os

import _common  # noqa: F401
from typography.utils import (
    derive_output_path,
    ensure_dir,
    load_jsonl,
    save_jsonl,
)
from typography.visual import VisualAttackConfig, inject_visual_typography


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--annotations", default=None)
    p.add_argument("--num-proc", type=int, default=8)

    p.add_argument("--position", choices=["center", "top", "bottom"], default="center")
    p.add_argument("--moving", action="store_true",
                   help="Bouncing-text overlay instead of a static anchor.")
    p.add_argument("--font-scale", type=float, default=1.5)
    p.add_argument("--thickness", type=int, default=3)

    p.add_argument("--duration-mode", choices=["full", "seconds", "ratio"], default="full")
    p.add_argument("--duration-sec", type=float, default=1.0)
    p.add_argument("--duration-ratio", type=float, default=0.35)
    p.add_argument("--start-mode", choices=["start", "center", "end", "random"], default="start")
    p.add_argument("--start-sec", type=float, default=None)
    p.add_argument("--frame-indices", default=None,
                   help="Comma-separated frame indices (sparse-frame mode).")
    return p.parse_args()


def make_config(args) -> VisualAttackConfig:
    frame_indices = None
    if args.frame_indices:
        frame_indices = tuple(int(x) for x in args.frame_indices.split(","))
    return VisualAttackConfig(
        position=args.position,
        moving=args.moving,
        font_scale=args.font_scale,
        thickness=args.thickness,
        duration_mode=args.duration_mode,
        duration_sec=args.duration_sec,
        duration_ratio=args.duration_ratio,
        start_mode=args.start_mode,
        start_sec=args.start_sec,
        frame_indices=frame_indices,
    )


def build_task(record: dict, output_dir: str) -> dict:
    video = record["video"]
    target = record["target"]
    output = record.get("output") or derive_output_path(video, output_dir, target, "visual")
    return {"video": video, "target": target, "output": output, "meta": record}


def worker(task_and_cfg):
    task, cfg = task_and_cfg
    if os.path.isfile(task["output"]):
        return {"output": task["output"], "skipped": True, "task": task}
    result = inject_visual_typography(
        video_in=task["video"],
        target_text=task["target"],
        video_out=task["output"],
        config=cfg,
    )
    return {"output": result.output_video, "task": task}


def main():
    args = parse_args()
    ensure_dir(args.output_dir)
    cfg = make_config(args)

    records = load_jsonl(args.manifest)
    tasks = [(build_task(r, args.output_dir), cfg) for r in records]
    print(f"[visual] {len(tasks)} videos | output -> {args.output_dir}")

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
            "exp_type": "visual_typography",
            "position": cfg.position,
            "moving": cfg.moving,
            "duration_mode": cfg.duration_mode,
            "start_mode": cfg.start_mode,
            "source_record": task["meta"],
        })

    out_anno = args.annotations or os.path.join(args.output_dir, "annotations_visual.jsonl")
    save_jsonl(annotations, out_anno)
    print(f"[visual] wrote {len(annotations)} annotations -> {out_anno}")
    if failures:
        print(f"[visual] {len(failures)} failures")
        for f in failures[:10]:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
