#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a source-provenance manifest for *your own* AudioSet-derived clips.

This is the generic counterpart of ``build_paper_manifests.py``. If you have a
class-folder dataset of AudioSet clips and want to release links + timestamps
instead of the videos, point this at your data and the AudioSet segment CSVs.

    python build_provenance.py \
        --source-root /path/to/dataset \
        --audioset-csv balanced_train_segments.csv unbalanced_train_segments.csv eval_segments.csv \
        --output sources.jsonl

Expected layout::

    source-root/<class>/<id>.mp4

``<id>`` should be the YouTube id, optionally with AudioSet's leading ``Y``
(e.g. ``Yabcdefghijk`` -> ``abcdefghijk``). Get the official segment CSVs from
https://research.google.com/audioset/download.html
"""

import argparse
import csv
import json
import os


def ytid_from_stem(stem):
    return stem[1:] if stem.startswith("Y") and len(stem) == 12 else stem


def load_audioset(csv_paths):
    seg = {}
    for path in csv_paths:
        with open(path) as fh:
            for line in fh:
                if line.startswith("#"):
                    continue
                parts = line.rstrip("\n").split(", ", 3)
                if len(parts) < 3:
                    continue
                seg[parts[0].strip()] = (
                    float(parts[1]), float(parts[2]),
                    parts[3].strip().strip('"') if len(parts) == 4 else "",
                )
    return seg


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source-root", required=True)
    p.add_argument("--audioset-csv", nargs="+", required=True)
    p.add_argument("--output", required=True, help="Output .jsonl (a .csv is written alongside).")
    return p.parse_args()


def main():
    args = parse_args()
    seg = load_audioset(args.audioset_csv)

    classes = sorted(
        d for d in os.listdir(args.source_root)
        if os.path.isdir(os.path.join(args.source_root, d))
    )
    rows, missing = [], 0
    for cls in classes:
        cdir = os.path.join(args.source_root, cls)
        for fn in sorted(os.listdir(cdir)):
            if not fn.lower().endswith((".mp4", ".mkv", ".webm", ".avi")):
                continue
            ytid = ytid_from_stem(os.path.splitext(fn)[0])
            if ytid not in seg:
                missing += 1
                continue
            start, end, labels = seg[ytid]
            rows.append({
                "clip_id": f"{cls}/{ytid}",
                "youtube_id": ytid,
                "class": cls,
                "start_seconds": start,
                "end_seconds": end,
                "youtube_url": f"https://www.youtube.com/watch?v={ytid}",
                "youtube_url_at_start": f"https://www.youtube.com/watch?v={ytid}&t={int(start)}s",
                "audioset_label_ids": labels,
            })

    with open(args.output, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    csv_path = os.path.splitext(args.output)[0] + ".csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)

    print(f"[provenance] {len(rows)} clips, {len(classes)} classes, {missing} unmatched")
    print(f"  -> {args.output}\n  -> {csv_path}")


if __name__ == "__main__":
    main()
