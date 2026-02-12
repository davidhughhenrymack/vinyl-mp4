"""Audio loading, metadata extraction, and energy computation."""

import hashlib
from pathlib import Path
from dataclasses import dataclass

import numpy as np
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
from pydub import AudioSegment
from scipy import signal as scipy_signal


@dataclass
class AudioEnergy:
    """Audio energy data split into frequency bands."""

    total: np.ndarray  # Total energy (0-1)
    low: np.ndarray  # Low frequency energy (0-1), sub-bass/kick <100Hz
    mid: np.ndarray  # Mid frequency energy (0-1), bass/vocals/instruments 100-4000Hz
    high: np.ndarray  # High frequency energy (0-1), hi-hats/cymbals >4000Hz


def load_audio(path: str) -> tuple[np.ndarray, int]:
    """Load an audio file and return samples as numpy array.

    Args:
        path: Path to the audio file (MP3 or WAV).

    Returns:
        Tuple of (samples as float32 numpy array normalized to -1.0 to 1.0, sample_rate)

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not Path(path).exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    audio = AudioSegment.from_file(path)

    # Get raw samples
    samples = np.array(audio.get_array_of_samples(), dtype=np.float32)

    # Handle stereo by averaging channels
    if audio.channels == 2:
        samples = samples.reshape((-1, 2)).mean(axis=1)

    # Normalize to -1.0 to 1.0 range
    max_val = 2 ** (audio.sample_width * 8 - 1)
    samples = samples / max_val

    return samples, audio.frame_rate


def get_metadata(path: str) -> dict[str, str]:
    """Extract title and artist from audio file metadata.

    Args:
        path: Path to the audio file (MP3 or WAV).

    Returns:
        Dict with 'title' and 'artist' keys. Missing title returns "CRATE1 2025", missing artist returns "DMACK".
        WAV files typically have no metadata so will use defaults.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not Path(path).exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    result = {"title": "2026", "artist": "DMACK"}

    try:
        audio = ID3(path)

        # TIT2 is the ID3 tag for title
        if "TIT2" in audio:
            result["title"] = str(audio["TIT2"])

        # TPE1 is the ID3 tag for lead artist
        if "TPE1" in audio:
            result["artist"] = str(audio["TPE1"])

    except Exception:
        # If ID3 tags can't be read, return defaults
        pass

    return result


def compute_energy(samples: np.ndarray, sample_rate: int, fps: int) -> AudioEnergy:
    """Compute audio energy per video frame, split into frequency bands.

    Uses RMS (root mean square) to calculate energy for each frame window.
    Splits audio into low (bass) and high (treble) frequency bands.
    Output is normalized to 0.0-1.0 range with smoothing applied.

    Args:
        samples: Audio samples as numpy array.
        sample_rate: Audio sample rate in Hz.
        fps: Video frames per second.

    Returns:
        AudioEnergy with total, low, and high frequency energy arrays.
    """
    duration = len(samples) / sample_rate
    num_frames = int(duration * fps)
    samples_per_frame = len(samples) // num_frames if num_frames > 0 else len(samples)

    if num_frames == 0:
        zeros = np.array([0.0], dtype=np.float32)
        return AudioEnergy(
            total=zeros, low=zeros.copy(), mid=zeros.copy(), high=zeros.copy()
        )

    # Design filters for frequency band separation
    # Low pass: 0-100 Hz (sub-bass, kick drums)
    # Band pass: 100-4000 Hz (bass guitar, vocals, instruments)
    # Band pass: 4000-20000 Hz (hi-hats, cymbals, brightness — capped at human hearing)
    nyquist = sample_rate / 2
    low_cutoff = 100 / nyquist
    high_cutoff = 4000 / nyquist
    hearing_limit = min(20000 / nyquist, 0.99)  # Cap at 20 kHz, stay below Nyquist

    # Create butterworth filters
    b_low, a_low = scipy_signal.butter(4, low_cutoff, btype="low")
    b_mid, a_mid = scipy_signal.butter(4, [low_cutoff, high_cutoff], btype="band")
    b_high, a_high = scipy_signal.butter(4, [high_cutoff, hearing_limit], btype="band")

    # Apply filters
    samples_low = scipy_signal.filtfilt(b_low, a_low, samples)
    samples_mid = scipy_signal.filtfilt(b_mid, a_mid, samples)
    samples_high = scipy_signal.filtfilt(b_high, a_high, samples)

    # Compute energy for each band
    energy_total = np.zeros(num_frames, dtype=np.float32)
    energy_low = np.zeros(num_frames, dtype=np.float32)
    energy_mid = np.zeros(num_frames, dtype=np.float32)
    energy_high = np.zeros(num_frames, dtype=np.float32)

    for i in range(num_frames):
        start = i * samples_per_frame
        end = min(start + samples_per_frame, len(samples))

        frame_total = samples[start:end]
        frame_low = samples_low[start:end]
        frame_mid = samples_mid[start:end]
        frame_high = samples_high[start:end]

        if len(frame_total) > 0:
            energy_total[i] = np.sqrt(np.mean(frame_total**2))
            energy_low[i] = np.sqrt(np.mean(frame_low**2))
            energy_mid[i] = np.sqrt(np.mean(frame_mid**2))
            energy_high[i] = np.sqrt(np.mean(frame_high**2))

    # Normalize each band independently
    def normalize_and_smooth(
        energy: np.ndarray, smooth_factor: float = 0.85
    ) -> np.ndarray:
        max_e = np.max(energy)
        if max_e > 0:
            energy = energy / max_e
        # Apply heavy smoothing for smoother animation
        smoothed = np.copy(energy)
        for i in range(1, len(smoothed)):
            smoothed[i] = (
                smooth_factor * smoothed[i - 1] + (1 - smooth_factor) * smoothed[i]
            )
        return np.clip(smoothed, 0.0, 1.0)

    # #region agent log
    import json as _json
    _log_path = "/Users/dmackparty/dev/vinyl-mp4/.cursor/debug.log"
    def _dbg(msg, data, hyp=""):
        import time as _t
        with open(_log_path, "a") as _f:
            _f.write(_json.dumps({"location":"audio.py:compute_energy","message":msg,"data":data,"hypothesisId":hyp,"timestamp":int(_t.time()*1000)}) + "\n")
    # Pre-normalization stats for each band
    _dbg("raw_energy_stats", {
        "low_max": float(np.max(energy_low)), "low_mean": float(np.mean(energy_low)),
        "low_p95": float(np.percentile(energy_low, 95)), "low_p99": float(np.percentile(energy_low, 99)),
        "mid_max": float(np.max(energy_mid)), "mid_mean": float(np.mean(energy_mid)),
        "high_max": float(np.max(energy_high)), "high_mean": float(np.mean(energy_high)),
        "num_frames": num_frames, "samples_per_frame": samples_per_frame,
    }, "H2,H3,H4")
    # Post-normalization, pre-smoothing stats
    _low_normed = energy_low / np.max(energy_low) if np.max(energy_low) > 0 else energy_low
    _dbg("low_normed_pre_smooth", {
        "max": float(np.max(_low_normed)), "mean": float(np.mean(_low_normed)),
        "p95": float(np.percentile(_low_normed, 95)), "p99": float(np.percentile(_low_normed, 99)),
        "first_300_values": [float(x) for x in _low_normed[:300]],
    }, "H1,H2")
    # #endregion

    result = AudioEnergy(
        total=normalize_and_smooth(energy_total, 0.9),
        low=normalize_and_smooth(energy_low, 0.7),
        mid=normalize_and_smooth(energy_mid, 0.90),
        high=normalize_and_smooth(energy_high, 0.88),
    )

    # #region agent log
    _dbg("post_smooth_low", {
        "max": float(np.max(result.low)), "mean": float(np.mean(result.low)),
        "min": float(np.min(result.low)),
        "p5": float(np.percentile(result.low, 5)), "p50": float(np.percentile(result.low, 50)),
        "p95": float(np.percentile(result.low, 95)),
        "first_300_values": [float(x) for x in result.low[:300]],
        "dynamic_range": float(np.max(result.low) - np.min(result.low)),
    }, "H1")
    _dbg("post_smooth_mid_high", {
        "mid_max": float(np.max(result.mid)), "mid_mean": float(np.mean(result.mid)),
        "mid_dynamic_range": float(np.max(result.mid) - np.min(result.mid)),
        "high_max": float(np.max(result.high)), "high_mean": float(np.mean(result.high)),
        "high_dynamic_range": float(np.max(result.high) - np.min(result.high)),
    }, "H1")
    # #endregion

    return result


def get_hue_offset(filename: str) -> float:
    """Hash filename to get deterministic hue from allowed colors.

    Uses MD5 hash of the filename to select from the list of allowed
    colors for random selection. Same filename always produces
    the same color scheme.

    Args:
        filename: The filename (not full path) to hash.

    Returns:
        Float in range 0.0-1.0 representing hue value from allowed colors.
    """
    from vinyl_mp4.shaders import get_random_color_hues

    allowed_hues = get_random_color_hues()
    h = hashlib.md5(filename.encode()).hexdigest()
    index = int(h[:8], 16) % len(allowed_hues)
    return allowed_hues[index]


def get_shader_index(filename: str, num_shaders: int) -> int:
    """Hash filename to get deterministic shader index.

    Uses different bits of the MD5 hash than get_hue_offset to ensure
    independent selection. Same filename always produces the same shader.

    Args:
        filename: The filename (not full path) to hash.
        num_shaders: Number of available shaders.

    Returns:
        Integer in range 0 to num_shaders-1.
    """
    if num_shaders <= 0:
        return 0
    h = hashlib.md5(filename.encode()).hexdigest()
    # Use bytes 8-16 (different from hue_offset which uses 0-8)
    return int(h[8:16], 16) % num_shaders


def get_vinyl_scale(filename: str) -> float:
    """Hash filename to get deterministic vinyl scale factor.

    Uses different bits of the MD5 hash than other hash functions.
    Scale ranges from 1.0 (base size) to 2.0 (double size).

    Args:
        filename: The filename (not full path) to hash.

    Returns:
        Float in range 1.0-2.0 representing scale multiplier.
    """
    h = hashlib.md5(filename.encode()).hexdigest()
    # Use bytes 16-24 (different from hue_offset and shader_index)
    normalized = int(h[16:24], 16) / 0xFFFFFFFF
    return 1.0 + normalized  # Range 1.0 to 2.0


def get_vinyl_offset_x(filename: str) -> float:
    """Hash filename to get deterministic vinyl horizontal offset.

    Uses different bits of the MD5 hash than other hash functions.
    Offset is in vinyl radii, ranging from -1.0 (left) to 1.0 (right).

    Args:
        filename: The filename (not full path) to hash.

    Returns:
        Float in range -1.0 to 1.0 representing horizontal offset.
    """
    h = hashlib.md5(filename.encode()).hexdigest()
    # Use bytes 24-32 (different from other hash functions)
    normalized = int(h[24:32], 16) / 0xFFFFFFFF
    return normalized * 2.0 - 1.0  # Range -1.0 to 1.0


def get_contrast(filename: str) -> float:
    """Hash filename to get deterministic contrast level.

    Uses a separate hash (prefixed filename) to ensure independent
    randomization from other parameters. Contrast ranges from 0.7
    (softer, more muted) to 1.3 (stronger, more vivid contrast).

    Args:
        filename: The filename (not full path) to hash.

    Returns:
        Float in range 0.7-1.3 representing contrast multiplier.
    """
    # Use different hash by prefixing to ensure independent randomization
    h = hashlib.md5(f"contrast-{filename}".encode()).hexdigest()
    normalized = int(h[:8], 16) / 0xFFFFFFFF
    return 0.7 + normalized * 0.6  # Range 0.7 to 1.3
