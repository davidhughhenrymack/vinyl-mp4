"""FBM Warp background shader - fractal Brownian motion with domain warping."""

import moderngl

from .base import BaseShader, ShaderPass
from . import register_shader


# Simple vertex shader for full-screen quad
VERTEX_SHADER = """
#version 330

in vec2 in_position;
out vec2 v_uv;

void main() {
    v_uv = in_position * 0.5 + 0.5;
    gl_Position = vec4(in_position, 0.0, 1.0);
}
"""

# Background fragment shader - Based on Shadertoy tdG3Rd "Base warp fBM"
# with added hue rotation support for filename-based color variation
# Uses separate low/high frequency energy bands for smooth audio reactivity
FRAGMENT_SHADER = """
#version 330

uniform float u_time;
uniform vec2 u_resolution;
uniform float u_energy_low;   // Sub-bass/kick energy (0-1) <100Hz
uniform float u_energy_mid;   // Bass/vocals/instruments energy (0-1) 100-4000Hz
uniform float u_energy_high;  // Hi-hat/treble energy (0-1) >4000Hz
uniform float u_hue_offset;

in vec2 v_uv;
out vec4 fragColor;

// HSV to RGB conversion
vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

// Harmonious colormap - stays within narrow hue band
// Maps pattern value (0-1) to dark -> saturated -> light
// Uses master hue as the center of the palette
vec3 harmonious_colormap(float x, float master_hue) {
    // Three-point gradient: dark -> saturated -> bright
    // Heavily biased toward saturated and bright colors
    float sat, val, hue_shift;
    
    if (x < 0.2) {
        // Dark accent region (small portion) - shifted hue for contrast
        float t = x / 0.2;
        sat = mix(0.75, 0.95, t);
        val = mix(0.35, 0.55, t);
        hue_shift = -0.08;  // Shift darks toward complementary
    } else if (x < 0.5) {
        // Saturated region (punchy colors)
        float t = (x - 0.2) / 0.3;
        sat = mix(0.95, 1.0, t);
        val = mix(0.55, 0.8, t);
        hue_shift = mix(-0.08, 0.0, t);  // Transition back to main hue
    } else {
        // Highlight region (bright and vibrant)
        float t = (x - 0.5) / 0.5;
        sat = mix(1.0, 0.6, t);
        val = mix(0.8, 1.0, t);
        hue_shift = (x - 0.5) * 0.06;  // Slight shift toward warm
    }
    
    // Narrow hue variation around master hue
    float hue = fract(master_hue + hue_shift + (x - 0.5) * 0.06);
    
    return hsv2rgb(vec3(hue, sat, val));
}

// Random function
float rand(vec2 n) { 
    return fract(sin(dot(n, vec2(12.9898, 4.1414))) * 43758.5453);
}

// Noise function
float noise(vec2 p) {
    vec2 ip = floor(p);
    vec2 u = fract(p);
    u = u * u * (3.0 - 2.0 * u);

    float res = mix(
        mix(rand(ip), rand(ip + vec2(1.0, 0.0)), u.x),
        mix(rand(ip + vec2(0.0, 1.0)), rand(ip + vec2(1.0, 1.0)), u.x),
        u.y);
    return res * res;
}

// Rotation matrix for FBM
const mat2 mtx = mat2(0.80, 0.60, -0.60, 0.80);

// Fractal Brownian Motion - with amplitude modulation
float fbm(vec2 p, float time, float amp_mod) {
    float f = 0.0;

    f += 0.500000 * (1.0 + amp_mod * 0.5) * noise(p + time); p = mtx * p * 2.02;
    f += 0.031250 * noise(p + time * 0.5); p = mtx * p * 2.01;
    f += 0.250000 * noise(p); p = mtx * p * 2.03;
    f += 0.125000 * noise(p + time * 0.3); p = mtx * p * 2.01;
    f += 0.062500 * noise(p + time * 0.7); p = mtx * p * 2.04;
    f += 0.015625 * noise(p + sin(time));

    return f / 0.96875;
}

// Domain warping pattern with warp intensity modulation
float pattern(vec2 p, float time, float amp_mod, float warp_intensity) {
    // Mid frequency controls domain warp complexity
    float warp = 0.8 + warp_intensity * 0.4;  // Range 0.8 to 1.2
    vec2 q = p + fbm(p, time, amp_mod) * warp;
    vec2 r = q + fbm(q, time, amp_mod) * warp;
    return fbm(r, time, amp_mod);
}

// Get color at a UV position (for blur sampling)
vec3 getColorAt(vec2 uv, float time, float scale, float amp_mod, float warp_mod, float master_hue) {
    vec2 scaled_uv = uv * scale;
    float shade = pattern(scaled_uv, time, amp_mod, warp_mod);
    return harmonious_colormap(shade, master_hue);
}

void main() {
    // Time runs smoothly - no energy-based speed changes for stable animation
    float time = u_time * 0.3;
    
    // UV coordinates centered at origin, with aspect ratio correction
    vec2 uv = v_uv - 0.5;  // Center at origin (-0.5 to 0.5)
    uv.x *= u_resolution.x / u_resolution.y;
    
    // Low frequency (bass) controls pattern scale - zoom anchored at center
    float scale = 2.8 + u_energy_low * 0.15;  // Gentle bass response
    
    // Master hue: base offset + slow drift over time (30 min cycle)
    // High frequency slightly shifts hue for sparkle on hi-hats/cymbals
    float hue_shift = u_energy_high * 0.08;  // Subtle hue shift on treble
    float master_hue = fract(u_hue_offset + sin(u_time * 3.14159 / 1800.0) * 0.15 + hue_shift);
    
    // Blur effect controlled by low frequency energy
    float blur_radius = u_energy_low * 0.025;  // Stronger bass blur
    
    vec3 rgb;
    if (blur_radius > 0.001) {
        // 9-tap gaussian-like blur kernel
        rgb = vec3(0.0);
        float total_weight = 0.0;
        
        // Center sample (highest weight)
        rgb += getColorAt(uv, time, scale, u_energy_low, u_energy_mid, master_hue) * 0.25;
        total_weight += 0.25;
        
        // Cardinal directions
        float w1 = 0.125;
        rgb += getColorAt(uv + vec2(blur_radius, 0.0), time, scale, u_energy_low, u_energy_mid, master_hue) * w1;
        rgb += getColorAt(uv + vec2(-blur_radius, 0.0), time, scale, u_energy_low, u_energy_mid, master_hue) * w1;
        rgb += getColorAt(uv + vec2(0.0, blur_radius), time, scale, u_energy_low, u_energy_mid, master_hue) * w1;
        rgb += getColorAt(uv + vec2(0.0, -blur_radius), time, scale, u_energy_low, u_energy_mid, master_hue) * w1;
        total_weight += w1 * 4.0;
        
        // Diagonal directions (lower weight)
        float w2 = 0.0625;
        float diag = blur_radius * 0.707;
        rgb += getColorAt(uv + vec2(diag, diag), time, scale, u_energy_low, u_energy_mid, master_hue) * w2;
        rgb += getColorAt(uv + vec2(-diag, diag), time, scale, u_energy_low, u_energy_mid, master_hue) * w2;
        rgb += getColorAt(uv + vec2(diag, -diag), time, scale, u_energy_low, u_energy_mid, master_hue) * w2;
        rgb += getColorAt(uv + vec2(-diag, -diag), time, scale, u_energy_low, u_energy_mid, master_hue) * w2;
        total_weight += w2 * 4.0;
        
        rgb /= total_weight;
    } else {
        // No blur - single sample
        rgb = getColorAt(uv, time, scale, u_energy_low, u_energy_mid, master_hue);
    }
    
    fragColor = vec4(rgb, 1.0);
}
"""


@register_shader
class FbmWarpShader(BaseShader):
    """FBM Warp shader - fractal Brownian motion with domain warping.

    Audio reactivity:
    - Low frequency (bass): controls pattern scale and blur
    - Mid frequency: controls domain warp complexity
    - High frequency: slightly shifts hue for sparkle effect
    """

    @property
    def name(self) -> str:
        return "FBM Warp"

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
    ) -> None:
        """Set shader uniforms."""
        program["u_time"].value = time
        program["u_resolution"].value = resolution
        program["u_energy_low"].value = energy_low
        program["u_energy_mid"].value = energy_mid
        program["u_energy_high"].value = energy_high
        program["u_hue_offset"].value = hue_offset
