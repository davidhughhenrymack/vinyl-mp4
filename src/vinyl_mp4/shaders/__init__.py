"""Shader package for vinyl-mp4 background shaders."""

from .base import BaseShader, ShaderPass

# Registry will be populated as shaders are added
SHADER_REGISTRY: list[type[BaseShader]] = []

# Color name to hue value mapping (0-1 range)
COLOR_HUES: dict[str, float] = {
    "red": 0.0,
    "orange": 0.08,
    "yellow": 0.17,
    "lime": 0.25,
    "green": 0.33,
    "teal": 0.42,
    "cyan": 0.50,
    "sky": 0.55,
    "blue": 0.67,
    "indigo": 0.72,
    "purple": 0.75,
    "violet": 0.78,
    "magenta": 0.83,
    "pink": 0.92,
}


def get_shader_class(index: int) -> type[BaseShader]:
    """Get shader class by index (wraps around)."""
    if not SHADER_REGISTRY:
        raise RuntimeError("No shaders registered")
    return SHADER_REGISTRY[index % len(SHADER_REGISTRY)]


def get_shader_by_name(name: str) -> type[BaseShader]:
    """Get shader class by name (case-insensitive, partial match)."""
    name_lower = name.lower()
    for shader_class in SHADER_REGISTRY:
        shader_name = shader_class().name.lower()
        # Exact match or partial match
        if name_lower == shader_name or name_lower in shader_name.replace(" ", ""):
            return shader_class
    raise ValueError(f"Unknown shader: {name}. Available: {get_shader_names()}")


def get_shader_names() -> list[str]:
    """Return list of available shader names."""
    return [cls().name for cls in SHADER_REGISTRY]


def get_num_shaders() -> int:
    """Return number of available shaders."""
    return len(SHADER_REGISTRY)


def get_color_names() -> list[str]:
    """Return list of available color names."""
    return list(COLOR_HUES.keys())


def get_hue_from_color(color: str) -> float:
    """Get hue value (0-1) from color name."""
    color_lower = color.lower()
    if color_lower not in COLOR_HUES:
        raise ValueError(f"Unknown color: {color}. Available: {get_color_names()}")
    return COLOR_HUES[color_lower]


def register_shader(shader_class: type[BaseShader]) -> type[BaseShader]:
    """Decorator to register a shader class."""
    SHADER_REGISTRY.append(shader_class)
    return shader_class


# Import shaders to trigger registration
from .fbm_warp import FbmWarpShader  # noqa: E402, F401
from .fbm_warp import VERTEX_SHADER as BACKGROUND_VERTEX_SHADER  # noqa: E402, F401
from .fbm_warp import FRAGMENT_SHADER as BACKGROUND_FRAGMENT_SHADER  # noqa: E402, F401
from .melted_sphere import MeltedSphereShader  # noqa: E402, F401

# Import vinyl shader constants
from .vinyl import VINYL_VERTEX_SHADER, VINYL_FRAGMENT_SHADER  # noqa: E402, F401

__all__ = [
    "BaseShader",
    "ShaderPass",
    "SHADER_REGISTRY",
    "COLOR_HUES",
    "get_shader_class",
    "get_shader_by_name",
    "get_shader_names",
    "get_num_shaders",
    "get_color_names",
    "get_hue_from_color",
    "register_shader",
    "FbmWarpShader",
    "MeltedSphereShader",
    # Legacy exports for backwards compatibility
    "BACKGROUND_VERTEX_SHADER",
    "BACKGROUND_FRAGMENT_SHADER",
    "VINYL_VERTEX_SHADER",
    "VINYL_FRAGMENT_SHADER",
]
