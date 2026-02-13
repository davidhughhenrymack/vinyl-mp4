#!/usr/bin/env -S uv run python
"""Export ALS per-track signals to CSV and print analysis (line-to-track mapping, activity)."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

# Add src to path when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vinyl_mp4.ableton_ingestion import load_ableton_signals


LINE_COUNT = 24


def line_to_track_index(line_i: int, track_count: int) -> int:
    """Match shader: signalIndex = (i * trackCount) / lineCount."""
    if track_count <= 0:
        return 0
    idx = (line_i * track_count) // LINE_COUNT
    return min(idx, track_count - 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export ALS track signals to CSV and analyze")
    parser.add_argument("als", type=Path, help="Path to .als file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Output CSV path (e.g. media/als_signals.csv)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Duration in seconds (default: from --audio or 300)",
    )
    parser.add_argument(
        "--audio",
        type=Path,
        default=None,
        help="Audio file to get duration from (e.g. media/hey.flac)",
    )
    parser.add_argument("--fps", type=int, default=60, help="Frames per second")
    args = parser.parse_args()

    if not args.als.exists():
        print(f"Error: ALS file not found: {args.als}", file=sys.stderr)
        return 1

    duration_sec: float
    if args.duration is not None:
        duration_sec = args.duration
    elif args.audio is not None and args.audio.exists():
        from vinyl_mp4.audio import load_audio
        samples, sample_rate = load_audio(str(args.audio))
        duration_sec = len(samples) / sample_rate
        print(f"Duration from audio: {duration_sec:.2f}s")
    else:
        duration_sec = 300.0
        print(f"Using default duration: {duration_sec:.1f}s")

    num_frames = max(1, int(duration_sec * args.fps))
    signals = load_ableton_signals(
        str(args.als),
        fps=args.fps,
        num_frames=num_frames,
        timeline_start_seconds=0.0,
    )

    track_count = len(signals.track_names)
    # Build CSV header: frame_index, time_sec, then one column per track (safe names)
    safe_names = [n.replace(",", "_").replace('"', "") for n in signals.track_names]
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["frame_index", "time_sec"] + safe_names)
        for frame_idx in range(num_frames):
            t = frame_idx / args.fps
            row = [frame_idx, round(t, 4)] + [
                round(float(signals.track_signals[frame_idx, j]), 6)
                for j in range(track_count)
            ]
            writer.writerow(row)

    print(f"Wrote {signals.track_signals.shape[0]} rows x {track_count + 2} columns to {args.output}")

    # Analysis: per-track activity
    threshold = 0.01
    print("\n--- Per-track activity ---")
    for j, name in enumerate(signals.track_names):
        col = signals.track_signals[:, j]
        nz = (np.abs(col) > threshold).sum()
        frac = nz / len(col) if len(col) else 0
        max_abs = float(np.max(np.abs(col))) if col.size else 0
        mean_when_nz = float(col[np.abs(col) > threshold].mean()) if nz else 0
        print(f"  {name}: non-zero frames {nz}/{len(col)} ({frac:.1%}), max_abs={max_abs:.4f}, mean_when_nz={mean_when_nz:.4f}")

    # Line -> track mapping and "response" summary
    print("\n--- Line -> track mapping (terrain lines 0=back, 23=front) ---")
    for line_i in range(LINE_COUNT):
        t_idx = line_to_track_index(line_i, track_count)
        t_name = signals.track_names[t_idx]
        col = signals.track_signals[:, t_idx]
        nz = (np.abs(col) > threshold).sum()
        frac = nz / len(col) if len(col) else 0
        print(f"  line {line_i:2d} -> track {t_idx} ({t_name}): active {nz}/{len(col)} ({frac:.1%})")

    # Why "most lines never respond": count lines whose track is active in < X% of frames
    pct_5 = sum(1 for i in range(LINE_COUNT) if (np.abs(signals.track_signals[:, line_to_track_index(i, track_count)]) > threshold).mean() < 0.05)
    pct_20 = sum(1 for i in range(LINE_COUNT) if (np.abs(signals.track_signals[:, line_to_track_index(i, track_count)]) > threshold).mean() < 0.20)
    print(f"\n--- Summary ---")
    print(f"  Lines whose track is active in < 5% of frames: {pct_5}/{LINE_COUNT}")
    print(f"  Lines whose track is active in < 20% of frames: {pct_20}/{LINE_COUNT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
