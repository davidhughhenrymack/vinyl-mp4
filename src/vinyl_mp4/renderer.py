"""OpenGL headless renderer for vinyl visualization."""

import math
import numpy as np
import moderngl
from PIL import Image, ImageDraw, ImageFont

from vinyl_mp4.shaders import (
    VINYL_VERTEX_SHADER,
    VINYL_FRAGMENT_SHADER,
    get_shader_class,
    BaseShader,
)


# Font paths to try (in order of preference)
FONT_PATHS_BOLD = [
    "/Users/dmackparty/Library/Fonts/BebasNeue-Bold.otf",
    "/Users/dmackparty/Library/Fonts/BebasNeue-Regular.otf",
    "/Users/dmackparty/Library/Fonts/Montserrat-Bold.ttf",
    "/Users/dmackparty/Library/Fonts/Roboto-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

FONT_PATHS_REGULAR = [
    "/Users/dmackparty/Library/Fonts/BebasNeue-Regular.otf",
    "/Users/dmackparty/Library/Fonts/Montserrat-Regular.ttf",
    "/Users/dmackparty/Library/Fonts/Roboto-Regular.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

FONT_PATHS_LIGHT = [
    "/Users/dmackparty/Library/Fonts/BebasNeue-Light.otf",
    "/Users/dmackparty/Library/Fonts/Montserrat-Light.ttf",
    "/Users/dmackparty/Library/Fonts/Roboto-Light.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

# Elegant fonts for curved rim text
FONT_PATHS_RIM = [
    "/Users/dmackparty/Library/Fonts/Raleway-Medium.ttf",
    "/Users/dmackparty/Library/Fonts/Cabin-Medium.ttf",
    "/Users/dmackparty/Library/Fonts/Lato-Regular.ttf",
    "/Users/dmackparty/Library/Fonts/Montserrat-Medium.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _load_font(font_paths: list[str], size: int) -> ImageFont.FreeTypeFont:
    """Try to load a font from a list of paths."""
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _draw_curved_text(
    draw: ImageDraw.Draw,
    text: str,
    center: tuple[int, int],
    radius: float,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    start_angle: float = 180,
    direction: int = 1,
) -> None:
    """Draw text along a circular arc.

    Args:
        draw: ImageDraw object
        text: Text to draw
        center: Center point (x, y)
        radius: Radius of the arc
        font: Font to use
        fill: Text color (RGBA)
        start_angle: Starting angle in degrees (0 = right, 90 = bottom, 180 = left)
        direction: 1 for clockwise, -1 for counter-clockwise
    """
    # Calculate total arc length needed for text
    char_angles = []
    for char in text:
        bbox = font.getbbox(char)
        char_width = bbox[2] - bbox[0]
        # Convert pixel width to angle (arc_length = radius * angle_in_radians)
        angle = (char_width / radius) * (180 / math.pi)
        char_angles.append(angle)

    # Add spacing between characters
    spacing_angle = 1.2  # degrees
    total_angle = sum(char_angles) + spacing_angle * (len(text) - 1)

    # Start from center of the text arc
    current_angle = start_angle - (direction * total_angle / 2)

    cx, cy = center

    for i, char in enumerate(text):
        # Calculate position on circle
        angle_rad = math.radians(current_angle)
        x = cx + radius * math.cos(angle_rad)
        y = cy + radius * math.sin(angle_rad)

        # Create a small image for this character
        bbox = font.getbbox(char)
        char_width = bbox[2] - bbox[0]
        char_height = bbox[3] - bbox[1]

        char_img = Image.new("RGBA", (char_width + 10, char_height + 10), (0, 0, 0, 0))
        char_draw = ImageDraw.Draw(char_img)
        char_draw.text((5, 5 - bbox[1]), char, fill=fill, font=font)

        # Rotate character so its top points outward from the circle center
        # Text is drawn at bottom (90°) and flipped to top for OpenGL
        rotation = 450 - current_angle  # (270 - current_angle + 180)
        char_img = char_img.rotate(rotation, expand=True, resample=Image.BICUBIC)

        # Paste at position (centered on the point)
        paste_x = int(x - char_img.width / 2)
        paste_y = int(y - char_img.height / 2)

        # Paste with alpha compositing
        draw._image.paste(char_img, (paste_x, paste_y), char_img)

        # Move to next character position
        current_angle += direction * (char_angles[i] + spacing_angle)


def create_label_texture(
    title: str, artist: str, track_name: str = "", size: int = 1024
) -> Image.Image:
    """Create a circular label texture with vintage vinyl aesthetic.

    Style inspired by classic record labels with cream background,
    orange center stripe, and bold typography.

    Args:
        title: Song title to display.
        artist: Artist name to display.
        track_name: Track name for curved text around rim.
        size: Size of the square texture in pixels.

    Returns:
        PIL Image with RGBA mode containing the rendered label.
    """
    # Create image with transparent background
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Colors - vintage cream and warm orange
    cream = (245, 240, 225, 255)
    orange = (210, 140, 60, 255)
    text_dark = (35, 35, 35, 255)

    center = size // 2

    # Draw circular background for label (no margin - extends to edge)
    draw.ellipse([0, 0, size, size], fill=cream)

    # Draw orange vertical stripe through center (rotationally symmetric)
    # Stripe extends equally above and below center
    stripe_width = int(size * 0.10)
    stripe_left = (size - stripe_width) // 2
    stripe_extent = int(size * 0.22)  # How far from center in each direction
    stripe_top = center - stripe_extent
    stripe_bottom = center + stripe_extent
    draw.rectangle(
        [stripe_left, stripe_top, stripe_left + stripe_width, stripe_bottom],
        fill=orange,
    )

    # Load fonts
    font_main = _load_font(FONT_PATHS_BOLD, int(size * 0.065))
    font_logo = _load_font(FONT_PATHS_BOLD, int(size * 0.10))
    font_curved = _load_font(FONT_PATHS_RIM, int(size * 0.038))

    # Maximum width for text (from edge of stripe to near edge of label)
    max_text_width = int(size * 0.32)
    line_height = int(size * 0.07)

    # Helper to wrap text to fit width
    def wrap_text(text: str, font, max_width: int) -> list[str]:
        """Wrap text to fit within max_width, returns list of lines."""
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        # If a single word is too long, truncate it
        final_lines = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            if bbox[2] - bbox[0] > max_width:
                # Truncate with ellipsis
                while len(line) > 3:
                    line = line[:-1]
                    test = line + "..."
                    bbox = draw.textbbox((0, 0), test, font=font)
                    if bbox[2] - bbox[0] <= max_width:
                        line = test
                        break
            final_lines.append(line)

        return final_lines[:3]  # Max 3 lines

    # Draw artist name (left side of center) - uppercase, right-aligned
    artist_text = artist.upper()
    artist_lines = wrap_text(artist_text, font_main, max_text_width)
    artist_x_right = int(size * 0.43)  # Right edge of artist text area
    artist_y = int(size * 0.38)
    for i, line in enumerate(artist_lines):
        bbox = draw.textbbox((0, 0), line, font=font_main)
        line_width = bbox[2] - bbox[0]
        draw.text(
            (artist_x_right - line_width, artist_y + i * line_height),
            line,
            fill=text_dark,
            font=font_main,
        )

    # Draw title (right side of center) - uppercase, left-aligned, one word per line
    # Split on whitespace and hyphens, keeping hyphens attached
    title_text = title.upper()
    # Split by spaces first, then split hyphenated words
    title_words = []
    for part in title_text.split():
        if "-" in part:
            # Split hyphenated words, e.g. "OUT-OF-MY-HEAD" -> ["OUT", "OF", "MY", "HEAD"]
            title_words.extend(part.split("-"))
        else:
            title_words.append(part)

    title_x = int(size * 0.57)
    title_y = int(size * 0.38)
    for i, word in enumerate(title_words):
        draw.text(
            (title_x, title_y + i * line_height), word, fill=text_dark, font=font_main
        )

    # Draw "DM" logo - horizontally centered, above the vertical stripe (after OpenGL flip)
    logo_text = "DM"
    logo_bbox = draw.textbbox((0, 0), logo_text, font=font_logo)
    logo_width = logo_bbox[2] - logo_bbox[0]
    logo_x = (size - logo_width) // 2  # Horizontally centered
    logo_y = int(size * 0.76)  # Near bottom, appears at top after OpenGL flip
    draw.text((logo_x, logo_y), logo_text, fill=text_dark, font=font_logo)

    # Draw curved track name around the rim
    if track_name:
        # Truncate if too long (curved text has limited space)
        max_curved_chars = 35
        curved_text = track_name.upper()
        if len(curved_text) > max_curved_chars:
            curved_text = curved_text[: max_curved_chars - 3] + "..."

        # Add some decorative dots
        curved_text = f"• {curved_text} •"

        # Draw at the outer rim of the label (at bottom, will flip to top for OpenGL)
        rim_radius = size * 0.44
        _draw_curved_text(
            draw,
            curved_text,
            (center, center),
            rim_radius,
            font_curved,
            text_dark,
            start_angle=90,  # Bottom of image, appears at top after OpenGL flip
            direction=-1,  # Counter-clockwise so text reads left-to-right after flip
        )

    # Draw center spindle hole (transparent)
    hole_radius = int(size * 0.025)
    draw.ellipse(
        [
            center - hole_radius,
            center - hole_radius,
            center + hole_radius,
            center + hole_radius,
        ],
        fill=(0, 0, 0, 0),
    )

    # Draw subtle ring around the hole
    ring_radius = int(size * 0.04)
    draw.ellipse(
        [
            center - ring_radius,
            center - ring_radius,
            center + ring_radius,
            center + ring_radius,
        ],
        outline=(180, 175, 165, 255),
        width=2,
    )

    return img


class VinylRenderer:
    """Headless OpenGL renderer for vinyl visualization.

    Renders a two-layer visualization:
    1. Background: Animated shader (selectable from registry)
    2. Foreground: Spinning vinyl record with label

    Optimized for high throughput with:
    - Pre-allocated output buffer for fast pixel readback
    - Cached uniform locations
    - Shader class-based rendering
    """

    def __init__(
        self,
        width: int,
        height: int,
        shader_index: int = 0,
        vinyl_scale: float = 1.0,
        vinyl_offset_x: float = 0.0,
        contrast: float = 1.0,
    ):
        """Initialize the renderer with given dimensions.

        Args:
            width: Output frame width in pixels.
            height: Output frame height in pixels.
            shader_index: Index of background shader to use (wraps around).
            vinyl_scale: Vinyl size multiplier (1.0 to 2.0).
            vinyl_offset_x: Horizontal offset in vinyl radii (-1.0 to 1.0).
            contrast: Color contrast level (0.7-1.3), only used by FBM Warp shader.
        """
        self.width = width
        self.height = height
        self.vinyl_scale = vinyl_scale
        self.vinyl_offset_x = vinyl_offset_x
        self.contrast = contrast
        self.frame_size = width * height * 4  # RGBA

        # Create headless OpenGL context with explicit backend selection
        self.ctx = moderngl.create_standalone_context()

        # Enable garbage collection optimization
        self.ctx.gc_mode = "context_gc"

        # Create texture-based framebuffer for rendering
        self.fbo_texture = self.ctx.texture((width, height), 4)
        self.fbo = self.ctx.framebuffer(color_attachments=[self.fbo_texture])

        # Pre-allocate output buffer for async-style reads
        self.output_buffer = self.ctx.buffer(reserve=self.frame_size)

        # Create full-screen quad vertices
        vertices = np.array([-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0], dtype="f4")
        self.vbo = self.ctx.buffer(vertices)

        # Instantiate selected background shader
        shader_class = get_shader_class(shader_index)
        self.bg_shader: BaseShader = shader_class()

        # Create noise texture if shader needs it
        self.noise_texture = None
        if self.bg_shader.needs_noise_texture:
            self.noise_texture = self._create_noise_texture(256, 256)

        # Create background shader programs
        self.bg_programs = self.bg_shader.create_programs(self.ctx)
        self.bg_program = self.bg_programs["main"]
        self.bg_vao = self.ctx.vertex_array(
            self.bg_program,
            [(self.vbo, "2f", "in_position")],
        )

        # Bind noise texture if available and shader has the uniform
        if self.noise_texture is not None and "u_noise_texture" in self.bg_program:
            self.noise_texture.use(location=1)
            self.bg_program["u_noise_texture"].value = 1

        # Create vinyl shader program
        self.vinyl_program = self.ctx.program(
            vertex_shader=VINYL_VERTEX_SHADER,
            fragment_shader=VINYL_FRAGMENT_SHADER,
        )
        self.vinyl_vao = self.ctx.vertex_array(
            self.vinyl_program,
            [(self.vbo, "2f", "in_position")],
        )

        # Cache uniform locations for vinyl shader
        self._vinyl_u_time = self.vinyl_program["u_time"]
        self._vinyl_u_resolution = self.vinyl_program["u_resolution"]
        self._vinyl_u_label_texture = self.vinyl_program["u_label_texture"]
        self._vinyl_u_scale = self.vinyl_program["u_vinyl_scale"]
        self._vinyl_u_offset_x = self.vinyl_program["u_vinyl_offset_x"]

        # Set static uniforms once
        self._vinyl_u_resolution.value = (float(width), float(height))
        self._vinyl_u_label_texture.value = 0
        self._vinyl_u_scale.value = self.vinyl_scale
        self._vinyl_u_offset_x.value = self.vinyl_offset_x

        # Create label texture
        self.label_size = 1024
        self.label_texture = self.ctx.texture((self.label_size, self.label_size), 4)
        self.label_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        default_label = create_label_texture(
            "2026", "DMACK", track_name="", size=self.label_size
        )
        self.label_texture.write(default_label.tobytes())

        # Bind label texture once (it doesn't change)
        self.label_texture.use(location=0)

        # Enable blending once (we always use it)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

        # Use the framebuffer
        self.fbo.use()

    def _create_noise_texture(self, width: int, height: int) -> moderngl.Texture:
        """Create a noise texture for shaders that need it.

        Args:
            width: Texture width.
            height: Texture height.

        Returns:
            OpenGL texture containing random RGBA values.
        """
        # Generate random noise data
        noise_data = np.random.randint(0, 256, (height, width, 4), dtype=np.uint8)
        texture = self.ctx.texture((width, height), 4, noise_data.tobytes())
        texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        texture.repeat_x = True
        texture.repeat_y = True
        return texture

    def set_label_texture(self, image: Image.Image) -> None:
        """Set the vinyl label texture from a PIL Image.

        Args:
            image: PIL Image in RGBA mode to use as label.
        """
        # Ensure RGBA mode
        if image.mode != "RGBA":
            image = image.convert("RGBA")

        # Resize if needed
        if image.size != (self.label_size, self.label_size):
            image = image.resize(
                (self.label_size, self.label_size), Image.Resampling.LANCZOS
            )

        # Flip vertically for OpenGL
        image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        self.label_texture.write(image.tobytes())

    def render_frame(
        self,
        time: float,
        energy_low: float,
        energy_mid: float,
        energy_high: float,
        hue_offset: float,
    ) -> bytes:
        """Render a single frame.

        Args:
            time: Current playback time in seconds.
            energy_low: Low frequency (bass) energy level (0.0-1.0).
            energy_mid: Mid frequency energy level (0.0-1.0).
            energy_high: High frequency (treble) energy level (0.0-1.0).
            hue_offset: Hue rotation for background colors (0.0-1.0).

        Returns:
            Raw RGBA pixel data as bytes.
        """
        # Clear framebuffer
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)

        # Render background using shader class
        self.bg_shader.set_uniforms(
            self.bg_program,
            time,
            energy_low,
            energy_mid,
            energy_high,
            hue_offset,
            (self.width, self.height),
            self.contrast,
        )
        self.bg_vao.render(moderngl.TRIANGLE_STRIP)

        # Render vinyl - only set dynamic uniform
        self._vinyl_u_time.value = time
        self.vinyl_vao.render(moderngl.TRIANGLE_STRIP)

        # Read pixels from framebuffer color attachment
        return self.fbo.color_attachments[0].read()

    def release(self) -> None:
        """Release OpenGL resources."""
        self.fbo.release()
        self.fbo_texture.release()
        self.output_buffer.release()
        self.vbo.release()
        self.bg_vao.release()
        self.vinyl_vao.release()
        for prog in self.bg_programs.values():
            prog.release()
        self.vinyl_program.release()
        self.label_texture.release()
        if self.noise_texture is not None:
            self.noise_texture.release()
        self.ctx.release()
