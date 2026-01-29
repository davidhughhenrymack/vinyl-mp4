"""OpenGL headless renderer for vinyl visualization."""

import math
import numpy as np
import moderngl
from PIL import Image, ImageDraw, ImageFont

from vinyl_mp4.shaders import (
    BACKGROUND_VERTEX_SHADER,
    BACKGROUND_FRAGMENT_SHADER,
    VINYL_VERTEX_SHADER,
    VINYL_FRAGMENT_SHADER,
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

    # Truncate long text
    max_chars = 16
    display_title = title[:max_chars] + "..." if len(title) > max_chars else title
    display_artist = artist[:max_chars] + "..." if len(artist) > max_chars else artist

    # Draw artist name (left side of center) - uppercase for Bebas
    artist_text = display_artist.upper()
    artist_bbox = draw.textbbox((0, 0), artist_text, font=font_main)
    artist_width = artist_bbox[2] - artist_bbox[0]
    artist_x = int(size * 0.43) - artist_width
    artist_y = int(size * 0.38)
    draw.text((artist_x, artist_y), artist_text, fill=text_dark, font=font_main)

    # Draw title (right side of center) - uppercase for Bebas
    title_text = display_title.upper()
    title_x = int(size * 0.57)
    title_y = int(size * 0.38)
    draw.text((title_x, title_y), title_text, fill=text_dark, font=font_main)

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
    1. Background: Animated iridescent fBM pattern
    2. Foreground: Spinning vinyl record with label
    """

    def __init__(self, width: int, height: int):
        """Initialize the renderer with given dimensions.

        Args:
            width: Output frame width in pixels.
            height: Output frame height in pixels.
        """
        self.width = width
        self.height = height

        # Create headless OpenGL context
        self.ctx = moderngl.create_standalone_context()

        # Create framebuffer for rendering
        self.fbo = self.ctx.framebuffer(
            color_attachments=[self.ctx.texture((width, height), 4)]
        )

        # Create full-screen quad vertices
        vertices = np.array(
            [
                -1.0,
                -1.0,
                1.0,
                -1.0,
                -1.0,
                1.0,
                1.0,
                1.0,
            ],
            dtype="f4",
        )

        self.vbo = self.ctx.buffer(vertices)

        # Create background shader program
        self.bg_program = self.ctx.program(
            vertex_shader=BACKGROUND_VERTEX_SHADER,
            fragment_shader=BACKGROUND_FRAGMENT_SHADER,
        )
        self.bg_vao = self.ctx.vertex_array(
            self.bg_program,
            [(self.vbo, "2f", "in_position")],
        )

        # Create vinyl shader program
        self.vinyl_program = self.ctx.program(
            vertex_shader=VINYL_VERTEX_SHADER,
            fragment_shader=VINYL_FRAGMENT_SHADER,
        )
        self.vinyl_vao = self.ctx.vertex_array(
            self.vinyl_program,
            [(self.vbo, "2f", "in_position")],
        )

        # Create default label texture (higher resolution for quality)
        self.label_size = 1024
        self.label_texture = self.ctx.texture((self.label_size, self.label_size), 4)
        default_label = create_label_texture(
            "Unknown", "Unknown", track_name="", size=self.label_size
        )
        self.label_texture.write(default_label.tobytes())
        self.label_texture.use(location=0)

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
        self, time: float, energy_low: float, energy_high: float, hue_offset: float
    ) -> bytes:
        """Render a single frame.

        Args:
            time: Current playback time in seconds.
            energy_low: Low frequency (bass) energy level (0.0-1.0).
            energy_high: High frequency (treble) energy level (0.0-1.0).
            hue_offset: Hue rotation for background colors (0.0-1.0).

        Returns:
            Raw RGBA pixel data as bytes.
        """
        self.fbo.use()
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)

        # Enable blending for transparency
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

        # Render background with frequency band energies
        self.bg_program["u_time"].value = time
        self.bg_program["u_resolution"].value = (float(self.width), float(self.height))
        self.bg_program["u_energy_low"].value = energy_low
        self.bg_program["u_energy_high"].value = energy_high
        self.bg_program["u_hue_offset"].value = hue_offset
        self.bg_vao.render(moderngl.TRIANGLE_STRIP)

        # Render vinyl on top
        self.vinyl_program["u_time"].value = time
        self.vinyl_program["u_resolution"].value = (
            float(self.width),
            float(self.height),
        )
        self.label_texture.use(location=0)
        self.vinyl_program["u_label_texture"].value = 0
        self.vinyl_vao.render(moderngl.TRIANGLE_STRIP)

        # Read pixels
        return self.fbo.color_attachments[0].read()

    def release(self) -> None:
        """Release OpenGL resources."""
        self.fbo.release()
        self.vbo.release()
        self.bg_vao.release()
        self.vinyl_vao.release()
        self.bg_program.release()
        self.vinyl_program.release()
        self.label_texture.release()
        self.ctx.release()
