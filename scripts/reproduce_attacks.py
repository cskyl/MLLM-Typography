#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproduce the paper's attacked videos from a manifest + a local clip pool.

Reads an ``attacks_*.jsonl`` manifest and applies the corresponding attack to
each clip with the bundled ``typography`` library. Each manifest row carries the
*data* of the attack (what is injected: ``spoken_text`` / ``overlay_text`` and
the target); the *hyperparameters* (voice, gain, etc.) come from CLI flags whose
defaults match the MMA-Bench audio recipe. This keeps the released manifests
small — the exact hyperparameters are documented in each benchmark README.

Examples
--------
    # MMA-Bench audio typography (defaults already match the paper recipe)
    python reproduce_attacks.py --attack audio \
        --manifest ../benchmarks/mma_bench/attacks_audio.jsonl \
        --clips ../clips --out-dir ../attacked/mma_audio

    # WorldSense audio attack (non-default hyperparameters)
    python reproduce_attacks.py --attack audio \
        --manifest ../benchmarks/worldsense/attacks_audio.jsonl \
        --clips ../clips --out-dir ../attacked/worldsense_audio \
        --gain 2.0 --leading-silence 1.0 --no-compress --max-repeat 1000

``--clips`` points at source clips laid out so each path matches its ``clip_id``
(``<clips>/<clip_id>.mp4``). Any clip not present is skipped, so a partial pool
still works. A manifest row may also embed a ``params`` dict, which overrides the
CLI flags for that row (useful for hand-written multi-setting manifests).
"""

import argparse
import json
import os

import _common  # noqa: F401  (puts the bundled `typography` package on sys.path)
from typography.audio import AudioAttackConfig, inject_audio_typography
from typography.multimodal import inject_multimodal_typography
from typography.utils import ensure_dir, save_jsonl
from typography.visual import VisualAttackConfig, inject_visual_typography


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def audio_cfg_from_args(args):
    """Build an audio config from CLI flags (defaults = MMA-Bench recipe)."""
    return AudioAttackConfig(
        voice=args.voice,
        gain=args.gain,
        leading_silence=args.leading_silence,
        loudnorm=not args.no_loudnorm,
        repeat_to_duration=True,
        max_repeat=args.max_repeat,
        compress=not args.no_compress,
        compress_threshold_db=args.compress_threshold_db,
        compress_ratio=args.compress_ratio,
        video_codec="libx264",
    )


def audio_cfg(p):
    # For manifests that still embed a per-row ``params`` dict; .get() keeps it
    # tolerant (e.g. MMA-Bench enables compression, WorldSense sets compress=False).
    return AudioAttackConfig(
        voice=p.get("tts_voice", "en-US-JennyNeural"),
        gain=p.get("speech_gain", 1.0),
        leading_silence=p.get("speech_leading_silence_sec", 0.3),
        loudnorm=p.get("loudnorm", True),
        repeat_to_duration=p.get("repeat_to_duration", True),
        max_repeat=p.get("max_repeat", 20),
        compress=p.get("compress", True),
        compress_threshold_db=p.get("compress_threshold_db", -10.0),
        compress_ratio=p.get("compress_ratio", 4.0),
        video_codec="libx264",
    )


def visual_cfg(p):
    return VisualAttackConfig(
        font_scale=p.get("font_scale", 1.5),
        thickness=p.get("thickness", 3),
        color=tuple(p.get("color", (255, 255, 255))),
        bg_color=tuple(p.get("bg_color", (0, 0, 0))),
        bg_alpha=p.get("bg_alpha", 0.4),
        position=p.get("position", "center"),
        duration_mode=p.get("duration_mode", "full"),
    )


def clip_path(clips_root, clip_id):
    return os.path.join(clips_root, clip_id + ".mp4")


def parse_args():
    here = os.path.dirname(os.path.abspath(__file__))
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--attack", required=True, choices=["audio", "visual", "multimodal"])
    p.add_argument("--manifest", required=True)
    p.add_argument("--clips", default=os.path.join(here, "..", "clips"))
    p.add_argument("--out-dir", required=True)
    p.add_argument("--limit", type=int, default=None)
    # Audio hyperparameters (defaults = MMA-Bench audio recipe). Override for
    # other settings, e.g. WorldSense uses --gain 2.0 --leading-silence 1.0 --no-compress.
    p.add_argument("--voice", default="en-US-JennyNeural")
    p.add_argument("--gain", type=float, default=1.0)
    p.add_argument("--leading-silence", type=float, default=0.3)
    p.add_argument("--max-repeat", type=int, default=20)
    p.add_argument("--no-loudnorm", action="store_true")
    p.add_argument("--no-compress", action="store_true")
    p.add_argument("--compress-threshold-db", type=float, default=-10.0)
    p.add_argument("--compress-ratio", type=float, default=4.0)
    return p.parse_args()


def main():
    args = parse_args()
    out_dir = os.path.abspath(args.out_dir)
    ensure_dir(out_dir)
    tts_cache = os.path.join(out_dir, "tts_cache")
    ensure_dir(tts_cache)

    rows = list(load_jsonl(args.manifest))
    if args.limit:
        rows = rows[: args.limit]

    # Hyperparameters come from CLI flags; a per-row "params" dict, if present,
    # overrides them for that row.
    cli_audio = audio_cfg_from_args(args)

    annotations, n_ok, n_missing = [], 0, 0
    for i, row in enumerate(rows, 1):
        clip_id = row["clip_id"]
        src = clip_path(args.clips, clip_id)
        if not os.path.isfile(src):
            n_missing += 1
            continue

        # Mirror the clip_id layout under out_dir: "class/id" -> class subdir,
        # a flat "id" (e.g. WorldSense) writes straight into out_dir.
        sub = os.path.dirname(clip_id)
        stem = os.path.basename(clip_id)
        out_cls = os.path.join(out_dir, sub) if sub else out_dir
        ensure_dir(out_cls)

        params = row.get("params")  # optional per-row override
        try:
            if args.attack == "audio":
                a_cfg = audio_cfg(params) if params else cli_audio
                out = os.path.join(out_cls, f"{stem}_audio_{row['audio_target']}.mp4")
                inject_audio_typography(
                    video_in=src, target_text=row["spoken_text"], video_out=out,
                    tts_cache_dir=tts_cache, config=a_cfg,
                )
            elif args.attack == "visual":
                v_cfg = visual_cfg(params) if params else VisualAttackConfig()
                out = os.path.join(out_cls, f"{stem}_visual_{row['visual_target']}.mp4")
                inject_visual_typography(
                    video_in=src, target_text=row["overlay_text"], video_out=out,
                    config=v_cfg,
                )
            else:  # multimodal (aligned or conflicting — both have audio+visual targets)
                a_cfg = audio_cfg(params["audio"]) if params else cli_audio
                v_cfg = visual_cfg(params["visual"]) if params else VisualAttackConfig()
                out = os.path.join(out_cls, f"{stem}_mm_{row['audio_target']}_{row['visual_target']}.mp4")
                inject_multimodal_typography(
                    video_in=src, audio_text=row["spoken_text"], visual_text=row["overlay_text"],
                    video_out=out, tts_cache_dir=tts_cache,
                    audio_config=a_cfg, visual_config=v_cfg,
                )
            ann = dict(row)
            ann["attacked_video"] = os.path.abspath(out)
            annotations.append(ann)
            n_ok += 1
            print(f"[{i}/{len(rows)}] OK {clip_id}")
        except Exception as exc:
            print(f"[{i}/{len(rows)}] ERROR {clip_id}: {exc!r}")

    save_jsonl(annotations, os.path.join(out_dir, "annotations.jsonl"))
    print(f"\nDone. attacked={n_ok} missing_clip={n_missing}")
    print(f"Output: {out_dir}")


if __name__ == "__main__":
    main()
