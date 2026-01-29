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
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tqdm import tqdm


@dataclass(frozen=True)
class Job:
    mp3_path: Path
    output_path: Optional[Path]
    limit: Optional[float]


@dataclass(frozen=True)
class JobResult:
    job: Job
    returncode: int
    stderr_tail: str


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
    cmd = [sys.executable, "-m", "vinyl_mp4", str(job.mp3_path)]
    if job.output_path is not None:
        cmd += ["-o", str(job.output_path)]
    if job.limit is not None:
        cmd += ["--limit", str(job.limit)]

    # Keep stdout quiet so progress stays readable. On failure, return stderr tail.
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stderr = (proc.stderr or "").strip()
    stderr_tail = "\n".join(stderr.splitlines()[-25:]) if stderr else ""
    return JobResult(job=job, returncode=proc.returncode, stderr_tail=stderr_tail)


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
        default=4,
        help="Max conversions in parallel (default: 4).",
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

    jobs: list[Job] = []
    for mp3 in mp3s:
        out_path = None
        if args.output_dir is not None:
            out_path = _build_output_path(args.output_dir, mp3, args.limit)
        jobs.append(Job(mp3_path=mp3, output_path=out_path, limit=args.limit))

    if args.dry_run:
        for j in jobs:
            out = str(j.output_path) if j.output_path else "(cli default рядом с mp3)"
            limit = j.limit if j.limit is not None else "(no limit)"
            print(f"- {j.mp3_path} -> {out}  limit={limit}")
        return 0

    # Queue + run up to max_parallel at once.
    from concurrent.futures import ThreadPoolExecutor, as_completed

    failures: list[JobResult] = []
    with ThreadPoolExecutor(max_workers=max_parallel) as ex:
        futures = [ex.submit(_run_job, j) for j in jobs]
        with tqdm(total=len(futures), desc="Converting", unit="file") as pbar:
            for fut in as_completed(futures):
                res = fut.result()
                pbar.update(1)

                name = res.job.mp3_path.name
                if res.returncode == 0:
                    tqdm.write(f"OK   {name}")
                else:
                    failures.append(res)
                    tqdm.write(f"FAIL {name} (exit={res.returncode})")

    if failures:
        print("\nFailures:")
        for res in failures:
            print(f"\n- {res.job.mp3_path} (exit={res.returncode})")
            if res.stderr_tail:
                print(res.stderr_tail)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
