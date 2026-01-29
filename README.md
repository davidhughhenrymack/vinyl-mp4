# Vinyl MP4

Convert MP3 files to MP4 videos with audio-reactive vinyl visualization.

Generates a video with:
- **Animated iridescent background** - Domain-warped fractal Brownian motion patterns that react to audio energy (bass controls scale/intensity, treble controls brightness)
- **Spinning vinyl record** - 33 RPM rotation with realistic grooves, film grain, and a vintage-style label
- **Custom label design** - Shows artist, title, track name as curved text around the rim, and "DM" logo
- **Unique colors per file** - Each input file gets a unique color palette based on its filename hash, with slow hue rotation over time

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
# Clone the repository
git clone https://github.com/yourusername/vinyl-mp4.git
cd vinyl-mp4

# Install with uv
uv sync
```

Or with pip:

```bash
pip install -e .
```

## Usage

### Basic Usage

```bash
# Using uv
uv run vinyl-mp4 song.mp3

# Or if installed globally
vinyl-mp4 song.mp3
```

This will create `song.mp4` in the same directory as the input file.

### Options

```bash
vinyl-mp4 input.mp3 [OPTIONS]

Resolution Presets (mutually exclusive):
  --480p              Output at 480p (854x480)
  --720p              Output at 720p (1280x720) - ~350 fps
  --1080p             Output at 1080p (1920x1080) [default] - ~160 fps
  --1440p             Output at 1440p/2K (2560x1440)
  --4k                Output at 4K (3840x2160) - ~55 fps

Other Options:
  -o, --output PATH   Output file path (MP4 for video, PNG for --frame)
  --width INT         Video width in pixels (overrides presets)
  --height INT        Video height in pixels (overrides presets)
  --fps INT           Frames per second (default: 60)
  --limit SECONDS     Limit output to first N seconds of audio
  --name TEXT         Track name to display on vinyl label (default: filename)
  --frame SECONDS     Render a single frame at this time to PNG (for testing)
  --help              Show help message
```

### Examples

**Basic conversion:**
```bash
uv run vinyl-mp4 song.mp3
```

**Convert to 1080p:**
```bash
uv run vinyl-mp4 song.mp3 --width 1920 --height 1080
```

**Custom output path:**
```bash
uv run vinyl-mp4 song.mp3 -o output/my_video.mp4
```

**Render first 30 seconds only:**
```bash
uv run vinyl-mp4 song.mp3 --limit 30
# Output: song-30s.mp4
```

**Custom track name on label:**
```bash
uv run vinyl-mp4 song.mp3 --name "My Awesome Track"
```

**Quick test - render single frame:**
```bash
uv run vinyl-mp4 song.mp3 --frame 10
# Output: song-frame-10.0s.png

# Render frame at specific time with custom output
uv run vinyl-mp4 song.mp3 --frame 5.5 -o preview.png
```

**Lower FPS for smaller file:**
```bash
uv run vinyl-mp4 song.mp3 --fps 24
```

## How It Works

1. **Audio Analysis** - Loads the MP3, extracts ID3 metadata (title/artist), and computes per-frame energy in two frequency bands:
   - **Low frequency** (<250 Hz) - Bass and kick drums
   - **High frequency** (>4000 Hz) - Hi-hats, cymbals, brightness
2. **Color Selection** - Hashes the filename to determine a unique hue offset, plus slow sine-based hue rotation over ~30 minutes
3. **Rendering** - Uses headless OpenGL (ModernGL) to render each frame:
   - **Background**: Animated domain-warped fBM shader - bass controls scale/intensity, treble controls brightness
   - **Vinyl**: Spinning 33 RPM record with procedural grooves and animated film grain
   - **Label**: Vintage-style design with curved track name, artist/title, and logo
4. **Encoding** - Streams raw RGBA frames to FFmpeg for H.264 encoding, muxed with original audio

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=vinyl_mp4

# Run specific test file
uv run pytest tests/test_audio.py -v
```

### Project Structure

```
vinyl-mp4/
├── pyproject.toml           # Package configuration
├── README.md                # This file
├── src/
│   └── vinyl_mp4/
│       ├── __init__.py
│       ├── __main__.py      # Entry point for python -m
│       ├── cli.py           # Command-line interface
│       ├── audio.py         # Audio loading and analysis
│       ├── renderer.py      # OpenGL rendering
│       ├── shaders.py       # GLSL shader code
│       └── encoder.py       # FFmpeg video encoding
└── tests/
    ├── conftest.py          # Test fixtures
    ├── test_audio.py
    ├── test_cli.py
    ├── test_encoder.py
    ├── test_renderer.py
    └── test_shaders.py
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Credits

Background shader based on [Shadertoy tdG3Rd](https://www.shadertoy.com/view/tdG3Rd) "Base warp fBM".
