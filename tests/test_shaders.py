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
            assert "u_energy_low" in program
            assert "u_energy_mid" in program
            assert "u_energy_high" in program
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


class TestShaderRegistry:
    """Tests for shader registry and multi-shader support."""

    def test_registry_not_empty(self):
        """Shader registry has at least one shader."""
        from vinyl_mp4.shaders import SHADER_REGISTRY

        assert len(SHADER_REGISTRY) > 0

    def test_registry_has_all_shaders(self):
        """Registry contains all expected shaders."""
        from vinyl_mp4.shaders import (
            SHADER_REGISTRY,
            FbmWarpShader,
            MeltedSphereShader,
            AuroraWaveShader,
            RetroTerrainShader,
        )

        shader_classes = [s for s in SHADER_REGISTRY]
        assert FbmWarpShader in shader_classes
        assert MeltedSphereShader in shader_classes
        assert AuroraWaveShader in shader_classes
        assert RetroTerrainShader in shader_classes

    def test_all_shaders_compile(self):
        """All registered shaders compile successfully."""
        import moderngl
        from vinyl_mp4.shaders import SHADER_REGISTRY

        ctx = moderngl.create_standalone_context()
        try:
            for shader_class in SHADER_REGISTRY:
                shader = shader_class()
                programs = shader.create_programs(ctx)
                assert "main" in programs
                # Clean up programs
                for prog in programs.values():
                    prog.release()
        finally:
            ctx.release()

    def test_get_shader_class_returns_correct_type(self):
        """get_shader_class returns shader class by index."""
        from vinyl_mp4.shaders import (
            get_shader_class,
            FbmWarpShader,
            MeltedSphereShader,
            AuroraWaveShader,
        )

        assert get_shader_class(0) == FbmWarpShader
        assert get_shader_class(1) == MeltedSphereShader
        assert get_shader_class(2) == AuroraWaveShader

    def test_get_shader_class_wraps_index(self):
        """Index wraps around registry length."""
        from vinyl_mp4.shaders import get_shader_class, get_num_shaders

        num = get_num_shaders()
        assert get_shader_class(0) == get_shader_class(num)
        assert get_shader_class(1) == get_shader_class(num + 1)

    def test_get_num_shaders_returns_registry_length(self):
        """get_num_shaders returns correct count."""
        from vinyl_mp4.shaders import get_num_shaders, SHADER_REGISTRY

        assert get_num_shaders() == len(SHADER_REGISTRY)
        assert get_num_shaders() >= 3  # At least three shaders


class TestMeltedSphereShader:
    """Tests for the Melted Sphere shader."""

    def test_shader_compiles(self):
        """Melted sphere main shader compiles."""
        import moderngl
        from vinyl_mp4.shaders import MeltedSphereShader

        ctx = moderngl.create_standalone_context()
        try:
            shader = MeltedSphereShader()
            programs = shader.create_programs(ctx)
            assert "main" in programs
        finally:
            ctx.release()

    def test_needs_noise_texture_true(self):
        """Shader reports needing noise texture."""
        from vinyl_mp4.shaders import MeltedSphereShader

        shader = MeltedSphereShader()
        assert shader.needs_noise_texture is True

    def test_has_audio_uniforms(self):
        """Shader has energy uniforms for audio reactivity."""
        import moderngl
        from vinyl_mp4.shaders import MeltedSphereShader

        ctx = moderngl.create_standalone_context()
        try:
            shader = MeltedSphereShader()
            programs = shader.create_programs(ctx)
            program = programs["main"]

            # Check audio reactivity uniforms
            assert "u_energy_low" in program
            assert "u_energy_mid" in program
            assert "u_energy_high" in program
            assert "u_hue_offset" in program
        finally:
            ctx.release()

    def test_shader_name(self):
        """Shader has correct name."""
        from vinyl_mp4.shaders import MeltedSphereShader

        shader = MeltedSphereShader()
        assert shader.name == "Melted Sphere"


class TestFbmWarpShader:
    """Tests for the FBM Warp shader."""

    def test_shader_compiles(self):
        """FBM warp shader compiles."""
        import moderngl
        from vinyl_mp4.shaders import FbmWarpShader

        ctx = moderngl.create_standalone_context()
        try:
            shader = FbmWarpShader()
            programs = shader.create_programs(ctx)
            assert "main" in programs
        finally:
            ctx.release()

    def test_does_not_need_noise_texture(self):
        """FBM shader does not need noise texture."""
        from vinyl_mp4.shaders import FbmWarpShader

        shader = FbmWarpShader()
        assert shader.needs_noise_texture is False

    def test_shader_name(self):
        """Shader has correct name."""
        from vinyl_mp4.shaders import FbmWarpShader

        shader = FbmWarpShader()
        assert shader.name == "FBM Warp"


class TestAuroraWaveShader:
    """Tests for the Aurora Wave shader."""

    def test_shader_compiles(self):
        """Aurora wave shader compiles."""
        import moderngl
        from vinyl_mp4.shaders import AuroraWaveShader

        ctx = moderngl.create_standalone_context()
        try:
            shader = AuroraWaveShader()
            programs = shader.create_programs(ctx)
            assert "main" in programs
        finally:
            ctx.release()

    def test_does_not_need_noise_texture(self):
        """Aurora wave shader does not need noise texture."""
        from vinyl_mp4.shaders import AuroraWaveShader

        shader = AuroraWaveShader()
        assert shader.needs_noise_texture is False

    def test_shader_name(self):
        """Shader has correct name."""
        from vinyl_mp4.shaders import AuroraWaveShader

        shader = AuroraWaveShader()
        assert shader.name == "Aurora Wave"

    def test_has_audio_uniforms(self):
        """Shader has energy uniforms for audio reactivity."""
        import moderngl
        from vinyl_mp4.shaders import AuroraWaveShader

        ctx = moderngl.create_standalone_context()
        try:
            shader = AuroraWaveShader()
            programs = shader.create_programs(ctx)
            program = programs["main"]

            # Check audio reactivity uniforms
            assert "u_energy_low" in program
            assert "u_energy_mid" in program
            assert "u_energy_high" in program
            assert "u_hue_offset" in program
        finally:
            ctx.release()


class TestRetroTerrainShader:
    """Tests for the Retro Terrain shader."""

    def test_shader_compiles(self):
        """Retro terrain shader compiles."""
        import moderngl
        from vinyl_mp4.shaders import RetroTerrainShader

        ctx = moderngl.create_standalone_context()
        try:
            shader = RetroTerrainShader()
            programs = shader.create_programs(ctx)
            assert "main" in programs
        finally:
            ctx.release()

    def test_does_not_need_noise_texture(self):
        """Retro terrain shader does not need noise texture."""
        from vinyl_mp4.shaders import RetroTerrainShader

        shader = RetroTerrainShader()
        assert shader.needs_noise_texture is False

    def test_shader_name(self):
        """Shader has correct name."""
        from vinyl_mp4.shaders import RetroTerrainShader

        shader = RetroTerrainShader()
        assert shader.name == "Retro Terrain"

    def test_has_audio_uniforms(self):
        """Shader has energy uniforms for audio reactivity."""
        import moderngl
        from vinyl_mp4.shaders import RetroTerrainShader

        ctx = moderngl.create_standalone_context()
        try:
            shader = RetroTerrainShader()
            programs = shader.create_programs(ctx)
            program = programs["main"]

            # Check audio reactivity uniforms
            assert "u_energy_low" in program
            assert "u_energy_mid" in program
            assert "u_energy_high" in program
            assert "u_hue_offset" in program
            assert "u_track_signal_count" in program
            assert "u_track_signals" in program
        finally:
            ctx.release()
