"""Base shader class for vinyl-mp4 background shaders."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import moderngl


@dataclass
class ShaderPass:
    """Represents a single render pass."""

    vertex_source: str
    fragment_source: str


class BaseShader(ABC):
    """Abstract base class for background shaders."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable shader name."""
        pass

    @property
    @abstractmethod
    def main_pass(self) -> ShaderPass:
        """Main fragment shader pass."""
        pass

    @property
    def buffer_pass(self) -> ShaderPass | None:
        """Optional buffer pass (for multi-pass shaders)."""
        return None

    @property
    def needs_noise_texture(self) -> bool:
        """Whether shader requires noise texture."""
        return False

    @property
    def needs_previous_frame(self) -> bool:
        """Whether buffer pass needs previous frame (ping-pong)."""
        return False

    def create_programs(self, ctx: moderngl.Context) -> dict[str, moderngl.Program]:
        """Create shader programs. Returns dict with 'main' and optionally 'buffer'."""
        programs = {}

        # Create main program
        programs["main"] = ctx.program(
            vertex_shader=self.main_pass.vertex_source,
            fragment_shader=self.main_pass.fragment_source,
        )

        # Create buffer program if needed
        if self.buffer_pass is not None:
            programs["buffer"] = ctx.program(
                vertex_shader=self.buffer_pass.vertex_source,
                fragment_shader=self.buffer_pass.fragment_source,
            )

        return programs

    @abstractmethod
    def set_uniforms(
        self,
        program: moderngl.Program,
        time: float,
        energy_low: float,
        energy_mid: float,
        energy_high: float,
        hue_offset: float,
        resolution: tuple[int, int],
    ) -> None:
        """Set shader-specific uniforms for the main pass."""
        pass

    def set_buffer_uniforms(
        self,
        program: moderngl.Program,
        time: float,
        energy_low: float,
        energy_mid: float,
        energy_high: float,
        resolution: tuple[int, int],
        frame_index: int,
    ) -> None:
        """Set shader-specific uniforms for the buffer pass (if any)."""
        pass
