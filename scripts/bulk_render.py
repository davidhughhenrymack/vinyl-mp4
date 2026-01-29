#!/usr/bin/env python3 -u
"""Bulk render MP3 files to MP4 videos.

Scans the media/ directory for MP3 files without corresponding MP4s
and renders them in parallel (max 4 at once).
"""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm


def get_pending_renders(media_dir: Path) -> list[Path]:
    """Find MP3 files that don't have corresponding MP4s."""
    pending = []
    for mp3_path in sorted(media_dir.glob("*.mp3")):
        mp4_path = mp3_path.with_suffix(".mp4")
        if not mp4_path.exists():
            pending.append(mp3_path)
    return pending


def render_file(mp3_path: Path) -> tuple[Path, bool, str]:
    """Render a single MP3 to MP4. Returns (path, success, message)."""
    mp4_path = mp3_path.with_suffix(".mp4")

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "vinyl_mp4",
                str(mp3_path),
                "-o",
                str(mp4_path),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            return (mp3_path, True, "OK")
        else:
            error = (
                result.stderr.strip().split("\n")[-1]
                if result.stderr
                else "Unknown error"
            )
            return (mp3_path, False, error)
    except Exception as e:
        return (mp3_path, False, str(e))


def main():
    # Find media directory relative to script or use current working directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    media_dir = project_root / "media"

    if not media_dir.exists():
        print(f"Error: Media directory not found: {media_dir}", flush=True)
        sys.exit(1)

    # Get list of files to render
    pending = get_pending_renders(media_dir)

    if not pending:
        print("No MP3 files need rendering.", flush=True)
        print(
            f"  (All MP3s in {media_dir} already have corresponding MP4s)", flush=True
        )
        return

    print(f"Found {len(pending)} MP3 file(s) to render:", flush=True)
    for mp3_path in pending:
        print(f"  - {mp3_path.name}", flush=True)
    print(flush=True)

    # Render in parallel with max 4 workers
    max_workers = 4
    failed = []

    print(f"Starting bulk render (max {max_workers} parallel)...", flush=True)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(render_file, mp3): mp3 for mp3 in pending}

        with tqdm(total=len(pending), unit="file", desc="Rendering") as pbar:
            for future in as_completed(futures):
                mp3_path, success, message = future.result()

                if success:
                    pbar.set_postfix_str(f"✓ {mp3_path.stem}")
                else:
                    pbar.set_postfix_str(f"✗ {mp3_path.stem}")
                    failed.append((mp3_path, message))

                pbar.update(1)

    print(flush=True)
    print(
        f"Completed: {len(pending) - len(failed)}/{len(pending)} successful", flush=True
    )

    if failed:
        print(f"\nFailed renders:", flush=True)
        for mp3_path, error in failed:
            print(f"  - {mp3_path.name}: {error}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
