"""Tests for shaders module - written BEFORE implementation (TDD)."""

import pytest


class TestBackgroundShader:
    """Tests for background shader."""

    def test_background_shader_compiles(self):
        """GLSL compiles without errors."""
        import moderngl
        from vinyl_mp4.shaders import (
            BACKGROUND_VERTEX_SHADER,
            BACKGROUND_FRAGMENT_SHADER,
        )

        ctx = moderngl.create_standalone_context()
        try:
            # This will raise an exception if shader doesn't compile
            program = ctx.program(
                vertex_shader=BACKGROUND_VERTEX_SHADER,
                fragment_shader=BACKGROUND_FRAGMENT_SHADER,
            )
            assert program is not None
        finally:
            ctx.release()

    def test_background_shader_has_required_uniforms(self):
        """Background shader has required uniforms."""
        import moderngl
        from vinyl_mp4.shaders import (
            BACKGROUND_VERTEX_SHADER,
            BACKGROUND_FRAGMENT_SHADER,
        )

        ctx = moderngl.create_standalone_context()
        try:
            program = ctx.program(
                vertex_shader=BACKGROUND_VERTEX_SHADER,
                fragment_shader=BACKGROUND_FRAGMENT_SHADER,
            )

            # Check required uniforms exist
            assert "u_time" in program
            assert "u_resolution" in program
            assert "u_energy" in program
            assert "u_hue_offset" in program
        finally:
            ctx.release()


class TestVinylShader:
    """Tests for vinyl shader."""

    def test_vinyl_shader_compiles(self):
        """GLSL compiles without errors."""
        import moderngl
        from vinyl_mp4.shaders import VINYL_VERTEX_SHADER, VINYL_FRAGMENT_SHADER

        ctx = moderngl.create_standalone_context()
        try:
            # This will raise an exception if shader doesn't compile
            program = ctx.program(
                vertex_shader=VINYL_VERTEX_SHADER,
                fragment_shader=VINYL_FRAGMENT_SHADER,
            )
            assert program is not None
        finally:
            ctx.release()

    def test_vinyl_shader_has_required_uniforms(self):
        """Vinyl shader has required uniforms."""
        import moderngl
        from vinyl_mp4.shaders import VINYL_VERTEX_SHADER, VINYL_FRAGMENT_SHADER

        ctx = moderngl.create_standalone_context()
        try:
            program = ctx.program(
                vertex_shader=VINYL_VERTEX_SHADER,
                fragment_shader=VINYL_FRAGMENT_SHADER,
            )

            # Check required uniforms exist
            assert "u_time" in program
            assert "u_resolution" in program
            assert "u_label_texture" in program
        finally:
            ctx.release()


class TestShaderConstants:
    """Tests for shader source code constants."""

    def test_shaders_are_strings(self):
        """Shader sources should be non-empty strings."""
        from vinyl_mp4.shaders import (
            BACKGROUND_VERTEX_SHADER,
            BACKGROUND_FRAGMENT_SHADER,
            VINYL_VERTEX_SHADER,
            VINYL_FRAGMENT_SHADER,
        )

        assert isinstance(BACKGROUND_VERTEX_SHADER, str)
        assert isinstance(BACKGROUND_FRAGMENT_SHADER, str)
        assert isinstance(VINYL_VERTEX_SHADER, str)
        assert isinstance(VINYL_FRAGMENT_SHADER, str)

        assert len(BACKGROUND_VERTEX_SHADER) > 0
        assert len(BACKGROUND_FRAGMENT_SHADER) > 0
        assert len(VINYL_VERTEX_SHADER) > 0
        assert len(VINYL_FRAGMENT_SHADER) > 0

    def test_background_shader_contains_fbm(self):
        """Background shader should use fBM (fractal Brownian motion)."""
        from vinyl_mp4.shaders import BACKGROUND_FRAGMENT_SHADER

        # Check for key components from the Shadertoy shader
        assert "fbm" in BACKGROUND_FRAGMENT_SHADER
        assert "noise" in BACKGROUND_FRAGMENT_SHADER
        assert "pattern" in BACKGROUND_FRAGMENT_SHADER

    def test_background_shader_contains_hue_rotation(self):
        """Background shader should include hue rotation logic."""
        from vinyl_mp4.shaders import BACKGROUND_FRAGMENT_SHADER

        # Should have hue offset uniform and HSV conversion
        assert "u_hue_offset" in BACKGROUND_FRAGMENT_SHADER
        # Should convert to HSV, rotate hue, convert back
        assert (
            "rgb2hsv" in BACKGROUND_FRAGMENT_SHADER
            or "hsv" in BACKGROUND_FRAGMENT_SHADER.lower()
        )
