"""Tests for renderer module - written BEFORE implementation (TDD)."""

import pytest
import numpy as np


class TestVinylRenderer:
    """Tests for VinylRenderer class."""

    def test_renderer_creates_context(self):
        """Headless OpenGL context initializes."""
        from vinyl_mp4.renderer import VinylRenderer

        renderer = VinylRenderer(width=640, height=480)
        try:
            assert renderer.ctx is not None
            assert renderer.width == 640
            assert renderer.height == 480
        finally:
            renderer.release()

    def test_render_frame_returns_correct_size(self):
        """Output is width * height * 4 bytes (RGBA)."""
        from vinyl_mp4.renderer import VinylRenderer

        width, height = 320, 240
        renderer = VinylRenderer(width=width, height=height)
        try:
            frame = renderer.render_frame(time=0.0, energy_low=0.5, energy_mid=0.5, energy_high=0.5, hue_offset=0.0)

            expected_size = width * height * 4  # RGBA
            assert len(frame) == expected_size
        finally:
            renderer.release()

    def test_render_frame_not_all_black(self):
        """Frame contains visible content."""
        from vinyl_mp4.renderer import VinylRenderer

        renderer = VinylRenderer(width=320, height=240)
        try:
            frame = renderer.render_frame(time=0.0, energy_low=0.5, energy_mid=0.5, energy_high=0.5, hue_offset=0.0)

            # Convert to numpy array and check not all zeros
            pixels = np.frombuffer(frame, dtype=np.uint8)
            # At least some pixels should be non-zero
            assert np.sum(pixels) > 0
        finally:
            renderer.release()

    def test_render_frame_with_different_energy(self):
        """Different energy values produce different frames."""
        from vinyl_mp4.renderer import VinylRenderer

        renderer = VinylRenderer(width=320, height=240)
        try:
            frame_low = renderer.render_frame(time=0.0, energy_low=0.1, energy_mid=0.1, energy_high=0.1, hue_offset=0.0)
            frame_high = renderer.render_frame(time=0.0, energy_low=0.9, energy_mid=0.9, energy_high=0.9, hue_offset=0.0)

            # Frames should be different (energy affects the shader)
            # Note: with same time=0, they might be similar but the effective_time differs
            # Let's check at a later time where energy effect is more visible
            frame_low_t1 = renderer.render_frame(time=1.0, energy_low=0.1, energy_mid=0.1, energy_high=0.1, hue_offset=0.0)
            frame_high_t1 = renderer.render_frame(time=1.0, energy_low=0.9, energy_mid=0.9, energy_high=0.9, hue_offset=0.0)

            # They should differ
            assert frame_low_t1 != frame_high_t1
        finally:
            renderer.release()

    def test_vinyl_rotation_changes_with_time(self):
        """Different times produce different frames (vinyl rotates)."""
        from vinyl_mp4.renderer import VinylRenderer

        renderer = VinylRenderer(width=320, height=240)
        try:
            frame_t0 = renderer.render_frame(time=0.0, energy_low=0.5, energy_mid=0.5, energy_high=0.5, hue_offset=0.0)
            frame_t1 = renderer.render_frame(time=1.0, energy_low=0.5, energy_mid=0.5, energy_high=0.5, hue_offset=0.0)

            # Frames at different times should be different
            assert frame_t0 != frame_t1
        finally:
            renderer.release()

    def test_render_with_label_texture(self):
        """Renderer works with label texture set."""
        from vinyl_mp4.renderer import VinylRenderer
        from PIL import Image

        renderer = VinylRenderer(width=320, height=240)
        try:
            # Create a simple test label image
            label_img = Image.new("RGBA", (256, 256), color=(255, 128, 0, 255))
            renderer.set_label_texture(label_img)

            frame = renderer.render_frame(time=0.0, energy_low=0.5, energy_mid=0.5, energy_high=0.5, hue_offset=0.0)

            # Should still produce a valid frame
            assert len(frame) == 320 * 240 * 4
        finally:
            renderer.release()

    def test_different_hue_offset_changes_colors(self):
        """Different hue offsets produce different colored frames."""
        from vinyl_mp4.renderer import VinylRenderer

        renderer = VinylRenderer(width=320, height=240)
        try:
            frame_hue0 = renderer.render_frame(time=0.0, energy_low=0.5, energy_mid=0.5, energy_high=0.5, hue_offset=0.0)
            frame_hue05 = renderer.render_frame(time=0.0, energy_low=0.5, energy_mid=0.5, energy_high=0.5, hue_offset=0.5)

            # Different hue offsets should produce different frames
            assert frame_hue0 != frame_hue05
        finally:
            renderer.release()


class TestLabelGeneration:
    """Tests for label texture generation."""

    def test_create_label_texture(self):
        """create_label_texture produces valid PIL Image."""
        from vinyl_mp4.renderer import create_label_texture
        from PIL import Image

        label = create_label_texture("Test Song", "Test Artist", size=256)

        assert isinstance(label, Image.Image)
        assert label.size == (256, 256)
        assert label.mode == "RGBA"

    def test_create_label_texture_has_text(self):
        """Label texture contains non-uniform pixels (text rendered)."""
        from vinyl_mp4.renderer import create_label_texture
        import numpy as np

        label = create_label_texture("Test Song", "Test Artist", size=256)
        pixels = np.array(label)

        # Should have some variation (not all same color)
        # Check that not all pixels are identical
        assert pixels.std() > 0

    def test_create_label_texture_handles_long_text(self):
        """Label handles long title/artist names."""
        from vinyl_mp4.renderer import create_label_texture

        long_title = "This Is A Very Long Song Title That Should Be Handled"
        long_artist = "Artist Name With Many Words In It"

        # Should not raise an exception
        label = create_label_texture(long_title, long_artist, size=256)
        assert label is not None


class TestMultiShaderRenderer:
    """Tests for multi-shader renderer functionality."""

    def test_renderer_accepts_shader_index(self):
        """Renderer initializes with different shader indices."""
        from vinyl_mp4.renderer import VinylRenderer

        for i in range(2):
            renderer = VinylRenderer(width=320, height=240, shader_index=i)
            try:
                assert renderer.bg_shader is not None
            finally:
                renderer.release()

    def test_renderer_shader_index_wraps(self):
        """Renderer handles index wrapping."""
        from vinyl_mp4.renderer import VinylRenderer
        from vinyl_mp4.shaders import get_num_shaders

        num_shaders = get_num_shaders()

        # Index beyond num_shaders should wrap
        renderer_wrapped = VinylRenderer(width=320, height=240, shader_index=num_shaders)
        renderer_zero = VinylRenderer(width=320, height=240, shader_index=0)
        try:
            assert type(renderer_wrapped.bg_shader) == type(renderer_zero.bg_shader)
        finally:
            renderer_wrapped.release()
            renderer_zero.release()

    def test_noise_texture_created_when_needed(self):
        """Noise texture created for shaders that need it."""
        from vinyl_mp4.renderer import VinylRenderer

        # Shader 0 (FBM Warp) doesn't need noise
        renderer0 = VinylRenderer(width=320, height=240, shader_index=0)
        assert renderer0.noise_texture is None
        renderer0.release()

        # Shader 1 (Melted Sphere) needs noise
        renderer1 = VinylRenderer(width=320, height=240, shader_index=1)
        assert renderer1.noise_texture is not None
        renderer1.release()

    def test_different_shaders_are_different_types(self):
        """Different shader indices use different shader classes."""
        from vinyl_mp4.renderer import VinylRenderer

        renderer0 = VinylRenderer(width=320, height=240, shader_index=0)
        renderer1 = VinylRenderer(width=320, height=240, shader_index=1)

        try:
            # Different shaders should be different types
            assert type(renderer0.bg_shader) != type(renderer1.bg_shader)

            # Both should produce valid output
            frame0 = renderer0.render_frame(
                time=0.5, energy_low=0.5, energy_mid=0.5, energy_high=0.5, hue_offset=0.0
            )
            frame1 = renderer1.render_frame(
                time=0.5, energy_low=0.5, energy_mid=0.5, energy_high=0.5, hue_offset=0.0
            )

            assert len(frame0) == 320 * 240 * 4
            assert len(frame1) == 320 * 240 * 4
        finally:
            renderer0.release()
            renderer1.release()

    def test_shader_name_accessible(self):
        """Renderer exposes shader name."""
        from vinyl_mp4.renderer import VinylRenderer

        renderer0 = VinylRenderer(width=320, height=240, shader_index=0)
        renderer1 = VinylRenderer(width=320, height=240, shader_index=1)

        try:
            assert renderer0.bg_shader.name == "FBM Warp"
            assert renderer1.bg_shader.name == "Melted Sphere"
        finally:
            renderer0.release()
            renderer1.release()
