"""Shared test fixtures for vinyl-mp4."""

import math
import struct
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def sample_mp3(tmp_path: Path) -> Path:
    """Generate a short test MP3 file (1 second, 440Hz sine wave).

    Uses pydub to create a minimal test audio file.
    """
    from pydub import AudioSegment
    from pydub.generators import Sine

    # Generate 1 second of 440Hz sine wave
    sine_wave = Sine(440).to_audio_segment(duration=1000)

    # Export as MP3
    mp3_path = tmp_path / "test_audio.mp3"
    sine_wave.export(str(mp3_path), format="mp3")

    return mp3_path


@pytest.fixture
def sample_mp3_with_metadata(tmp_path: Path) -> Path:
    """Generate a test MP3 file with ID3 metadata tags."""
    from pydub import AudioSegment
    from pydub.generators import Sine
    from mutagen.id3 import ID3, TIT2, TPE1

    # Generate 1 second of 440Hz sine wave
    sine_wave = Sine(440).to_audio_segment(duration=1000)

    # Export as MP3
    mp3_path = tmp_path / "test_with_metadata.mp3"
    sine_wave.export(str(mp3_path), format="mp3")

    # Add ID3 tags
    audio = ID3(str(mp3_path))
    audio.add(TIT2(encoding=3, text="Test Song"))
    audio.add(TPE1(encoding=3, text="Test Artist"))
    audio.save()

    return mp3_path


@pytest.fixture
def silent_mp3(tmp_path: Path) -> Path:
    """Generate a silent MP3 file for testing energy computation."""
    from pydub import AudioSegment

    # Generate 1 second of silence
    silence = AudioSegment.silent(duration=1000)

    # Export as MP3
    mp3_path = tmp_path / "silent.mp3"
    silence.export(str(mp3_path), format="mp3")

    return mp3_path


@pytest.fixture
def mock_metadata() -> dict[str, str]:
    """Return mock metadata for testing."""
    return {"title": "Test Song", "artist": "Test Artist"}


@pytest.fixture
def sample_raw_audio() -> tuple:
    """Generate raw audio samples (numpy array) for testing.

    Returns:
        Tuple of (samples as numpy array, sample_rate)
    """
    import numpy as np

    sample_rate = 44100
    duration = 1.0  # 1 second
    frequency = 440  # Hz

    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    samples = np.sin(2 * np.pi * frequency * t)

    return samples, sample_rate


@pytest.fixture
def loud_mp3(tmp_path: Path) -> Path:
    """Generate a loud MP3 file for testing energy computation."""
    from pydub import AudioSegment
    from pydub.generators import Sine

    # Generate 1 second of loud 440Hz sine wave
    sine_wave = Sine(440).to_audio_segment(duration=1000)
    # Boost volume
    loud_wave = sine_wave + 10  # +10 dB

    mp3_path = tmp_path / "loud.mp3"
    loud_wave.export(str(mp3_path), format="mp3")

    return mp3_path
