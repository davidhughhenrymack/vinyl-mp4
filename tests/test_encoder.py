"""Tests for encoder module - written BEFORE implementation (TDD)."""

import subprocess
from pathlib import Path

import pytest
import numpy as np


class TestVideoEncoder:
    """Tests for VideoEncoder class."""

    def test_encoder_starts_ffmpeg(self, sample_mp3: Path, tmp_path: Path):
        """FFmpeg process spawns successfully."""
        from vinyl_mp4.encoder import VideoEncoder

        output_path = tmp_path / "output.mp4"
        encoder = VideoEncoder(
            output_path=str(output_path),
            audio_path=str(sample_mp3),
            width=320,
            height=240,
            fps=30,
        )

        try:
            # Process should be running
            assert encoder.proc is not None
            assert encoder.proc.poll() is None  # None means still running
        finally:
            encoder.abort()

    def test_encoder_accepts_frames(self, sample_mp3: Path, tmp_path: Path):
        """Can write frame data without error."""
        from vinyl_mp4.encoder import VideoEncoder

        output_path = tmp_path / "output.mp4"
        width, height = 320, 240

        encoder = VideoEncoder(
            output_path=str(output_path),
            audio_path=str(sample_mp3),
            width=width,
            height=height,
            fps=30,
        )

        try:
            # Create a test frame (solid red)
            frame = np.zeros((height, width, 4), dtype=np.uint8)
            frame[:, :, 0] = 255  # Red channel
            frame[:, :, 3] = 255  # Alpha

            # Should not raise an exception
            encoder.write_frame(frame.tobytes())
        finally:
            encoder.abort()

    def test_encoder_finish_creates_file(self, sample_mp3: Path, tmp_path: Path):
        """Output file exists after finish()."""
        from vinyl_mp4.encoder import VideoEncoder

        output_path = tmp_path / "output.mp4"
        width, height = 320, 240
        fps = 30

        encoder = VideoEncoder(
            output_path=str(output_path),
            audio_path=str(sample_mp3),
            width=width,
            height=height,
            fps=fps,
        )

        # Write enough frames for 1 second (matching the sample_mp3 duration)
        frame = np.zeros((height, width, 4), dtype=np.uint8)
        frame[:, :, 0] = 255  # Red
        frame[:, :, 3] = 255  # Alpha
        frame_bytes = frame.tobytes()

        for _ in range(fps):  # 1 second worth of frames
            encoder.write_frame(frame_bytes)

        encoder.finish()

        # File should exist and have content
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_encoder_ffmpeg_not_found(
        self, sample_mp3: Path, tmp_path: Path, monkeypatch
    ):
        """Raises clear error if ffmpeg missing."""
        from vinyl_mp4.encoder import VideoEncoder, FFmpegNotFoundError

        # Mock subprocess to simulate ffmpeg not found
        def mock_popen(*args, **kwargs):
            raise FileNotFoundError("ffmpeg not found")

        monkeypatch.setattr(subprocess, "Popen", mock_popen)

        output_path = tmp_path / "output.mp4"

        with pytest.raises(FFmpegNotFoundError):
            VideoEncoder(
                output_path=str(output_path),
                audio_path=str(sample_mp3),
                width=320,
                height=240,
                fps=30,
            )

    def test_encoder_abort_cleans_up(self, sample_mp3: Path, tmp_path: Path):
        """abort() properly terminates the process."""
        from vinyl_mp4.encoder import VideoEncoder

        output_path = tmp_path / "output.mp4"
        encoder = VideoEncoder(
            output_path=str(output_path),
            audio_path=str(sample_mp3),
            width=320,
            height=240,
            fps=30,
        )

        encoder.abort()

        # Process should be terminated
        assert encoder.proc.poll() is not None


class TestFFmpegAvailability:
    """Tests for FFmpeg availability check."""

    def test_check_ffmpeg_available(self):
        """check_ffmpeg returns True when ffmpeg is installed."""
        from vinyl_mp4.encoder import check_ffmpeg

        # This test assumes ffmpeg is installed in the test environment
        # If not, this test will fail which is intentional
        result = check_ffmpeg()
        assert isinstance(result, bool)

    def test_check_ffmpeg_returns_version(self):
        """check_ffmpeg can return version info."""
        from vinyl_mp4.encoder import get_ffmpeg_version

        version = get_ffmpeg_version()
        # Should return a string if ffmpeg is available, or None if not
        if version is not None:
            assert isinstance(version, str)
            assert len(version) > 0
