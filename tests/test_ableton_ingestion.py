"""Tests for Ableton ALS ingestion and signal extraction."""

from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
import pytest


def _write_test_als(path: Path) -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Ableton>
  <LiveSet>
    <MainTrack>
      <DeviceChain>
        <Mixer>
          <Tempo>
            <Manual Value="120" />
          </Tempo>
        </Mixer>
      </DeviceChain>
    </MainTrack>
    <Tracks>
      <MidiTrack Id="1">
        <Name><EffectiveName Value="Lead" /></Name>
        <MidiClip Id="10" Time="0">
          <KeyTracks>
            <KeyTrack Id="11">
              <Notes>
                <MidiNoteEvent Time="0" Duration="1" Velocity="100" />
              </Notes>
              <MidiKey Value="60" />
            </KeyTrack>
          </KeyTracks>
        </MidiClip>
      </MidiTrack>
      <MidiTrack Id="2">
        <Name><EffectiveName Value="Bass" /></Name>
        <MidiClip Id="20" Time="0">
          <KeyTracks>
            <KeyTrack Id="21">
              <Notes>
                <MidiNoteEvent Time="1" Duration="1" Velocity="90" />
              </Notes>
              <MidiKey Value="36" />
            </KeyTrack>
          </KeyTracks>
        </MidiClip>
      </MidiTrack>
    </Tracks>
  </LiveSet>
</Ableton>
"""
    path.write_bytes(gzip.compress(xml.encode("utf-8")))


def test_load_ableton_signals_extracts_signed_tracks(tmp_path: Path):
    from vinyl_mp4.ableton_ingestion import load_ableton_signals

    als_path = tmp_path / "test.als"
    _write_test_als(als_path)

    signals = load_ableton_signals(str(als_path), fps=10, num_frames=30)

    assert signals.track_signals.shape == (30, 2)
    assert signals.track_names == ["Lead", "Bass"]
    assert signals.note_count == 2
    assert np.any(signals.track_signals[:, 0] > 0.0)  # melody positive
    assert np.any(signals.track_signals[:, 1] < 0.0)  # bass negative
    assert np.all(signals.melody_energy >= 0.0)
    assert np.all(signals.bass_energy >= 0.0)
    assert np.all(signals.transient_energy >= 0.0)


def test_load_ableton_signals_requires_notes(tmp_path: Path):
    from vinyl_mp4.ableton_ingestion import load_ableton_signals

    empty_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Ableton>
  <LiveSet>
    <MainTrack><DeviceChain><Mixer><Tempo><Manual Value="120" /></Tempo></Mixer></DeviceChain></MainTrack>
    <Tracks><MidiTrack Id="1"><Name><EffectiveName Value="Empty" /></Name></MidiTrack></Tracks>
  </LiveSet>
</Ableton>
"""
    als_path = tmp_path / "empty.als"
    als_path.write_bytes(gzip.compress(empty_xml.encode("utf-8")))

    with pytest.raises(ValueError):
        load_ableton_signals(str(als_path), fps=10, num_frames=20)


def test_analyze_als_audio_alignment_returns_metrics(tmp_path: Path):
    from vinyl_mp4.ableton_ingestion import (
        load_ableton_signals,
        analyze_als_audio_alignment,
    )

    als_path = tmp_path / "test.als"
    _write_test_als(als_path)
    signals = load_ableton_signals(str(als_path), fps=20, num_frames=80)

    # 4 seconds audio at 44.1kHz with both low and mid content
    sample_rate = 44100
    t = np.linspace(0, 4, sample_rate * 4, endpoint=False, dtype=np.float32)
    samples = (0.4 * np.sin(2 * np.pi * 80 * t) + 0.4 * np.sin(2 * np.pi * 700 * t)).astype(
        np.float32
    )

    report = analyze_als_audio_alignment(signals, samples, sample_rate, fps=20)
    assert isinstance(report.melody_mid_corr, float)
    assert isinstance(report.bass_low_corr, float)
    assert 0.0 <= report.kick_low_at_onset_mean <= 1.0
    assert 0.0 <= report.low_band_global_mean <= 1.0
