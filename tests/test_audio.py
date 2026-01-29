"""Tests for audio module - written BEFORE implementation (TDD)."""

from pathlib import Path

import numpy as np
import pytest


class TestLoadAudio:
    """Tests for load_audio function."""

    def test_load_audio_returns_samples_and_rate(self, sample_mp3: Path):
        """Verify load_audio returns numpy array and sample rate."""
        from vinyl_mp4.audio import load_audio

        samples, sample_rate = load_audio(str(sample_mp3))

        assert isinstance(samples, np.ndarray)
        assert isinstance(sample_rate, int)
        assert sample_rate > 0
        assert len(samples) > 0

    def test_load_audio_file_not_found(self, tmp_path: Path):
        """Raises FileNotFoundError for missing file."""
        from vinyl_mp4.audio import load_audio

        with pytest.raises(FileNotFoundError):
            load_audio(str(tmp_path / "nonexistent.mp3"))

    def test_load_audio_samples_are_normalized(self, sample_mp3: Path):
        """Audio samples should be normalized to approximately -1.0 to 1.0 range."""
        from vinyl_mp4.audio import load_audio

        samples, _ = load_audio(str(sample_mp3))

        # Samples should be in reasonable range (allowing some headroom)
        assert np.max(np.abs(samples)) <= 2.0


class TestGetMetadata:
    """Tests for get_metadata function."""

    def test_get_metadata_extracts_title_artist(self, sample_mp3_with_metadata: Path):
        """Extracts ID3 tags correctly."""
        from vinyl_mp4.audio import get_metadata

        metadata = get_metadata(str(sample_mp3_with_metadata))

        assert metadata["title"] == "Test Song"
        assert metadata["artist"] == "Test Artist"

    def test_get_metadata_missing_tags(self, sample_mp3: Path):
        """Returns 'Unknown' for missing tags."""
        from vinyl_mp4.audio import get_metadata

        metadata = get_metadata(str(sample_mp3))

        assert metadata["title"] == "Unknown"
        assert metadata["artist"] == "Unknown"

    def test_get_metadata_file_not_found(self, tmp_path: Path):
        """Raises FileNotFoundError for missing file."""
        from vinyl_mp4.audio import get_metadata

        with pytest.raises(FileNotFoundError):
            get_metadata(str(tmp_path / "nonexistent.mp3"))


class TestComputeEnergy:
    """Tests for compute_energy function."""

    def test_compute_energy_shape(self, sample_raw_audio: tuple):
        """Output length should equal duration * fps."""
        from vinyl_mp4.audio import compute_energy

        samples, sample_rate = sample_raw_audio
        fps = 30
        duration = len(samples) / sample_rate

        energy = compute_energy(samples, sample_rate, fps)

        expected_frames = int(duration * fps)
        assert len(energy) == expected_frames

    def test_compute_energy_normalized(self, sample_raw_audio: tuple):
        """Values should be in 0.0-1.0 range."""
        from vinyl_mp4.audio import compute_energy

        samples, sample_rate = sample_raw_audio
        fps = 30

        energy = compute_energy(samples, sample_rate, fps)

        assert np.all(energy >= 0.0)
        assert np.all(energy <= 1.0)

    def test_compute_energy_silence(self):
        """Silent audio produces near-zero energy."""
        from vinyl_mp4.audio import compute_energy

        # Create silent samples
        sample_rate = 44100
        samples = np.zeros(sample_rate, dtype=np.float32)  # 1 second of silence
        fps = 30

        energy = compute_energy(samples, sample_rate, fps)

        # All energy values should be very close to zero
        assert np.all(energy < 0.01)

    def test_compute_energy_loud_vs_quiet(self):
        """Loud audio should have higher energy than quiet audio."""
        from vinyl_mp4.audio import compute_energy

        sample_rate = 44100
        fps = 30
        t = np.linspace(0, 1, sample_rate, dtype=np.float32)

        # Quiet sine wave
        quiet_samples = 0.1 * np.sin(2 * np.pi * 440 * t)
        quiet_energy = compute_energy(quiet_samples, sample_rate, fps)

        # Loud sine wave
        loud_samples = 0.9 * np.sin(2 * np.pi * 440 * t)
        loud_energy = compute_energy(loud_samples, sample_rate, fps)

        # Average energy should be higher for loud audio
        assert np.mean(loud_energy) > np.mean(quiet_energy)


class TestGetHueOffset:
    """Tests for get_hue_offset function."""

    def test_get_hue_offset_deterministic(self):
        """Same filename always returns same hue."""
        from vinyl_mp4.audio import get_hue_offset

        filename = "my_song.mp3"

        hue1 = get_hue_offset(filename)
        hue2 = get_hue_offset(filename)

        assert hue1 == hue2

    def test_get_hue_offset_range(self):
        """Output is always in 0.0-1.0."""
        from vinyl_mp4.audio import get_hue_offset

        test_filenames = [
            "song.mp3",
            "another_song.mp3",
            "very_long_filename_with_many_characters.mp3",
            "短い.mp3",  # Unicode
            "test123!@#.mp3",
        ]

        for filename in test_filenames:
            hue = get_hue_offset(filename)
            assert 0.0 <= hue <= 1.0, f"Hue {hue} out of range for {filename}"

    def test_get_hue_offset_different_files(self):
        """Different files produce different hues."""
        from vinyl_mp4.audio import get_hue_offset

        hue1 = get_hue_offset("song_a.mp3")
        hue2 = get_hue_offset("song_b.mp3")
        hue3 = get_hue_offset("completely_different.mp3")

        # At least some should be different (hash collision is very unlikely)
        hues = {hue1, hue2, hue3}
        assert len(hues) >= 2, "All hues are the same - possible issue with hashing"
