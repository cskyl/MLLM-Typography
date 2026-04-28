"""Shared CLI helpers for the manifest-driven attack scripts."""

import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Callable, Iterable

# Allow running scripts directly without `pip install -e .`
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))


def run_parallel(worker: Callable, tasks: Iterable, num_proc: int):
    """Run ``worker(task)`` for each task and yield (result, error) tuples."""
    if num_proc <= 1:
        for t in tasks:
            yield _safe_call(worker, t)
        return

    with ProcessPoolExecutor(num_proc) as pool:
        futures = [pool.submit(_safe_call, worker, t) for t in tasks]
        for fut in as_completed(futures):
            yield fut.result()


def _safe_call(worker, task):
    try:
        return worker(task), None
    except Exception as exc:  # surface worker errors without killing the pool
        return None, {"task": task, "error": repr(exc)}


def report_failures(failures: list) -> None:
    if not failures:
        print("[done] no failed items")
        return
    print(f"[done] {len(failures)} failed items:")
    for f in failures:
        print(f"  - {f['task']!r}: {f['error']}")
