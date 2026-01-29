"""Shader package for vinyl-mp4 background shaders."""

from .base import BaseShader, ShaderPass

# Registry will be populated as shaders are added
SHADER_REGISTRY: list[type[BaseShader]] = []


def get_shader_class(index: int) -> type[BaseShader]:
    """Get shader class by index (wraps around)."""
    if not SHADER_REGISTRY:
        raise RuntimeError("No shaders registered")
    return SHADER_REGISTRY[index % len(SHADER_REGISTRY)]


def get_num_shaders() -> int:
    """Return number of available shaders."""
    return len(SHADER_REGISTRY)


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
    "get_shader_class",
    "get_num_shaders",
    "register_shader",
    "FbmWarpShader",
    "MeltedSphereShader",
    # Legacy exports for backwards compatibility
    "BACKGROUND_VERTEX_SHADER",
    "BACKGROUND_FRAGMENT_SHADER",
    "VINYL_VERTEX_SHADER",
    "VINYL_FRAGMENT_SHADER",
]
