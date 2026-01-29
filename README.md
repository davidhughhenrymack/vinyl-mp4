# Vinyl MP4

Convert MP3 files to MP4 videos with audio-reactive vinyl visualization.

Generates a video with:
- **Animated iridescent background** - Domain-warped fractal Brownian motion patterns that react to audio energy
- **Spinning vinyl record** - 33 RPM rotation with grooves and a label showing track title/artist
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

Options:
  -o, --output PATH   Output MP4 file path (default: input name with .mp4)
  --width INT         Video width in pixels (default: 3840 for 4K)
  --height INT        Video height in pixels (default: 2160 for 4K)
  --fps INT           Frames per second (default: 30)
  --help              Show help message
```

### Examples

**Convert to 1080p:**
```bash
uv run vinyl-mp4 song.mp3 --width 1920 --height 1080
```

**Custom output path:**
```bash
uv run vinyl-mp4 song.mp3 -o output/my_video.mp4
```

**Lower FPS for smaller file:**
```bash
uv run vinyl-mp4 song.mp3 --fps 24
```

## How It Works

1. **Audio Analysis** - Loads the MP3, extracts metadata (title/artist), and computes per-frame energy levels
2. **Color Selection** - Hashes the filename to determine a unique hue offset for the background colors
3. **Rendering** - Uses OpenGL to render each frame:
   - Background: Animated warped fBM shader with audio-reactive speed
   - Foreground: Spinning vinyl record with label
4. **Encoding** - Streams frames to FFmpeg for H.264 encoding with the original audio

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
