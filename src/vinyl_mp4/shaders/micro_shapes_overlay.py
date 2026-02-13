"""Micro-Shapes Overlay: six 2D shape "micro-shaders" assigned to track groups, overlaid fullscreen.

Shape families:
  - rectangle
  - square
  - circle
  - triangle

Each family is rendered in both outlined and filled variants.

Tracks map to variant groups by trackIndex % 8. Signal drives shape/size; onset drives visible flash.
"""

import moderngl

from .base import BaseShader, ShaderPass
from . import register_shader

VERTEX_SHADER = """
#version 330

in vec2 in_position;
out vec2 v_uv;

void main() {
    v_uv = in_position * 0.5 + 0.5;
    gl_Position = vec4(in_position, 0.0, 1.0);
}
"""

FRAGMENT_SHADER = """
#version 330

uniform float u_time;
uniform vec2 u_resolution;
uniform vec3 u_bg_rgb;
uniform vec3 u_line_rgb;
uniform float u_audio_drive;
uniform float u_group_signal[8];
uniform float u_group_onset[8];

in vec2 v_uv;
out vec4 fragColor;

const float PI = 3.141592654;

mat2 rot2(float a) {
    float c = cos(a);
    float s = sin(a);
    return mat2(c, -s, s, c);
}

// --- Shape 0/1: rectangle (outline and fill)
float shape_rect_outline(vec2 p, float signal, float onset) {
    float hitGrow = 1.0 + 1.2 * pow(clamp(onset, 0.0, 1.0), 0.65);
    float w = (0.12 + 0.30 * signal) * hitGrow;
    float h = (0.06 + 0.22 * signal) * hitGrow;
    float thick = 0.003 + 0.006 * signal + 0.008 * onset;
    vec2 q = abs(p - 0.5);
    vec2 r = vec2(w, h);
    float outer = 1.0 - step(0.0, max(q.x - r.x, q.y - r.y));
    vec2 innerR = max(r - vec2(thick), vec2(0.001));
    float inner = 1.0 - step(0.0, max(q.x - innerR.x, q.y - innerR.y));
    return max(0.0, outer - inner);
}

float shape_rect_fill(vec2 p, float signal, float onset) {
    float hitGrow = 1.0 + 1.0 * pow(clamp(onset, 0.0, 1.0), 0.65);
    float w = (0.10 + 0.28 * signal) * hitGrow;
    float h = (0.05 + 0.20 * signal) * hitGrow;
    vec2 q = abs(p - 0.5);
    float inside = 1.0 - step(0.0, max(q.x - w, q.y - h));
    return inside;
}

// --- Shape 2/3: square (outline and fill)
float shape_square_outline(vec2 p, float signal, float onset) {
    float hitGrow = 1.0 + 1.25 * pow(clamp(onset, 0.0, 1.0), 0.65);
    float s = (0.07 + 0.22 * signal) * hitGrow;
    float thick = 0.003 + 0.006 * signal + 0.008 * onset;
    vec2 q = abs(p - 0.5);
    float outer = 1.0 - step(0.0, max(q.x - s, q.y - s));
    float innerS = max(s - thick, 0.001);
    float inner = 1.0 - step(0.0, max(q.x - innerS, q.y - innerS));
    return max(0.0, outer - inner);
}

float shape_square_fill(vec2 p, float signal, float onset) {
    float hitGrow = 1.0 + 1.05 * pow(clamp(onset, 0.0, 1.0), 0.65);
    float s = (0.06 + 0.20 * signal) * hitGrow;
    vec2 q = abs(p - 0.5);
    return 1.0 - step(0.0, max(q.x - s, q.y - s));
}

// --- Shape 4/5: circle (outline and fill)
float shape_circle_outline(vec2 p, float signal, float onset) {
    vec2 c = vec2(0.5);
    float hitGrow = 1.0 + 1.3 * pow(clamp(onset, 0.0, 1.0), 0.6);
    float r = (0.07 + 0.16 * signal) * hitGrow;
    float d = length(p - c);
    float thick = 0.002 + 0.006 * signal + 0.007 * onset;
    return 1.0 - step(thick, abs(d - r));
}

float shape_circle_fill(vec2 p, float signal, float onset) {
    vec2 c = vec2(0.5);
    float hitGrow = 1.0 + 1.1 * pow(clamp(onset, 0.0, 1.0), 0.6);
    float r = (0.06 + 0.15 * signal) * hitGrow;
    float d = length(p - c);
    return 1.0 - step(r, d);
}

// --- Shape 6/7: triangle (outline and fill)
float shape_triangle_outline(vec2 p, float signal, float onset) {
    float hitGrow = 1.0 + 1.2 * pow(clamp(onset, 0.0, 1.0), 0.65);
    float scale = (0.09 + 0.30 * signal) * hitGrow;
    vec2 c = vec2(0.5);
    vec2 q = (p - c) / scale;
    float k = sqrt(3.0);
    float s = 0.5;
    float d = max(abs(q.x) - s, max(-k * q.y - q.x - s, k * q.y - q.x - s));
    float thick = 0.012 + 0.02 * signal + 0.025 * onset;
    return 1.0 - step(thick, abs(d));
}

float shape_triangle_fill(vec2 p, float signal, float onset) {
    float hitGrow = 1.0 + 1.1 * pow(clamp(onset, 0.0, 1.0), 0.65);
    float scale = (0.08 + 0.27 * signal) * hitGrow;
    vec2 c = vec2(0.5);
    vec2 q = (p - c) / scale;
    float k = sqrt(3.0);
    float s = 0.5;
    float d = max(abs(q.x) - s, max(-k * q.y - q.x - s, k * q.y - q.x - s));
    return 1.0 - step(0.0, d);
}

void main() {
    float aspect = u_resolution.x / u_resolution.y;
    vec2 pFrame = v_uv;
    pFrame.x -= 0.5;
    pFrame.x *= aspect;
    pFrame.x += 0.5;

    vec2 p = pFrame;
    // Break center-lock and symmetry slightly for the whole composition.
    p += vec2(0.04 * sin(u_time * 0.17), 0.035 * cos(u_time * 0.13));

    vec3 bg = u_bg_rgb;
    vec3 acc = bg;
    float alphaAcc = 1.0;
    float maxOnset = 0.0;
    float maxSignal = 0.0;
    for (int i = 0; i < 8; i++) {
        maxOnset = max(maxOnset, u_group_onset[i]);
        maxSignal = max(maxSignal, abs(u_group_signal[i]));
    }
    float activity = max(u_audio_drive, max(maxOnset, maxSignal));
    float visibilityGate = mix(0.10, 1.0, smoothstep(0.04, 0.35, activity));

    for (int g = 0; g < 8; g++) {
        float sig = u_group_signal[g];
        float on = u_group_onset[g];
        float shapeAlpha = 0.0;
        float gf = float(g);
        vec2 pg = p;
        vec2 pgRect = pFrame;
        // Each group gets independent drift + rotation to avoid symmetric overlap.
        pg += vec2(
            0.09 * sin(gf * 1.73 + u_time * 0.29),
            0.08 * cos(gf * 1.21 - u_time * 0.23)
        );
        // Rectangle keeps axis alignment with the 2D frame: translation only, no rotation/shear.
        pgRect += vec2(
            0.09 * sin(gf * 1.73 + u_time * 0.29),
            0.08 * cos(gf * 1.21 - u_time * 0.23)
        );
        vec2 center = vec2(0.48, 0.52) + vec2(0.03 * sin(gf), -0.04 * cos(gf * 0.7));
        pg = (pg - center) * rot2(0.15 * sin(gf + u_time * 0.37) + 0.25 * sig + 0.2 * on) + center;

        if (g == 0) shapeAlpha = shape_rect_outline(pgRect, sig, on);
        else if (g == 1) shapeAlpha = shape_rect_fill(pgRect, sig, on);
        else if (g == 2) shapeAlpha = shape_square_outline(pg, sig, on);
        else if (g == 3) shapeAlpha = shape_square_fill(pg, sig, on);
        else if (g == 4) shapeAlpha = shape_circle_outline(pg, sig, on);
        else if (g == 5) shapeAlpha = shape_circle_fill(pg, sig, on);
        else if (g == 6) shapeAlpha = shape_triangle_outline(pg, sig, on);
        else if (g == 7) shapeAlpha = shape_triangle_fill(pg, sig, on);

        float strength;
        if (g == 0) {
            // Dedicated audio-file element: driven by spectral energy even without ALS note onsets.
            strength = 0.15 + 1.2 * clamp(u_audio_drive, 0.0, 1.0) + 0.25 * on;
        } else {
            // Most elements stay subtle at idle and become strongly visible at note hits.
            float idle = 0.02 + 0.08 * min(1.0, abs(sig));
            float pulse = pow(clamp(on, 0.0, 1.0), 0.65);
            strength = idle + 1.35 * pulse;
        }
        shapeAlpha = shapeAlpha * strength * visibilityGate;

        vec3 shapeColor = (u_line_rgb.x >= 0.0) ? u_line_rgb : vec3(1.0);

        acc = mix(acc, shapeColor, shapeAlpha * (1.0 - alphaAcc * 0.3));
        alphaAcc = alphaAcc * (1.0 - shapeAlpha * 0.85);
    }

    fragColor = vec4(acc, 1.0);
}
"""


@register_shader
class MicroShapesOverlayShader(BaseShader):
    """Four shape families (rect/square/circle/triangle), each as outline+fill overlays."""

    def __init__(self) -> None:
        self.progress: float = 1.0

    @property
    def name(self) -> str:
        return "Micro Shapes"

    @property
    def main_pass(self) -> ShaderPass:
        return ShaderPass(
            vertex_source=VERTEX_SHADER,
            fragment_source=FRAGMENT_SHADER,
        )

    def set_uniforms(
        self,
        program: moderngl.Program,
        time: float,
        energy_low: float,
        energy_mid: float,
        energy_high: float,
        hue_offset: float,
        resolution: tuple[int, int],
        contrast: float = 1.0,
        track_signals: list[float] | None = None,
        *,
        bg_rgb: tuple[float, float, float] | None = None,
        line_rgb: tuple[float, float, float] | None = None,
        track_onsets: list[float] | None = None,
        track_pitches: list[float] | None = None,
    ) -> None:
        """Aggregate tracks into 8 groups (trackIndex % 8), set group signals/onsets."""
        signals = list(track_signals or [])
        onsets = list(track_onsets or [])
        n = max(len(signals), len(onsets))
        group_signal = [0.0] * 8
        group_onset = [0.0] * 8
        for i in range(n):
            g = i % 8
            if i < len(signals):
                group_signal[g] = max(group_signal[g], abs(signals[i]))
            if i < len(onsets):
                group_onset[g] = max(group_onset[g], onsets[i])
        program["u_time"].value = time
        program["u_resolution"].value = resolution
        program["u_bg_rgb"].value = bg_rgb if bg_rgb is not None else (0.0, 0.0, 0.0)
        program["u_line_rgb"].value = line_rgb if line_rgb is not None else (-1.0, 0.0, 0.0)
        audio_drive = max(0.0, min(1.0, 0.5 * energy_low + 0.35 * energy_mid + 0.15 * energy_high))
        program["u_audio_drive"].value = float(audio_drive)
        program["u_group_signal"].value = tuple(group_signal)
        program["u_group_onset"].value = tuple(group_onset)
