# Vinyl MP4

Convert audio files to MP4 videos with audio-reactive vinyl visualization.

Generates a video with:
- **Audio-reactive background shaders** - Multiple shader options (FBM Warp, Melted Sphere, Retro Terrain, Aurora Wave) that react to bass, mids, and treble
- **Spinning vinyl record** - 33 RPM rotation with realistic grooves, film grain, and a vintage-style label
- **Custom label design** - Shows artist, title, track name as curved text around the rim, and "DM" logo
- **Unique colors per file** - Each input file gets a unique color palette based on its filename hash

## Requirements

- **Python 3.13+**
- **FFmpeg** - Must be installed and available in PATH
- **OpenGL** - Required for GPU-accelerated rendering

### Installing FFmpeg

**macOS (Homebrew):**

```bash
brew install ffmpeg
```

**Ubuntu/Debian:**

```bash
sudo apt install ffmpeg
```

**Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

## Installation

Using [uv](https://docs.astral.sh/uv/) (recommended):

```bash
git clone https://github.com/yourusername/vinyl-mp4.git
cd vinyl-mp4
uv sync
```

Or with pip:

```bash
pip install -e .
```

## Quick Start

```bash
# Render a full track (outputs song.mp4 next to the input file)
uv run vinyl-mp4 song.mp3

# Render 20 seconds at 480p with a specific shader
uv run vinyl-mp4 song.flac --limit 20 --480p --shader terrain

# Preview a single frame at the 10-second mark
uv run vinyl-mp4 song.mp3 --frame 10
```

## Usage

```
vinyl-mp4 INPUT [OPTIONS]
```

`INPUT` can be any audio file supported by FFmpeg (MP3, FLAC, WAV, etc.).

### Resolution Presets

| Flag     | Resolution  |
|----------|-------------|
| `--480p` | 854 x 480   |
| `--720p` | 1280 x 720  |
| `--1080p`| 1920 x 1080 (default) |
| `--1440p`| 2560 x 1440 |
| `--4k`   | 3840 x 2160 |

Or pass `--width` and `--height` directly to override presets.

### Options

| Option | Description |
|--------|-------------|
| `-o, --output PATH` | Output file path (MP4 for video, PNG for `--frame`) |
| `--fps INT` | Frames per second (default: 60) |
| `--limit SECONDS` | Render only the first N seconds |
| `--start SECONDS` | Start from N seconds into the audio |
| `--name TEXT` | Track name on the vinyl label (default: filename) |
| `--rim-text TEXT` | Text around the vinyl rim (default: title from metadata) |
| `--frame SECONDS` | Render a single frame to PNG instead of video |
| `--shader NAME` | Background shader (see below) |
| `--color NAME` | Base color: red, orange, yellow, lime, green, teal, cyan, sky, blue, indigo, purple, violet, magenta, pink |
| `--als PATH` | Optional Ableton `.als` file to feed per-track MIDI note signals to shaders |
| `--no-audio-viz` | Use ALS-only visualization inputs (requires `--als`) |

### Shaders

| Name | CLI flag | Description |
|------|----------|-------------|
| FBM Warp | `--shader fbm` | Flowing fractal Brownian motion patterns |
| Melted Sphere | `--shader melted` | Raymarched iridescent blob |
| Retro Terrain | `--shader terrain` | Wireframe terrain with perspective projection |
| Aurora Wave | `--shader aurora` | Undulating aurora borealis waves |

By default a shader is auto-selected based on the filename hash.

### Examples

```bash
# Basic conversion (auto shader, auto color, 1080p)
uv run vinyl-mp4 song.mp3

# Custom output path
uv run vinyl-mp4 song.mp3 -o output/my_video.mp4

# First 30 seconds only (output: song-30s.mp4)
uv run vinyl-mp4 song.mp3 --limit 30

# Start from 60 seconds in, render 20 seconds
uv run vinyl-mp4 song.mp3 --start 60 --limit 20

# Custom label text
uv run vinyl-mp4 song.mp3 --name "My Track" --rim-text "SIDE A"

# Pick shader + color
uv run vinyl-mp4 song.mp3 --shader terrain --color cyan

# Drive visualization from Ableton MIDI tracks only
uv run vinyl-mp4 song.flac --als media/hey.als --no-audio-viz --shader terrain

# Quick frame preview
uv run vinyl-mp4 song.mp3 --frame 5.5 -o preview.png

# Lower FPS for smaller file
uv run vinyl-mp4 song.mp3 --fps 24
```

## How It Works

1. **Audio Analysis** - Loads the audio file, extracts metadata (title/artist), and computes per-frame energy in three frequency bands:
   - **Low** (<250 Hz) - Bass and kick drums
   - **Mid** (250-4000 Hz) - Vocals, instruments
   - **High** (>4000 Hz) - Hi-hats, cymbals, brightness
2. **Color Selection** - Hashes the filename to determine a unique hue offset
3. **Rendering** - Uses headless OpenGL (ModernGL) to render each frame:
   - **Background**: Audio-reactive shader (bass controls amplitude/scale, mids affect brightness, treble drives shape/warp)
   - **Vinyl**: Spinning 33 RPM record with procedural grooves and animated film grain
   - **Label**: Vintage-style design with curved track name, artist/title, and logo
4. **Encoding** - Streams raw RGBA frames to FFmpeg for H.264 encoding, muxed with original audio

## Development

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=vinyl_mp4

# Run a specific test file
uv run pytest tests/test_audio.py -v
```

### Project Structure

```
vinyl-mp4/
├── pyproject.toml
├── README.md
├── src/
│   └── vinyl_mp4/
│       ├── __init__.py
│       ├── __main__.py          # python -m entry point
│       ├── cli.py               # Command-line interface
│       ├── audio.py             # Audio loading and energy analysis
│       ├── renderer.py          # OpenGL rendering pipeline
│       ├── encoder.py           # FFmpeg video encoding
│       └── shaders/
│           ├── __init__.py      # Shader registry
│           ├── base.py          # BaseShader abstract class
│           ├── fbm_warp.py      # FBM Warp shader
│           ├── melted_sphere.py # Melted Sphere shader
│           ├── retro_terrain.py # Retro Terrain shader
│           ├── aurora_wave.py   # Aurora Wave shader
│           └── vinyl.py         # Vinyl record overlay
└── tests/
```

## License

MIT License - see [LICENSE](LICENSE) for details.
