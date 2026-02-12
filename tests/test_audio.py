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
        """Returns defaults for missing tags."""
        from vinyl_mp4.audio import get_metadata

        metadata = get_metadata(str(sample_mp3))

        assert metadata["title"] == "2026"
        assert metadata["artist"] == "DMACK"

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
        assert len(energy.low) == expected_frames
        assert len(energy.mid) == expected_frames
        assert len(energy.high) == expected_frames

    def test_compute_energy_normalized(self, sample_raw_audio: tuple):
        """Values should be in 0.0-1.0 range."""
        from vinyl_mp4.audio import compute_energy

        samples, sample_rate = sample_raw_audio
        fps = 30

        energy = compute_energy(samples, sample_rate, fps)

        assert np.all(energy.low >= 0.0)
        assert np.all(energy.low <= 1.0)
        assert np.all(energy.mid >= 0.0)
        assert np.all(energy.mid <= 1.0)
        assert np.all(energy.high >= 0.0)
        assert np.all(energy.high <= 1.0)

    def test_compute_energy_silence(self):
        """Silent audio produces near-zero energy."""
        from vinyl_mp4.audio import compute_energy

        # Create silent samples
        sample_rate = 44100
        samples = np.zeros(sample_rate, dtype=np.float32)  # 1 second of silence
        fps = 30

        energy = compute_energy(samples, sample_rate, fps)

        # All energy values should be very close to zero
        assert np.all(energy.low < 0.01)
        assert np.all(energy.mid < 0.01)
        assert np.all(energy.high < 0.01)

    def test_compute_energy_produces_valid_output(self):
        """Audio signal produces valid energy output in all bands."""
        from vinyl_mp4.audio import compute_energy

        sample_rate = 44100
        fps = 30
        t = np.linspace(0, 1, sample_rate, dtype=np.float32)

        # Create a signal with energy in all frequency bands
        # Low: 50Hz, Mid: 440Hz, High: 8000Hz
        samples = (
            0.3 * np.sin(2 * np.pi * 50 * t)  # Low frequency
            + 0.5 * np.sin(2 * np.pi * 440 * t)  # Mid frequency
            + 0.2 * np.sin(2 * np.pi * 8000 * t)  # High frequency
        ).astype(np.float32)

        energy = compute_energy(samples, sample_rate, fps)

        # All bands should have some energy (after normalization)
        assert np.mean(energy.low) > 0.0
        assert np.mean(energy.mid) > 0.0
        assert np.mean(energy.high) > 0.0
        assert np.mean(energy.total) > 0.0


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


class TestGetShaderIndex:
    """Tests for get_shader_index function."""

    def test_get_shader_index_deterministic(self):
        """Same filename always returns same shader index."""
        from vinyl_mp4.audio import get_shader_index

        filename = "my_song.mp3"

        idx1 = get_shader_index(filename, 2)
        idx2 = get_shader_index(filename, 2)

        assert idx1 == idx2

    def test_get_shader_index_in_range(self):
        """Index always less than num_shaders."""
        from vinyl_mp4.audio import get_shader_index

        test_filenames = [
            "a.mp3",
            "b.mp3",
            "test.mp3",
            "song_123.mp3",
            "另一首歌.mp3",
        ]

        for filename in test_filenames:
            assert 0 <= get_shader_index(filename, 2) < 2
            assert 0 <= get_shader_index(filename, 5) < 5
            assert 0 <= get_shader_index(filename, 10) < 10

    def test_get_shader_index_zero_shaders(self):
        """Returns 0 when num_shaders is 0."""
        from vinyl_mp4.audio import get_shader_index

        assert get_shader_index("song.mp3", 0) == 0

    def test_get_shader_index_uses_different_bits_than_hue(self):
        """Uses different hash bits than hue_offset for independence."""
        from vinyl_mp4.audio import get_shader_index, get_hue_offset

        # Test many files to find examples where shader differs even with similar hue
        # This is a probabilistic test - with 2 shaders, roughly half should be shader 0
        shader_counts = {0: 0, 1: 0}
        for i in range(100):
            filename = f"test_song_{i}.mp3"
            idx = get_shader_index(filename, 2)
            shader_counts[idx] += 1

        # Both shaders should be selected at least some times
        assert shader_counts[0] > 20, "Shader 0 selected too rarely"
        assert shader_counts[1] > 20, "Shader 1 selected too rarely"
