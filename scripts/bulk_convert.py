"""
Bulk conversion helper for vinyl-mp4.

What it does:
- Lists MP3s in a media directory
- Queues them for conversion
- Converts up to N in parallel (default: 4)

Run (recommended):
  uv run python scripts/bulk_convert.py --limit 10
"""

from __future__ import annotations

import argparse
import collections
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tqdm import tqdm


@dataclass(frozen=True)
class Job:
    mp3_path: Path
    output_path: Optional[Path]
    limit: Optional[float]
    extra_args: tuple[str, ...] = ()


@dataclass(frozen=True)
class JobResult:
    job: Job
    returncode: int
    stderr_tail: str
    last_percent: Optional[int]


def _build_output_path(
    output_dir: Path, mp3_path: Path, limit: Optional[float]
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = ""
    if limit is not None:
        # Keep consistent with CLI default naming: "-{int(limit)}s"
        suffix = f"-{int(limit)}s"
    return output_dir / f"{mp3_path.stem}{suffix}.mp4"


def _run_job(job: Job) -> JobResult:
    raise RuntimeError(
        "_run_job is unused; jobs are managed with Popen for live progress."
    )


def _job_cmd(job: Job) -> list[str]:
    cmd = [sys.executable, "-m", "vinyl_mp4", str(job.mp3_path)]
    cmd += list(job.extra_args)
    if job.output_path is not None:
        cmd += ["-o", str(job.output_path)]
    if job.limit is not None:
        cmd += ["--limit", str(job.limit)]
    return cmd


def _format_running(names: list[str], max_chars: int = 60) -> str:
    # Show a compact list of currently running jobs.
    parts: list[str] = []
    used = 0
    for n in names:
        item = n
        if parts:
            item = ", " + item
        if used + len(item) > max_chars:
            if parts:
                parts.append(", …")
            else:
                parts.append("…")
            break
        parts.append(item)
        used += len(item)
    return "".join(parts) if parts else "-"


def _extract_latest_percent(text: str) -> Optional[int]:
    # tqdm looks like: "Rendering:  18%|█▊        | ..."
    marker = "%|"
    idx = text.rfind(marker)
    if idx == -1:
        return None
    j = idx - 1
    while j >= 0 and text[j].isdigit():
        j -= 1
    num = text[j + 1 : idx]
    if not num:
        return None
    try:
        p = int(num)
    except ValueError:
        return None
    if 0 <= p <= 100:
        return p
    return None


@dataclass
class _Running:
    proc: subprocess.Popen[bytes]
    job: Job
    started_at: float
    stderr_tail: collections.deque[str]
    last_percent: Optional[int]
    reader: threading.Thread


def _stderr_reader(r: _Running) -> None:
    # Read tqdm output from stderr continuously, track last percent,
    # and keep a small tail for failures.
    if r.proc.stderr is None:
        return

    buf = ""
    while True:
        chunk = r.proc.stderr.read(4096)
        if not chunk:
            break

        s = chunk.decode("utf-8", errors="replace")
        if not s:
            continue

        latest = _extract_latest_percent(s)
        if latest is not None:
            r.last_percent = latest

        buf += s
        if "\r" in buf:
            buf = buf.replace("\r", "\n")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            latest_line = _extract_latest_percent(line)
            if latest_line is not None:
                r.last_percent = latest_line
            r.stderr_tail.append(line)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="bulk_convert",
        description="Bulk convert MP3s in a directory using vinyl-mp4 (max 4 in parallel).",
    )
    parser.add_argument(
        "--media-dir",
        type=Path,
        default=Path("media"),
        help="Directory containing MP3 files (default: ./media)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional output directory for MP4s (default: next to each MP3 / CLI default).",
    )
    parser.add_argument(
        "--limit",
        type=float,
        default=None,
        help="Limit output to first N seconds (recommended for testing).",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=2,
        help="Max conversions in parallel (default: 4).",
    )
    # Resolution presets (match vinyl-mp4 CLI)
    res_group = parser.add_mutually_exclusive_group()
    res_group.add_argument(
        "--480p",
        action="store_true",
        dest="res_480p",
        help="Output at 480p (854x480)",
    )
    res_group.add_argument(
        "--720p",
        action="store_true",
        dest="res_720p",
        help="Output at 720p (1280x720)",
    )
    res_group.add_argument(
        "--1080p",
        action="store_true",
        dest="res_1080p",
        help="Output at 1080p (1920x1080) [default]",
    )
    res_group.add_argument(
        "--1440p",
        action="store_true",
        dest="res_1440p",
        help="Output at 1440p/2K (2560x1440)",
    )
    res_group.add_argument(
        "--4k",
        action="store_true",
        dest="res_4k",
        help="Output at 4K (3840x2160)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List queued jobs and exit.",
    )

    args = parser.parse_args()

    media_dir: Path = args.media_dir
    if not media_dir.exists() or not media_dir.is_dir():
        raise SystemExit(f"media dir not found: {media_dir}")

    mp3s = sorted(
        p for p in media_dir.iterdir() if p.is_file() and p.suffix.lower() == ".mp3"
    )
    if not mp3s:
        print(f"No mp3 files found in: {media_dir}")
        return 0

    max_parallel = args.max_parallel
    if max_parallel < 1:
        raise SystemExit("--max-parallel must be >= 1")
    if max_parallel > 4:
        # Hard cap to what you asked for.
        max_parallel = 4

    # Pass-through args shared by all jobs
    extra_args: list[str] = []
    if getattr(args, "res_480p", False):
        extra_args.append("--480p")
    elif getattr(args, "res_720p", False):
        extra_args.append("--720p")
    elif getattr(args, "res_1080p", False):
        extra_args.append("--1080p")
    elif getattr(args, "res_1440p", False):
        extra_args.append("--1440p")
    elif getattr(args, "res_4k", False):
        extra_args.append("--4k")

    jobs: list[Job] = []
    skipped = 0
    for mp3 in mp3s:
        # Determine expected output path
        if args.output_dir is not None:
            out_path = _build_output_path(args.output_dir, mp3, args.limit)
        else:
            # CLI default: output next to the MP3
            suffix = ""
            if args.limit is not None:
                suffix = f"-{int(args.limit)}s"
            out_path = mp3.parent / f"{mp3.stem}{suffix}.mp4"

        # Skip if output already exists
        if out_path.exists():
            skipped += 1
            continue

        jobs.append(
            Job(
                mp3_path=mp3,
                output_path=out_path if args.output_dir is not None else None,
                limit=args.limit,
                extra_args=tuple(extra_args),
            )
        )

    if skipped:
        print(f"Skipping {skipped} file(s) with existing MP4 output.")

    if args.dry_run:
        for j in jobs:
            out = str(j.output_path) if j.output_path else "(cli default рядом с mp3)"
            limit = j.limit if j.limit is not None else "(no limit)"
            print(f"- {j.mp3_path} -> {out}  limit={limit}")
        return 0

    failures: list[JobResult] = []
    pending = list(jobs)

    # Keep stdout quiet so progress stays readable. On failure, include stderr tail.
    running: list[_Running] = []
    total = len(pending)

    with tqdm(total=total, desc="Converting", unit="file", mininterval=0.2) as pbar:
        while pending or running:
            # Start more work (up to max_parallel).
            while pending and len(running) < max_parallel:
                job = pending.pop(0)
                proc: subprocess.Popen[bytes] = subprocess.Popen(
                    _job_cmd(job),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=False,
                )
                r = _Running(
                    proc=proc,
                    job=job,
                    started_at=time.time(),
                    stderr_tail=collections.deque(maxlen=25),
                    last_percent=0,
                    reader=threading.Thread(target=lambda: None),
                )
                r.reader = threading.Thread(
                    target=_stderr_reader, args=(r,), daemon=True
                )
                r.reader.start()
                running.append(r)

            # Update live status even when nothing finishes yet.
            running_names: list[str] = []
            for r in running:
                pct = r.last_percent
                if pct is None:
                    running_names.append(f"{r.job.mp3_path.name} ?%")
                else:
                    running_names.append(f"{r.job.mp3_path.name} {pct}%")
            pbar.set_postfix_str(f"running: {_format_running(running_names)}")
            pbar.refresh()

            # Poll running processes.
            still_running: list[_Running] = []
            for r in running:
                rc = r.proc.poll()
                if rc is None:
                    still_running.append(r)
                    continue

                # Give stderr reader a moment to drain the pipe.
                r.reader.join(timeout=2)
                stderr_tail = "\n".join(list(r.stderr_tail))

                pbar.update(1)
                name = r.job.mp3_path.name
                pct = r.last_percent
                pct_txt = f"{pct}%" if pct is not None else "?%"
                if rc == 0:
                    tqdm.write(f"OK   {name} ({pct_txt})")
                else:
                    failures.append(
                        JobResult(
                            job=r.job,
                            returncode=rc,
                            stderr_tail=stderr_tail,
                            last_percent=pct,
                        )
                    )
                    tqdm.write(f"FAIL {name} ({pct_txt}, exit={rc})")

            running = still_running
            if pending or running:
                time.sleep(0.5)

    if failures:
        print("\nFailures:")
        for res in failures:
            print(f"\n- {res.job.mp3_path} (exit={res.returncode})")
            if res.last_percent is not None:
                print(f"  last progress: {res.last_percent}%")
            if res.stderr_tail:
                print(res.stderr_tail)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
