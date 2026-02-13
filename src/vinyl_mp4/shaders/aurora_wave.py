"""Aurora Wave background shader - wavy gradient with film grain."""

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

# Aurora wave fragment shader - wavy gradient with film grain
# Based on Shadertoy shader, converted to GLSL 330 with audio reactivity
FRAGMENT_SHADER = """
#version 330

uniform float u_time;
uniform vec2 u_resolution;
uniform float u_energy_low;   // Sub-bass/kick energy (0-1) - warp intensity
uniform float u_energy_mid;   // Mid frequency (0-1) - color balance shift
uniform float u_energy_high;  // Hi-hat/treble (0-1) - grain amount
uniform float u_hue_offset;   // Randomized hue offset (0-1)

in vec2 v_uv;
out vec4 fragColor;

#define S(a,b,t) smoothstep(a,b,t)

mat2 Rot(float a) {
    float s = sin(a); float c = cos(a);
    return mat2(c, -s, s, c);
}

vec2 hash( vec2 p ) {
    p = vec2( dot(p,vec2(2127.1,81.17)), dot(p,vec2(1269.5,283.37)) );
    return fract(sin(p)*43758.5453);
}

float noise( in vec2 p ) {
    vec2 i = floor( p ); vec2 f = fract( p );
    vec2 u = f*f*(3.0-2.0*f);
    float n = mix( mix( dot( -1.0+2.0*hash( i + vec2(0.0,0.0) ), f - vec2(0.0,0.0) ), 
                        dot( -1.0+2.0*hash( i + vec2(1.0,0.0) ), f - vec2(1.0,0.0) ), u.x),
                   mix( dot( -1.0+2.0*hash( i + vec2(0.0,1.0) ), f - vec2(0.0,1.0) ), 
                        dot( -1.0+2.0*hash( i + vec2(1.0,1.0) ), f - vec2(1.0,1.0) ), u.x), u.y);
    return 0.5 + 0.5*n;
}

// HSV to RGB conversion for hue rotation
vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

// RGB to HSV conversion
vec3 rgb2hsv(vec3 c) {
    vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
    vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
    float d = q.x - min(q.w, q.y);
    float e = 1.0e-10;
    return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}

// Apply hue rotation to a color
vec3 rotateHue(vec3 color, float hueShift) {
    vec3 hsv = rgb2hsv(color);
    hsv.x = fract(hsv.x + hueShift);
    return hsv2rgb(hsv);
}

void main() {
    // --- TWEAKABLE CONTROLS (modulated by audio) ---
    float timeSpeed    = 1.0;
    // Mid frequency shifts color balance
    float colorBalance = 0.2 + u_energy_mid * 0.3;
    // Low frequency (bass) increases warp intensity
    float warpStrength = 1.0 + u_energy_low * 1.5;
    // High frequency adds more grain
    float grainAmount  = 0.06 + u_energy_high * 0.08;
    // --------------------------

    float t = u_time * timeSpeed;
    vec2 uv = v_uv;
    float ratio = u_resolution.x / u_resolution.y;

    vec2 tuv = uv - 0.5;

    // Rotate with Noise
    float degree = noise(vec2(t * 0.1, tuv.x * tuv.y));
    tuv.y *= 1./ratio;
    tuv *= Rot(radians((degree - 0.5) * 720. + 180.));
    tuv.y *= ratio;

    // Wave warp with sin - amplitude inversely proportional to warpStrength
    float frequency = 5.;
    float amplitude = 30. / warpStrength;
    tuv.x += sin(tuv.y * frequency + (t * 2.)) / amplitude;
    tuv.y += sin(tuv.x * (frequency * 1.5) + (t * 2.)) / (amplitude * 0.5);
    
    // --- COLOR PALETTE (will be hue-rotated) ---
    vec3 colLavender = vec3(0.867, 0.827, 0.965); // #DDD3F6
    vec3 colOrange   = vec3(0.941, 0.408, 0.247); // #F0683F
    vec3 colDark     = vec3(0.000, 0.047, 0.071); // #000C12
    
    // Apply hue rotation based on u_hue_offset
    colLavender = rotateHue(colLavender, u_hue_offset);
    colOrange = rotateHue(colOrange, u_hue_offset);
    colDark = rotateHue(colDark, u_hue_offset);
    
    // Blending with Color Balance Control
    float b = colorBalance;
    vec3 layer1 = mix(colDark, colOrange, S(-0.3 - b, 0.2 - b, (tuv * Rot(radians(-5.))).x));
    vec3 layer2 = mix(colOrange, colLavender, S(-0.3 - b, 0.2 - b, (tuv * Rot(radians(-5.))).x));
    
    // Final vertical mix
    vec3 col = mix(layer1, layer2, S(0.5 - b, -0.3 - b, tuv.y));
    
    // --- STATIC FILM GRAIN ---
    float grain = fract(sin(dot(uv + fract(u_time), vec2(12.9898, 78.233))) * 43758.5453);
    col += (grain - 0.5) * grainAmount;
    
    fragColor = vec4(col, 1.0);
}
"""


@register_shader
class AuroraWaveShader(BaseShader):
    """Aurora Wave shader - wavy gradient with film grain.

    Audio reactivity:
    - Low frequency (bass): wave warp intensity
    - Mid frequency: color balance shift (darker/lighter)
    - High frequency: film grain intensity
    """

    @property
    def name(self) -> str:
        return "Aurora Wave"

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
        **kwargs: object,
    ) -> None:
        """Set shader uniforms (contrast is ignored for Aurora Wave)."""
        program["u_time"].value = time
        program["u_resolution"].value = resolution
        program["u_energy_low"].value = energy_low
        program["u_energy_mid"].value = energy_mid
        program["u_energy_high"].value = energy_high
        program["u_hue_offset"].value = hue_offset
