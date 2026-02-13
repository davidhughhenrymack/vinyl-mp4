"""Tests for CLI module - written BEFORE implementation (TDD)."""

import subprocess
import sys
from pathlib import Path

import pytest


class TestCLIArguments:
    """Tests for CLI argument parsing."""

    def test_cli_help(self):
        """--help exits 0 and shows usage."""
        result = subprocess.run(
            [sys.executable, "-m", "vinyl_mp4", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "mp3" in result.stdout.lower()

    def test_cli_missing_input(self):
        """Missing input file shows error."""
        result = subprocess.run(
            [sys.executable, "-m", "vinyl_mp4"],
            capture_output=True,
            text=True,
        )

        # Should exit with error
        assert result.returncode != 0

    def test_cli_nonexistent_file(self, tmp_path: Path):
        """Nonexistent input file shows clear error."""
        result = subprocess.run(
            [sys.executable, "-m", "vinyl_mp4", str(tmp_path / "nonexistent.mp3")],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        # Should mention the file doesn't exist
        assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()


class TestCLIIntegration:
    """Integration tests for full CLI pipeline."""

    def test_cli_full_pipeline(self, sample_mp3_with_metadata: Path, tmp_path: Path):
        """End-to-end: MP3 in, MP4 out."""
        output_path = tmp_path / "output.mp4"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "vinyl_mp4",
                str(sample_mp3_with_metadata),
                "-o",
                str(output_path),
                "--width",
                "320",
                "--height",
                "240",
                "--fps",
                "10",  # Low FPS for faster test
            ],
            capture_output=True,
            text=True,
            timeout=60,  # 1 minute timeout
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_cli_custom_resolution(self, sample_mp3: Path, tmp_path: Path):
        """--width/--height respected."""
        output_path = tmp_path / "output.mp4"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "vinyl_mp4",
                str(sample_mp3),
                "-o",
                str(output_path),
                "--width",
                "640",
                "--height",
                "480",
                "--fps",
                "10",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_path.exists()

    def test_cli_default_output_name(
        self, sample_mp3: Path, tmp_path: Path, monkeypatch
    ):
        """Default output name is input name with .mp4 extension."""
        # Change to tmp directory so output goes there
        monkeypatch.chdir(tmp_path)

        # Copy sample to tmp_path
        import shutil

        local_mp3 = tmp_path / "test_song.mp3"
        shutil.copy(sample_mp3, local_mp3)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "vinyl_mp4",
                str(local_mp3),
                "--width",
                "320",
                "--height",
                "240",
                "--fps",
                "10",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(tmp_path),
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Output should be test_song.mp4
        expected_output = tmp_path / "test_song.mp4"
        assert expected_output.exists()


class TestCLIOutputValidation:
    """Tests for output video validation."""

    def test_output_video_has_audio(self, sample_mp3: Path, tmp_path: Path):
        """Output MP4 contains audio stream."""
        output_path = tmp_path / "output.mp4"

        # Generate video
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "vinyl_mp4",
                str(sample_mp3),
                "-o",
                str(output_path),
                "--width",
                "320",
                "--height",
                "240",
                "--fps",
                "10",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Use ffprobe to check for audio stream
        probe_result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                str(output_path),
            ],
            capture_output=True,
            text=True,
        )

        assert "audio" in probe_result.stdout

    def test_output_video_has_video(self, sample_mp3: Path, tmp_path: Path):
        """Output MP4 contains video stream."""
        output_path = tmp_path / "output.mp4"

        # Generate video
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "vinyl_mp4",
                str(sample_mp3),
                "-o",
                str(output_path),
                "--width",
                "320",
                "--height",
                "240",
                "--fps",
                "10",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Use ffprobe to check for video stream
        probe_result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                str(output_path),
            ],
            capture_output=True,
            text=True,
        )

        assert "video" in probe_result.stdout


class TestTonight:
    """Integration test for 'tonight' project: short render with Micro Shapes + ALS when media exists."""

    def test_tonight_preview_render(self, tmp_path: Path):
        """Run a short 480p preview of tonight with Micro Shapes shader; skip if media/tonight.flac missing."""
        project_root = Path(__file__).resolve().parent.parent
        audio = project_root / "media" / "tonight.flac"
        als = project_root / "media" / "tonight.als"
        if not audio.exists():
            pytest.skip("media/tonight.flac not found; add it to run the tonight test")
        output_path = tmp_path / "tonight-test-preview.mp4"
        cmd = [
            sys.executable,
            "-m",
            "vinyl_mp4",
            str(audio),
            "-o",
            str(output_path),
            "--shader",
            "Micro Shapes",
            "--480p",
            "--no-vinyl",
            "--limit",
            "3",
            "--fps",
            "15",
        ]
        if als.exists():
            cmd.extend(["--als", str(als)])
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=90,
            cwd=str(project_root),
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_path.exists()
        assert output_path.stat().st_size > 0
