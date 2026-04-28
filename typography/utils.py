"""ffmpeg / ffprobe helpers and small IO utilities."""

import json
import os
import subprocess
from pathlib import Path
from typing import Iterable, Optional, Tuple


VIDEO_EXTS = (".mp4", ".mkv", ".avi", ".webm", ".mov")


def is_video_file(name: str) -> bool:
    return name.lower().endswith(VIDEO_EXTS)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def run(cmd: str, capture: bool = False) -> Tuple[int, str, str]:
    if capture:
        proc = subprocess.run(
            cmd, shell=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return proc.returncode, proc.stdout, proc.stderr
    proc = subprocess.run(cmd, shell=True)
    return proc.returncode, "", ""


def run_checked(cmd: str) -> None:
    rc, _, err = run(cmd, capture=True)
    if rc != 0:
        raise RuntimeError(f"command failed (rc={rc}): {cmd}\n{err.strip()}")


def get_duration(path: str) -> float:
    cmd = (
        f'ffprobe -v error -show_entries format=duration '
        f'-of default=noprint_wrappers=1:nokey=1 "{path}"'
    )
    out = subprocess.check_output(cmd, shell=True, text=True).strip()
    return float(out)


def load_jsonl(path: str) -> list:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def save_jsonl(rows: Iterable[dict], path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        ensure_dir(parent)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def derive_output_path(
    video_in: str, output_dir: str, target: str, suffix: str = "attack"
) -> str:
    stem = Path(video_in).stem
    safe_target = target.strip().replace(" ", "_").replace("/", "_")[:64]
    return os.path.join(output_dir, f"{stem}_{suffix}_{safe_target}.mp4")


def copy_baseline(video_in: str, video_out: str, reencode: bool = False) -> None:
    """Make a baseline copy of the input video. Re-encode if needed for downstream tooling."""
    ensure_dir(os.path.dirname(video_out) or ".")
    if reencode:
        cmd = f'ffmpeg -y -i "{video_in}" -c:v libx264 -c:a aac "{video_out}"'
    else:
        cmd = f'ffmpeg -y -i "{video_in}" -c:v copy -c:a copy "{video_out}"'
    run_checked(cmd)


def collect_videos_by_class(source_root: str) -> dict:
    """Return {class_name: [video_path, ...]} for a class-folder dataset layout."""
    classes = sorted(
        d for d in os.listdir(source_root)
        if os.path.isdir(os.path.join(source_root, d))
    )
    return {
        c: sorted(
            os.path.join(source_root, c, f)
            for f in os.listdir(os.path.join(source_root, c))
            if is_video_file(f)
        )
        for c in classes
    }


def safe_remove(path: Optional[str]) -> None:
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass
