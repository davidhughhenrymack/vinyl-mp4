"""Command-line interface for vinyl-mp4."""

import argparse
import os
import random
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from tqdm import tqdm

from vinyl_mp4.audio import (
    load_audio,
    get_metadata,
    compute_energy,
    get_hue_offset,
    get_shader_index,
    get_vinyl_scale,
    get_vinyl_offset_x,
    get_contrast,
    AudioEnergy,
)
from vinyl_mp4.ableton_ingestion import (
    load_ableton_signals,
    analyze_als_audio_alignment,
)
from vinyl_mp4.encoder import VideoEncoder, check_ffmpeg, FFmpegNotFoundError
from vinyl_mp4.renderer import VinylRenderer, create_label_texture
from vinyl_mp4.shaders import (
    get_num_shaders,
    get_shader_by_name,
    get_shader_names,
    get_color_names,
    get_hue_from_color,
    SHADER_REGISTRY,
)


def _print_als_track_summary(als_signals) -> None:
    print("  ALS track summary (volume, MIDI notes):")
    for name, volume, note_count in zip(
        als_signals.track_names,
        als_signals.track_volumes,
        als_signals.track_note_counts,
    ):
        print(f"    - {name}: volume={volume:.3f}, notes={note_count}")


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
    print("Computing visualization energy...")
    als_signals = None
    num_frames = max(1, int(duration * args.fps))
    if args.als:
        als_signals = load_ableton_signals(
            args.als,
            fps=args.fps,
            num_frames=num_frames,
            timeline_start_seconds=0.0,
        )
        alignment = analyze_als_audio_alignment(als_signals, samples, sample_rate, args.fps)
        print(
            "  ALS alignment:"
            f" melody~mid corr={alignment.melody_mid_corr:.3f},"
            f" bass~low corr={alignment.bass_low_corr:.3f},"
            f" kick-low={alignment.kick_low_at_onset_mean:.3f} vs global-low={alignment.low_band_global_mean:.3f}"
        )
        print(
            f"  ALS tracks: {len(als_signals.track_names)}, notes: {als_signals.note_count}, tempo: {als_signals.tempo_bpm:.2f} BPM"
        )
        _print_als_track_summary(als_signals)

    if args.no_audio_viz:
        if als_signals is None:
            raise ValueError("--no-audio-viz requires --als")
        energy = AudioEnergy(
            total=(als_signals.melody_energy + als_signals.bass_energy) * 0.5,
            low=als_signals.bass_energy,
            mid=als_signals.melody_energy,
            high=als_signals.transient_energy,
        )
    else:
        energy = compute_energy(samples, sample_rate, args.fps)

    # Get frame index
    frame_idx = int(frame_time * args.fps)
    frame_idx = min(frame_idx, len(energy.total) - 1)

    energy_low = energy.low[frame_idx]
    energy_mid = energy.mid[frame_idx]
    energy_high = energy.high[frame_idx]
    print(
        f"  Frame {frame_idx} at {frame_time:.2f}s: low={energy_low:.3f}, mid={energy_mid:.3f}, high={energy_high:.3f}"
    )

    # Get hue offset (from --color or hash of filename)
    if args.color:
        try:
            hue_offset = get_hue_from_color(args.color)
            print(f"  Color: {args.color} (hue={hue_offset:.3f})")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    else:
        hue_offset = get_hue_offset(input_path.name)
        print(f"  Hue offset: {hue_offset:.3f}")

    # Get shader (from --shader or hash of filename)
    if args.shader:
        try:
            shader_class = get_shader_by_name(args.shader)
            shader_index = SHADER_REGISTRY.index(shader_class)
            print(f"  Shader: {args.shader}")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    else:
        shader_index = get_shader_index(input_path.name, get_num_shaders())
        print(f"  Shader index: {shader_index}")

    # Get vinyl scale and position from filename hash
    vinyl_scale = get_vinyl_scale(input_path.name)
    vinyl_offset_x = get_vinyl_offset_x(input_path.name)
    contrast = get_contrast(input_path.name)
    print(f"  Vinyl scale: {vinyl_scale:.2f}x, offset: {vinyl_offset_x:.2f}")
    print(f"  Contrast: {contrast:.2f}")

    # Initialize renderer
    print(f"Initializing renderer ({args.width}x{args.height})...")
    renderer = VinylRenderer(
        args.width,
        args.height,
        shader_index=shader_index,
        vinyl_scale=vinyl_scale,
        vinyl_offset_x=vinyl_offset_x,
        contrast=contrast,
        show_vinyl=not args.no_vinyl,
        bg_rgb=getattr(args, "bg_rgb", None),
        line_rgb=getattr(args, "line_rgb", None),
    )
    print(f"  Using shader: {renderer.bg_shader.name}")

    # Create and set label texture
    if not args.no_vinyl:
        # Track name shown in bold center, rim text on the rim
        rim_text = args.rim_text if args.rim_text else title
        print(f"  Rim text: {rim_text}")
        label_img = create_label_texture(track_name, artist, track_name=rim_text)
        renderer.set_label_texture(label_img)

    # Set progress for line reveal (single frame uses position within duration)
    renderer.bg_shader.progress = frame_time / duration if duration > 0 else 1.0

    # Render frame
    print(f"Rendering frame at t={frame_time:.2f}s...")
    frame_track_signals = None
    frame_track_onsets = None
    frame_track_pitches = None
    if als_signals is not None and frame_idx < als_signals.track_signals.shape[0]:
        frame_track_signals = als_signals.track_signals[frame_idx].tolist()
        frame_track_onsets = als_signals.track_onsets[frame_idx].tolist()
        frame_track_pitches = list(als_signals.track_pitch_norms)
    if args.no_audio_viz:
        energy_low = energy_mid = energy_high = 0.0
    frame_data = renderer.render_frame(
        frame_time,
        energy_low,
        energy_mid,
        energy_high,
        hue_offset,
        track_signals=frame_track_signals,
        track_onsets=frame_track_onsets,
        track_pitches=frame_track_pitches,
    )

    # Convert to PIL Image and save (RGBA format, flip for OpenGL)
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
        description="Convert audio files to MP4 videos with audio-reactive vinyl visualization",
    )

    parser.add_argument(
        "input",
        help="Input audio file (MP3 or WAV)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output file (MP4 for video, PNG for --frame)",
    )

    # Resolution presets (mutually exclusive)
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
        "--width",
        type=int,
        default=None,
        help="Output video width (default: 1920, overrides resolution presets)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=None,
        help="Output video height (default: 1080, overrides resolution presets)",
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
        "--start",
        type=float,
        default=None,
        help="Start processing from N seconds into the audio (skip beginning)",
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
    parser.add_argument(
        "--shader",
        type=str,
        default=None,
        help=f"Background shader to use (available: {', '.join(get_shader_names())})",
    )
    parser.add_argument(
        "--color",
        type=str,
        default=None,
        help=f"Base color for shader (available: {', '.join(get_color_names())})",
    )
    parser.add_argument(
        "--rim-text",
        type=str,
        default=None,
        help="Text to display around the vinyl rim (default: from audio metadata title)",
    )
    parser.add_argument(
        "--no-vinyl",
        action="store_true",
        default=False,
        help="Hide the vinyl record and render only the background shader",
    )
    parser.add_argument(
        "--als",
        type=str,
        default=None,
        help="Optional Ableton Live Set (.als) to drive additional per-track shader signals",
    )
    parser.add_argument(
        "--no-audio-viz",
        action="store_true",
        default=False,
        help="Use ALS-only visualization inputs (ignore audio frequency energy for shader driving)",
    )
    parser.add_argument(
        "--bg-color",
        type=str,
        default=None,
        help="Background color for terrain shader (e.g. white, black)",
    )
    parser.add_argument(
        "--line-color",
        type=str,
        default=None,
        help="Line color for terrain shader (e.g. gold, golden, red)",
    )

    args = parser.parse_args()

    # Theme RGB for terrain: named colors (only used when --shader terrain / Retro Terrain)
    THEME_COLORS = {
        "white": (1.0, 1.0, 1.0),
        "black": (0.0, 0.0, 0.0),
        "gold": (1.0, 0.84, 0.0),
        "golden": (1.0, 0.84, 0.0),
        "orange": (1.0, 0.5, 0.0),
        "red": (1.0, 0.0, 0.0),
        "green": (0.0, 1.0, 0.0),
        "blue": (0.0, 0.0, 1.0),
    }
    args.bg_rgb = THEME_COLORS.get(args.bg_color.lower()) if args.bg_color else None
    args.line_rgb = THEME_COLORS.get(args.line_color.lower()) if args.line_color else None
    if args.bg_color and args.bg_rgb is None:
        print(f"Error: Unknown --bg-color '{args.bg_color}'", file=sys.stderr)
        return 1
    if args.line_color and args.line_rgb is None:
        print(f"Error: Unknown --line-color '{args.line_color}'", file=sys.stderr)
        return 1

    # Resolve resolution from presets or explicit width/height
    resolution_presets = {
        "res_480p": (854, 480),
        "res_720p": (1280, 720),
        "res_1080p": (1920, 1080),
        "res_1440p": (2560, 1440),
        "res_4k": (3840, 2160),
    }

    # Check if any preset is selected
    selected_preset = None
    for preset, (w, h) in resolution_presets.items():
        if getattr(args, preset, False):
            selected_preset = (w, h)
            break

    # Explicit width/height override presets, presets override defaults
    if args.width is not None and args.height is not None:
        pass  # Use explicit values
    elif args.width is not None or args.height is not None:
        # Partial override - fill in from preset or default
        base_w, base_h = selected_preset or (1920, 1080)
        args.width = args.width or base_w
        args.height = args.height or base_h
    elif selected_preset:
        args.width, args.height = selected_preset
    else:
        # Default to 1080p
        args.width, args.height = 1920, 1080

    # Validate input file exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1

    if args.no_audio_viz and not args.als:
        print(
            "Error: --no-audio-viz requires --als <project.als>",
            file=sys.stderr,
        )
        return 1

    als_path: Path | None = None
    if args.als is not None:
        als_path = Path(args.als)
        if not als_path.exists():
            print(f"Error: ALS file not found: {args.als}", file=sys.stderr)
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

        # Apply start offset if specified
        start_offset = 0.0
        if args.start is not None and args.start > 0:
            start_offset = min(args.start, full_duration)
            start_samples = int(start_offset * sample_rate)
            samples = samples[start_samples:]
            full_duration = len(samples) / sample_rate
            print(f"  Starting from: {start_offset:.2f}s")

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

        # Compute visualization energy
        print("Computing visualization energy...")
        num_frames = max(1, int(duration * args.fps))
        als_signals = None
        if als_path is not None:
            als_signals = load_ableton_signals(
                str(als_path),
                fps=args.fps,
                num_frames=num_frames,
                timeline_start_seconds=start_offset,
            )
            alignment = analyze_als_audio_alignment(
                als_signals, samples, sample_rate, args.fps
            )
            print(
                "  ALS alignment:"
                f" melody~mid corr={alignment.melody_mid_corr:.3f},"
                f" bass~low corr={alignment.bass_low_corr:.3f},"
                f" kick-low={alignment.kick_low_at_onset_mean:.3f} vs global-low={alignment.low_band_global_mean:.3f}"
            )
            print(
                f"  ALS tracks: {len(als_signals.track_names)}, notes: {als_signals.note_count}, tempo: {als_signals.tempo_bpm:.2f} BPM"
            )
            _print_als_track_summary(als_signals)

        if args.no_audio_viz:
            if als_signals is None:
                raise ValueError("--no-audio-viz requires --als")
            energy = AudioEnergy(
                total=(als_signals.melody_energy + als_signals.bass_energy) * 0.5,
                low=als_signals.bass_energy,
                mid=als_signals.melody_energy,
                high=als_signals.transient_energy,
            )
        else:
            energy = compute_energy(samples, sample_rate, args.fps)

        num_frames = min(num_frames, len(energy.total))
        print(f"  Frames to render: {num_frames}")

        # Get hue offset (from --color or hash of filename)
        if args.color:
            try:
                hue_offset = get_hue_from_color(args.color)
                print(f"  Color: {args.color} (hue={hue_offset:.3f})")
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1
        else:
            hue_offset = get_hue_offset(input_path.name)
            print(f"  Hue offset: {hue_offset:.3f}")

        # Get shader (from --shader or hash of filename)
        if args.shader:
            try:
                shader_class = get_shader_by_name(args.shader)
                shader_index = SHADER_REGISTRY.index(shader_class)
                print(f"  Shader: {args.shader}")
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1
        else:
            shader_index = get_shader_index(input_path.name, get_num_shaders())
            print(f"  Shader index: {shader_index}")

        # Get vinyl scale and position from filename hash
        vinyl_scale = get_vinyl_scale(input_path.name)
        vinyl_offset_x = get_vinyl_offset_x(input_path.name)
        contrast = get_contrast(input_path.name)
        print(f"  Vinyl scale: {vinyl_scale:.2f}x, offset: {vinyl_offset_x:.2f}")
        print(f"  Contrast: {contrast:.2f}")

        # Initialize renderer
        print(f"Initializing renderer ({args.width}x{args.height})...")
        renderer = VinylRenderer(
            args.width,
            args.height,
            shader_index=shader_index,
            vinyl_scale=vinyl_scale,
            vinyl_offset_x=vinyl_offset_x,
            contrast=contrast,
            show_vinyl=not args.no_vinyl,
            bg_rgb=getattr(args, "bg_rgb", None),
            line_rgb=getattr(args, "line_rgb", None),
        )
        print(f"  Using shader: {renderer.bg_shader.name}")

        # Create and set label texture with track name in bold center, rim text on rim
        if not args.no_vinyl:
            rim_text = args.rim_text if args.rim_text else title
            print(f"  Rim text: {rim_text}")
            label_img = create_label_texture(track_name, artist, track_name=rim_text)
            renderer.set_label_texture(label_img)

        # Initialize encoder
        print("Starting video encoder...")
        # Write to a temp file first, then move into place on success.
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_dir = Path(tempfile.gettempdir())
        tmp_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_out = tempfile.mkstemp(
            prefix=f".{output_path.stem}.",
            suffix=".tmp.mp4",
            dir=str(tmp_dir),
        )
        os.close(fd)
        tmp_output_path = Path(tmp_out)
        encoder = VideoEncoder(
            output_path=str(tmp_output_path),
            audio_path=str(input_path),
            width=args.width,
            height=args.height,
            fps=args.fps,
            duration_limit=args.limit,
            start_offset=start_offset if start_offset > 0 else None,
        )

        # Randomize shader time start so videos don't all begin on the same frame.
        # This offsets the visual animation timeline only; audio energy indexing is unchanged.
        time_offset = random.uniform(0.0, 10_000.0)

        # Render frames with progress bar
        with tqdm(
            total=num_frames,
            desc="Rendering",
            unit="frame",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        ) as pbar:
            # #region agent log
            import json as _json
            _log_path = "/Users/dmackparty/dev/vinyl-mp4/.cursor/debug.log"
            _log_interval = 6  # log every 6 frames = 10 per second at 60fps
            # #endregion
            for frame_idx in range(num_frames):
                renderer.bg_shader.progress = frame_idx / num_frames
                time = (frame_idx / args.fps) + time_offset
                energy_low = energy.low[frame_idx]
                energy_mid = energy.mid[frame_idx]
                energy_high = energy.high[frame_idx]
                if args.no_audio_viz:
                    energy_low = energy_mid = energy_high = 0.0

                # #region agent log
                if frame_idx % _log_interval == 0:
                    _real_t = frame_idx / args.fps + (start_offset if start_offset > 0 else 0)
                    with open(_log_path, "a") as _f:
                        _f.write(_json.dumps({"location":"cli.py:render_loop","message":"frame_energy","data":{"frame":frame_idx,"real_time":round(_real_t,3),"low":round(float(energy_low),4),"mid":round(float(energy_mid),4),"high":round(float(energy_high),4)},"hypothesisId":"H6,H7","timestamp":int(__import__('time').time()*1000)}) + "\n")
                # #endregion

                # Render frame with frequency band energies
                frame_track_signals = None
                frame_track_onsets = None
                frame_track_pitches = None
                if als_signals is not None and frame_idx < als_signals.track_signals.shape[0]:
                    frame_track_signals = als_signals.track_signals[frame_idx].tolist()
                    frame_track_onsets = als_signals.track_onsets[frame_idx].tolist()
                    frame_track_pitches = list(als_signals.track_pitch_norms)

                frame_data = renderer.render_frame(
                    time,
                    energy_low,
                    energy_mid,
                    energy_high,
                    hue_offset,
                    track_signals=frame_track_signals,
                    track_onsets=frame_track_onsets,
                    track_pitches=frame_track_pitches,
                )

                # Flip vertically for correct video orientation (OpenGL is bottom-to-top)
                arr = np.frombuffer(frame_data, dtype=np.uint8).reshape(
                    args.height, args.width, 4
                )
                frame_data = np.ascontiguousarray(arr[::-1]).tobytes()

                # Write to encoder
                encoder.write_frame(frame_data)

                pbar.update(1)

        # Finish encoding
        print("Finalizing video...")
        encoder.finish()

        # Cleanup
        renderer.release()

        shutil.move(tmp_output_path, output_path)
        print(f"Done! Output saved to: {output_path}")
        return 0

    except FFmpegNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        # Best-effort cleanup of temp output file if it exists.
        try:
            tmp_output_path  # type: ignore[name-defined]
        except Exception:
            pass
        else:
            try:
                if tmp_output_path.exists():
                    tmp_output_path.unlink()
            except Exception:
                pass
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
