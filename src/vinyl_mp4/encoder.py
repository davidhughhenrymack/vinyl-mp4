"""Video encoding using FFmpeg subprocess."""

import subprocess
import shutil
from typing import Optional


class FFmpegNotFoundError(Exception):
    """Raised when FFmpeg is not available."""

    pass


def check_ffmpeg() -> bool:
    """Check if FFmpeg is available on the system.

    Returns:
        True if ffmpeg is available, False otherwise.
    """
    return shutil.which("ffmpeg") is not None


def get_ffmpeg_version() -> Optional[str]:
    """Get the FFmpeg version string.

    Returns:
        Version string if ffmpeg is available, None otherwise.
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # First line typically contains version
            first_line = result.stdout.split("\n")[0]
            return first_line
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


class VideoEncoder:
    """Encodes raw video frames to MP4 using FFmpeg.

    Streams raw RGBA frames to ffmpeg via stdin and muxes with
    the original audio track.
    """

    def __init__(
        self,
        output_path: str,
        audio_path: str,
        width: int,
        height: int,
        fps: int,
        duration_limit: Optional[float] = None,
    ):
        """Initialize the encoder and start FFmpeg process.

        Args:
            output_path: Path for output MP4 file.
            audio_path: Path to audio file for muxing.
            width: Video frame width in pixels.
            height: Video frame height in pixels.
            fps: Video frames per second.
            duration_limit: Optional limit on output duration in seconds.

        Raises:
            FFmpegNotFoundError: If FFmpeg is not installed.
        """
        self.output_path = output_path
        self.audio_path = audio_path
        self.width = width
        self.height = height
        self.fps = fps
        self.duration_limit = duration_limit

        # Build FFmpeg command
        # Input: raw RGBA video from stdin
        # Input: audio from file
        # Output: H.264 video + AAC audio in MP4 container
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output without asking
            # Video input (raw frames from pipe)
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgba",
            "-s",
            f"{width}x{height}",
            "-r",
            str(fps),
            "-i",
            "pipe:0",
            # Audio input
            "-i",
            audio_path,
        ]

        # Add duration limit if specified
        if duration_limit is not None:
            cmd.extend(["-t", str(duration_limit)])

        cmd.extend(
            [
                # Video codec settings - ultrafast for maximum throughput
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                # Audio codec settings
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                # Use shortest stream (in case of length mismatch)
                "-shortest",
                # Output
                output_path,
            ]
        )

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as e:
            raise FFmpegNotFoundError(
                "FFmpeg not found. Please install FFmpeg to use this tool.\n"
                "On macOS: brew install ffmpeg\n"
                "On Ubuntu: sudo apt install ffmpeg"
            ) from e

    def write_frame(self, frame_data: bytes) -> None:
        """Write a single frame to the encoder.

        Args:
            frame_data: Raw RGBA pixel data (width * height * 4 bytes).
        """
        if self.proc.stdin:
            self.proc.stdin.write(frame_data)

    def finish(self) -> None:
        """Finish encoding and wait for FFmpeg to complete.

        This closes the input stream and waits for FFmpeg to finish
        writing the output file.
        """
        if self.proc.stdin:
            self.proc.stdin.close()

        # Wait for FFmpeg to complete and capture output
        # Don't use communicate() since stdin is already closed
        stderr_data = self.proc.stderr.read() if self.proc.stderr else b""
        self.proc.wait()

        if self.proc.returncode != 0:
            raise RuntimeError(
                f"FFmpeg failed with return code {self.proc.returncode}:\n"
                f"{stderr_data.decode('utf-8', errors='replace')}"
            )

    def abort(self) -> None:
        """Abort encoding and terminate FFmpeg process."""
        if self.proc.stdin:
            try:
                self.proc.stdin.close()
            except BrokenPipeError:
                pass

        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
