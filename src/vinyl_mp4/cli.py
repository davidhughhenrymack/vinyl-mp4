"""Command-line interface for vinyl-mp4."""

import argparse
import sys
from pathlib import Path

from PIL import Image
from tqdm import tqdm

from vinyl_mp4.audio import (
    load_audio,
    get_metadata,
    compute_energy,
    get_hue_offset,
    AudioEnergy,
)
from vinyl_mp4.encoder import VideoEncoder, check_ffmpeg, FFmpegNotFoundError
from vinyl_mp4.renderer import VinylRenderer, create_label_texture


def render_single_frame(args, input_path: Path) -> int:
    """Render a single frame to PNG for testing.

    Args:
        args: Parsed command-line arguments.
        input_path: Path to input MP3 file.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    frame_time = args.frame

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = (
            input_path.parent / f"{input_path.stem}-frame-{frame_time:.1f}s.png"
        )

    # Load audio for metadata and energy
    print(f"Loading audio: {input_path}")
    samples, sample_rate = load_audio(str(input_path))
    duration = len(samples) / sample_rate

    if frame_time > duration:
        print(
            f"Error: Frame time {frame_time}s exceeds audio duration {duration:.2f}s",
            file=sys.stderr,
        )
        return 1

    # Get metadata
    metadata = get_metadata(str(input_path))
    title = metadata["title"]
    artist = metadata["artist"]
    track_name = args.name if args.name else input_path.stem

    print(f"  Title: {title}")
    print(f"  Artist: {artist}")
    print(f"  Track name: {track_name}")

    # Compute energy for the specific frame
    print("Computing audio energy...")
    energy = compute_energy(samples, sample_rate, args.fps)

    # Get frame index
    frame_idx = int(frame_time * args.fps)
    frame_idx = min(frame_idx, len(energy.total) - 1)

    energy_low = energy.low[frame_idx]
    energy_high = energy.high[frame_idx]
    print(
        f"  Frame {frame_idx} at {frame_time:.2f}s: low={energy_low:.3f}, high={energy_high:.3f}"
    )

    # Get hue offset
    hue_offset = get_hue_offset(input_path.name)
    print(f"  Hue offset: {hue_offset:.3f}")

    # Initialize renderer
    print(f"Initializing renderer ({args.width}x{args.height})...")
    renderer = VinylRenderer(args.width, args.height)

    # Create and set label texture
    label_img = create_label_texture(title, artist, track_name=track_name)
    renderer.set_label_texture(label_img)

    # Render frame
    print(f"Rendering frame at t={frame_time:.2f}s...")
    frame_data = renderer.render_frame(frame_time, energy_low, energy_high, hue_offset)

    # Convert to PIL Image and save
    img = Image.frombytes("RGBA", (args.width, args.height), frame_data)
    img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)  # OpenGL is upside down
    img.save(output_path)

    renderer.release()

    print(f"Done! Frame saved to: {output_path}")
    return 0


def main() -> int:
    """Main entry point for vinyl-mp4 CLI.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    parser = argparse.ArgumentParser(
        prog="vinyl-mp4",
        description="Convert MP3 files to MP4 videos with audio-reactive vinyl visualization",
    )

    parser.add_argument(
        "input",
        help="Input MP3 file",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output file (MP4 for video, PNG for --frame)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=3840,
        help="Output video width (default: 3840)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=2160,
        help="Output video height (default: 2160)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=60,
        help="Output video frame rate (default: 60)",
    )
    parser.add_argument(
        "--limit",
        type=float,
        default=None,
        help="Limit output to first N seconds of audio",
    )
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="Track name to display on vinyl (default: filename without extension)",
    )
    parser.add_argument(
        "--frame",
        type=float,
        default=None,
        help="Render a single frame at this time (seconds) to PNG instead of video",
    )

    args = parser.parse_args()

    # Validate input file exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1

    # Single frame mode - no FFmpeg needed
    if args.frame is not None:
        return render_single_frame(args, input_path)

    # Video mode - check FFmpeg is available
    if not check_ffmpeg():
        print(
            "Error: FFmpeg not found. Please install FFmpeg:\n"
            "  macOS:  brew install ffmpeg\n"
            "  Ubuntu: sudo apt install ffmpeg",
            file=sys.stderr,
        )
        return 1

    # Determine output path (add limit suffix if limit is specified and no explicit output)
    if args.output:
        output_path = Path(args.output)
    elif args.limit is not None:
        # Add limit to filename: "song.mp3" -> "song-30s.mp4"
        output_path = input_path.parent / f"{input_path.stem}-{int(args.limit)}s.mp4"
    else:
        output_path = input_path.with_suffix(".mp4")

    try:
        # Process the audio
        print(f"Loading audio: {input_path}")
        samples, sample_rate = load_audio(str(input_path))
        full_duration = len(samples) / sample_rate

        print(f"  Full duration: {full_duration:.2f}s")
        print(f"  Sample rate: {sample_rate}Hz")

        # Apply limit if specified
        if args.limit is not None and args.limit < full_duration:
            limit_samples = int(args.limit * sample_rate)
            samples = samples[:limit_samples]
            duration = args.limit
            print(f"  Limited to: {duration:.2f}s")
        else:
            duration = full_duration

        # Get metadata
        metadata = get_metadata(str(input_path))
        title = metadata["title"]
        artist = metadata["artist"]
        print(f"  Title: {title}")
        print(f"  Artist: {artist}")

        # Determine track name for display
        track_name = args.name if args.name else input_path.stem
        print(f"  Track name: {track_name}")

        # Compute energy (split into frequency bands)
        print("Computing audio energy...")
        energy = compute_energy(samples, sample_rate, args.fps)
        num_frames = len(energy.total)
        print(f"  Frames to render: {num_frames}")

        # Get hue offset from filename
        hue_offset = get_hue_offset(input_path.name)
        print(f"  Hue offset: {hue_offset:.3f}")

        # Initialize renderer
        print(f"Initializing renderer ({args.width}x{args.height})...")
        renderer = VinylRenderer(args.width, args.height)

        # Create and set label texture with track name for curved text
        label_img = create_label_texture(title, artist, track_name=track_name)
        renderer.set_label_texture(label_img)

        # Initialize encoder
        print("Starting video encoder...")
        encoder = VideoEncoder(
            output_path=str(output_path),
            audio_path=str(input_path),
            width=args.width,
            height=args.height,
            fps=args.fps,
            duration_limit=args.limit,
        )

        # Render frames with progress bar
        with tqdm(
            total=num_frames,
            desc="Rendering",
            unit="frame",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        ) as pbar:
            for frame_idx in range(num_frames):
                time = frame_idx / args.fps
                energy_low = energy.low[frame_idx]
                energy_high = energy.high[frame_idx]

                # Render frame with frequency band energies
                frame_data = renderer.render_frame(
                    time, energy_low, energy_high, hue_offset
                )

                # Write to encoder
                encoder.write_frame(frame_data)

                pbar.update(1)

        # Finish encoding
        print("Finalizing video...")
        encoder.finish()

        # Cleanup
        renderer.release()

        print(f"Done! Output saved to: {output_path}")
        return 0

    except FFmpegNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
