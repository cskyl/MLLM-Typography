"""Visual typography: render text as a persistent overlay on every frame."""

import os
import random
from dataclasses import dataclass, field
from typing import Optional, Tuple

import cv2

from .utils import ensure_dir, get_duration, run_checked, safe_remove


@dataclass
class VisualAttackConfig:
    font: int = cv2.FONT_HERSHEY_SIMPLEX
    font_scale: float = 1.5
    thickness: int = 3
    color: Tuple[int, int, int] = (255, 255, 255)
    bg_color: Tuple[int, int, int] = (0, 0, 0)
    bg_alpha: float = 0.4

    # Spatial layout
    position: str = "center"          # center | top | bottom
    moving: bool = False
    speed_min: int = 2
    speed_max: int = 5

    # Temporal layout
    duration_mode: str = "full"       # full | seconds | ratio
    duration_sec: float = 1.0
    duration_ratio: float = 0.35
    start_mode: str = "start"          # start | center | end | random
    start_sec: Optional[float] = None  # if set, overrides start_mode

    # Sparse-frame mode (if frame_indices is given, only those frames carry text)
    frame_indices: Optional[Tuple[int, ...]] = None

    # Encoding
    video_codec: str = "libx264"
    pixel_format: str = "yuv420p"
    audio_codec: str = "copy"


@dataclass
class VisualAttackResult:
    output_video: str
    config: VisualAttackConfig = field(default_factory=VisualAttackConfig)


def _draw_text_with_bg(frame, text: str, x: int, y: int, cfg: VisualAttackConfig):
    (tw, th), _ = cv2.getTextSize(text, cfg.font, cfg.font_scale, cfg.thickness)
    overlay = frame.copy()
    cv2.rectangle(
        overlay,
        (x - 15, y - th - 15),
        (x + tw + 15, y + 15),
        cfg.bg_color,
        -1,
    )
    cv2.addWeighted(overlay, cfg.bg_alpha, frame, 1 - cfg.bg_alpha, 0, frame)
    cv2.putText(
        frame, text, (x, y),
        cfg.font, cfg.font_scale, cfg.color, cfg.thickness, cv2.LINE_AA,
    )
    return frame


def _anchor(text: str, w: int, h: int, cfg: VisualAttackConfig) -> Tuple[int, int]:
    (tw, th), _ = cv2.getTextSize(text, cfg.font, cfg.font_scale, cfg.thickness)
    if cfg.position == "center":
        return (w - tw) // 2, (h + th) // 2
    if cfg.position == "top":
        return (w - tw) // 2, th + 30
    if cfg.position == "bottom":
        return (w - tw) // 2, h - 30
    raise ValueError(f"unknown position: {cfg.position!r}")


def _resolve_frame_window(
    total_frames: int, fps: float, total_duration: float, cfg: VisualAttackConfig
) -> Tuple[int, int]:
    if cfg.duration_mode == "full":
        return 0, total_frames
    if cfg.duration_mode == "ratio":
        seg = max(0.0, min(cfg.duration_ratio, 1.0)) * total_duration
    elif cfg.duration_mode == "seconds":
        seg = max(0.0, min(cfg.duration_sec, total_duration))
    else:
        raise ValueError(f"unknown duration_mode: {cfg.duration_mode!r}")

    seg_frames = int(round(seg * fps))
    seg_frames = max(0, min(seg_frames, total_frames))

    if cfg.start_sec is not None:
        start_frame = int(round(cfg.start_sec * fps))
    elif cfg.start_mode == "start":
        start_frame = 0
    elif cfg.start_mode == "end":
        start_frame = total_frames - seg_frames
    elif cfg.start_mode == "center":
        start_frame = (total_frames - seg_frames) // 2
    elif cfg.start_mode == "random":
        start_frame = random.randint(0, max(0, total_frames - seg_frames))
    else:
        raise ValueError(f"unknown start_mode: {cfg.start_mode!r}")

    start_frame = max(0, min(start_frame, total_frames))
    end_frame = max(start_frame, min(start_frame + seg_frames, total_frames))
    return start_frame, end_frame


def overlay_text_on_video(
    video_in: str,
    text: str,
    video_out: str,
    config: Optional[VisualAttackConfig] = None,
    tmp_dir: Optional[str] = None,
) -> VisualAttackResult:
    """Render ``text`` onto frames of ``video_in`` and re-mux original audio."""
    cfg = config or VisualAttackConfig()
    text = text.replace("_", " ")

    cap = cv2.VideoCapture(video_in)
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video: {video_in}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = get_duration(video_in)

    if cfg.frame_indices is not None:
        active = set(int(i) for i in cfg.frame_indices)
        frame_window = (0, total_frames)
    else:
        start_f, end_f = _resolve_frame_window(total_frames, fps, duration, cfg)
        active = None
        frame_window = (start_f, end_f)

    tmp_dir = tmp_dir or os.path.join(os.path.dirname(video_out) or ".", "_tmp")
    ensure_dir(tmp_dir)
    tmp_video = os.path.join(tmp_dir, os.path.basename(video_out) + ".silent.mp4")

    writer = cv2.VideoWriter(
        tmp_video,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (w, h),
    )

    if cfg.moving:
        x = random.randint(50, max(51, w - 200))
        y = random.randint(50, max(51, h - 50))
        dx = random.choice([-1, 1]) * random.randint(cfg.speed_min, cfg.speed_max)
        dy = random.choice([-1, 1]) * random.randint(cfg.speed_min, cfg.speed_max)
    else:
        x, y = _anchor(text, w, h, cfg)
        dx = dy = 0

    idx = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            should_draw = (
                (active is not None and idx in active)
                or (active is None and frame_window[0] <= idx < frame_window[1])
            )
            if should_draw:
                if cfg.moving:
                    (tw, th), _ = cv2.getTextSize(
                        text, cfg.font, cfg.font_scale, cfg.thickness
                    )
                    if x + tw + 15 >= w or x - 15 <= 0:
                        dx = -dx
                    if y + 15 >= h or y - th - 15 <= 0:
                        dy = -dy
                    x += dx
                    y += dy
                    frame = _draw_text_with_bg(frame, text, x, y, cfg)
                else:
                    frame = _draw_text_with_bg(frame, text, x, y, cfg)
            writer.write(frame)
            idx += 1
    finally:
        cap.release()
        writer.release()

    ensure_dir(os.path.dirname(video_out) or ".")
    cmd = (
        f'ffmpeg -y -i "{tmp_video}" -i "{video_in}" '
        f'-map 0:v -map 1:a? '
        f'-c:v {cfg.video_codec} -pix_fmt {cfg.pixel_format} '
        f'-c:a {cfg.audio_codec} -shortest "{video_out}"'
    )
    try:
        run_checked(cmd)
    finally:
        safe_remove(tmp_video)

    return VisualAttackResult(
        output_video=os.path.abspath(video_out),
        config=cfg,
    )


def inject_visual_typography(
    video_in: str,
    target_text: str,
    video_out: str,
    config: Optional[VisualAttackConfig] = None,
    tmp_dir: Optional[str] = None,
) -> VisualAttackResult:
    return overlay_text_on_video(video_in, target_text, video_out, config, tmp_dir)
