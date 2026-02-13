"""Ableton Live Set (.als) ingestion and signal extraction."""

from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import signal as scipy_signal


_MAX_TRACK_SIGNALS = 64


@dataclass
class AbletonSignals:
    """Frame-aligned note signals derived from an ALS file."""

    track_names: list[str]
    track_signals: np.ndarray  # shape: (num_frames, num_tracks), values in [-1, 1]
    melody_energy: np.ndarray  # shape: (num_frames,), values in [0, 1]
    bass_energy: np.ndarray  # shape: (num_frames,), values in [0, 1]
    transient_energy: np.ndarray  # shape: (num_frames,), values in [0, 1]
    tempo_bpm: float
    note_count: int


@dataclass
class AlignmentReport:
    """Coarse ALS-to-audio alignment metrics."""

    melody_mid_corr: float
    bass_low_corr: float
    kick_low_at_onset_mean: float
    low_band_global_mean: float


def _normalize_01(values: np.ndarray) -> np.ndarray:
    max_val = float(np.max(values)) if values.size > 0 else 0.0
    if max_val <= 0.0:
        return np.zeros_like(values, dtype=np.float32)
    return np.clip(values / max_val, 0.0, 1.0).astype(np.float32)


def _load_als_root(als_path: str) -> ET.Element:
    path = Path(als_path)
    if not path.exists():
        raise FileNotFoundError(f"Ableton project file not found: {als_path}")

    raw = path.read_bytes()
    xml_bytes = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
    return ET.fromstring(xml_bytes)


def _track_name(track: ET.Element) -> str:
    effective_name = track.find(".//Name/EffectiveName")
    if effective_name is not None and effective_name.get("Value"):
        return str(effective_name.get("Value"))
    track_id = track.get("Id", "unknown")
    return f"{track.tag}-{track_id}"


def _extract_tempo_bpm(root: ET.Element) -> float:
    tempo_node = root.find(".//MainTrack/DeviceChain/Mixer/Tempo/Manual")
    if tempo_node is None or tempo_node.get("Value") is None:
        raise ValueError("ALS parsing error: could not find project tempo")
    tempo_bpm = float(tempo_node.get("Value"))
    if tempo_bpm <= 0.0:
        raise ValueError("ALS parsing error: tempo must be positive")
    return tempo_bpm


def load_ableton_signals(
    als_path: str,
    fps: int,
    num_frames: int,
    timeline_start_seconds: float = 0.0,
    pitch_split: int = 48,
    max_tracks: int = _MAX_TRACK_SIGNALS,
) -> AbletonSignals:
    """Parse ALS and build frame-aligned per-track signed note signals.

    Positive values represent melody notes, negative values represent bass notes.
    Amplitude is weighted by note pitch and velocity.
    """
    if fps <= 0:
        raise ValueError("fps must be > 0")
    if num_frames <= 0:
        raise ValueError("num_frames must be > 0")
    if max_tracks <= 0:
        raise ValueError("max_tracks must be > 0")

    root = _load_als_root(als_path)
    tempo_bpm = _extract_tempo_bpm(root)
    seconds_per_beat = 60.0 / tempo_bpm

    track_names: list[str] = []
    per_track_series: list[np.ndarray] = []
    note_count = 0

    for track in root.findall(".//Tracks/MidiTrack"):
        current_track_name = _track_name(track)
        track_series = np.zeros(num_frames, dtype=np.float32)
        track_pitches: list[int] = []
        for key_track in track.findall(".//KeyTracks/KeyTrack"):
            midi_key = key_track.find("./MidiKey")
            if midi_key is None or midi_key.get("Value") is None:
                continue
            track_pitches.append(int(float(midi_key.get("Value"))))
        if not track_pitches:
            continue
        track_min_pitch = min(track_pitches)
        track_max_pitch = max(track_pitches)
        track_pitch_range = track_max_pitch - track_min_pitch

        for clip in track.findall(".//MidiClip"):
            clip_time_beats = float(clip.get("Time", "0"))

            for key_track in clip.findall(".//KeyTracks/KeyTrack"):
                midi_key = key_track.find("./MidiKey")
                if midi_key is None or midi_key.get("Value") is None:
                    continue
                pitch = int(float(midi_key.get("Value")))

                for midi_note in key_track.findall("./Notes/MidiNoteEvent"):
                    note_start_beats = clip_time_beats + float(midi_note.get("Time", "0"))
                    note_duration_beats = float(midi_note.get("Duration", "0"))
                    velocity = float(midi_note.get("Velocity", "0"))

                    start_seconds = (note_start_beats * seconds_per_beat) - timeline_start_seconds
                    duration_seconds = max(note_duration_beats * seconds_per_beat, 0.0)
                    if start_seconds + duration_seconds <= 0.0:
                        continue

                    start_frame = max(0, int(np.floor(start_seconds * fps)))
                    end_frame = min(
                        num_frames - 1,
                        int(np.floor((start_seconds + max(duration_seconds, 1.0 / fps)) * fps)),
                    )
                    if start_frame > end_frame:
                        continue

                    velocity_weight = np.clip(velocity / 127.0, 0.0, 1.0)
                    if track_pitch_range > 0:
                        pitch_weight = np.clip(
                            (pitch - track_min_pitch) / track_pitch_range, 0.0, 1.0
                        )
                    else:
                        pitch_weight = 1.0
                    magnitude = velocity_weight * pitch_weight
                    signed_magnitude = magnitude if pitch >= pitch_split else -magnitude
                    track_series[start_frame : end_frame + 1] += signed_magnitude
                    note_count += 1

        if np.any(track_series):
            track_names.append(current_track_name)
            per_track_series.append(np.clip(track_series, -1.0, 1.0))
            if len(per_track_series) >= max_tracks:
                break

    if not per_track_series:
        raise ValueError("ALS parsing error: no MIDI note events found in MidiTracks")

    track_signals = np.stack(per_track_series, axis=1).astype(np.float32)
    melody_energy = _normalize_01(np.sum(np.clip(track_signals, 0.0, 1.0), axis=1))
    bass_energy = _normalize_01(np.sum(np.clip(-track_signals, 0.0, 1.0), axis=1))
    transient_energy = _normalize_01(np.abs(np.diff(np.sum(track_signals, axis=1), prepend=0.0)))

    return AbletonSignals(
        track_names=track_names,
        track_signals=track_signals,
        melody_energy=melody_energy,
        bass_energy=bass_energy,
        transient_energy=transient_energy,
        tempo_bpm=tempo_bpm,
        note_count=note_count,
    )


def analyze_als_audio_alignment(
    signals: AbletonSignals,
    samples: np.ndarray,
    sample_rate: int,
    fps: int,
) -> AlignmentReport:
    """Compare ALS-derived activity to audio low/mid bands at frame resolution."""
    if sample_rate <= 0:
        raise ValueError("sample_rate must be > 0")
    if fps <= 0:
        raise ValueError("fps must be > 0")

    duration = len(samples) / sample_rate if sample_rate > 0 else 0.0
    num_frames = min(len(signals.melody_energy), int(duration * fps))
    if num_frames <= 1:
        raise ValueError("Not enough frames for alignment analysis")

    samples_per_frame = max(1, len(samples) // num_frames)
    nyquist = sample_rate / 2.0
    low_cutoff = min(180.0 / nyquist, 0.99)
    mid_low = min(220.0 / nyquist, 0.99)
    mid_high = min(2200.0 / nyquist, 0.99)
    if not (0.0 < mid_low < mid_high < 1.0):
        raise ValueError("Invalid sample_rate for analysis filters")

    b_low, a_low = scipy_signal.butter(4, low_cutoff, btype="low")
    b_mid, a_mid = scipy_signal.butter(4, [mid_low, mid_high], btype="band")
    low_filtered = scipy_signal.filtfilt(b_low, a_low, samples)
    mid_filtered = scipy_signal.filtfilt(b_mid, a_mid, samples)

    low_energy = np.zeros(num_frames, dtype=np.float32)
    mid_energy = np.zeros(num_frames, dtype=np.float32)
    for i in range(num_frames):
        start = i * samples_per_frame
        end = min(start + samples_per_frame, len(samples))
        frame_low = low_filtered[start:end]
        frame_mid = mid_filtered[start:end]
        if len(frame_low) == 0:
            continue
        low_energy[i] = np.sqrt(np.mean(frame_low**2))
        mid_energy[i] = np.sqrt(np.mean(frame_mid**2))

    low_norm = _normalize_01(low_energy)
    mid_norm = _normalize_01(mid_energy)
    melody = signals.melody_energy[:num_frames]
    bass = signals.bass_energy[:num_frames]

    def _corr(a: np.ndarray, b: np.ndarray) -> float:
        if np.std(a) == 0.0 or np.std(b) == 0.0:
            return 0.0
        return float(np.corrcoef(a, b)[0, 1])

    # Kick proxy: frames where bass activity spikes.
    bass_diff = np.diff(bass, prepend=0.0)
    kick_frames = np.where(bass_diff > 0.25)[0]
    kick_mean = float(np.mean(low_norm[kick_frames])) if len(kick_frames) > 0 else 0.0

    return AlignmentReport(
        melody_mid_corr=_corr(melody, mid_norm),
        bass_low_corr=_corr(bass, low_norm),
        kick_low_at_onset_mean=kick_mean,
        low_band_global_mean=float(np.mean(low_norm)),
    )
