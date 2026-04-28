#!/usr/bin/env python3
"""Build attack manifests from a class-folder dataset.

Given a directory of the form

    source_root/
        cat/
            clip_001.mp4
            clip_002.mp4
        dog/
            ...

this writes a jsonl manifest where each row is a (video, target) pair, with
``target`` drawn at random from the *other* classes — the standard
classification setup used in the Multi-Modal Typography paper.

For the multimodal "conflicting" setting use ``--mode multimodal-conflict``,
which samples *two* distinct other-class targets per video.
"""

import argparse
import json
import os
import random

import _common  # noqa: F401
from typography.utils import collect_videos_by_class, ensure_dir


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source-root", required=True)
    p.add_argument("--output", required=True, help="Manifest jsonl to write.")
    p.add_argument(
        "--mode",
        choices=["single", "multimodal-aligned", "multimodal-conflict"],
        default="single",
    )
    p.add_argument(
        "--target",
        default=None,
        help=(
            "Optional fixed target string. If set, every video is paired with "
            "this target instead of a random other class."
        ),
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--include-true-class",
        action="store_true",
        help="Include the original class label as a 'true_class' field.",
    )
    return p.parse_args()


def main():
    args = parse_args()
    random.seed(args.seed)

    classes_to_videos = collect_videos_by_class(args.source_root)
    classes = sorted(classes_to_videos)
    if not classes:
        raise SystemExit(f"no class folders under {args.source_root}")

    rows = []
    for cls in classes:
        for video in classes_to_videos[cls]:
            others = [c for c in classes if c != cls]
            if not others:
                raise SystemExit("need at least 2 classes to sample a wrong target")

            if args.mode == "single":
                target = args.target or random.choice(others)
                row = {"video": video, "target": target}
            elif args.mode == "multimodal-aligned":
                target = args.target or random.choice(others)
                row = {"video": video, "audio_target": target, "visual_target": target}
            else:  # multimodal-conflict
                if len(others) < 2:
                    raise SystemExit("need >=3 classes for conflicting attacks")
                a_t, v_t = random.sample(others, 2)
                row = {"video": video, "audio_target": a_t, "visual_target": v_t}

            if args.include_true_class:
                row["true_class"] = cls
            rows.append(row)

    ensure_dir(os.path.dirname(os.path.abspath(args.output)) or ".")
    with open(args.output, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"[manifest] wrote {len(rows)} rows ({len(classes)} classes) -> {args.output}")


if __name__ == "__main__":
    main()
