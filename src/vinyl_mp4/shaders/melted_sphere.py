"""Melted Sphere background shader - raymarched iridescent sphere with droplets."""

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

# Melted sphere fragment shader - raymarched scene
# Based on Shadertoy shader, converted to GLSL 330 with audio reactivity
FRAGMENT_SHADER = """
#version 330

uniform float u_time;
uniform vec2 u_resolution;
uniform float u_energy_low;   // Sub-bass/kick energy (0-1) - sphere distortion
uniform float u_energy_mid;   // Mid frequency (0-1) - droplet speed
uniform float u_energy_high;  // Hi-hat/treble (0-1) - glow intensity
uniform float u_hue_offset;
uniform sampler2D u_noise_texture;

in vec2 v_uv;
out vec4 fragColor;

#define PI 3.14159265359
#define TAU 6.283185
#define SURF_DIST 0.01

// Rotation matrix
mat2 rot(float a) { return mat2(cos(a), -sin(a), sin(a), cos(a)); }

// Camera look-at
vec3 lookAt(vec3 from, vec3 at, vec2 uv, float fov) {
    vec3 z = normalize(at - from);
    vec3 x = normalize(cross(z, vec3(0, 1, 0)));
    vec3 y = normalize(cross(x, z));
    return normalize(z * fov + uv.x * x + uv.y * y);
}

// Mercury's polar modulo
// https://mercury.sexy/hg_sdf/
float pModPolar(inout vec2 p, float repetitions) {
    float angle = TAU / repetitions;
    float a = atan(p.y, p.x) + angle / 2.0;
    float r = length(p);
    float c = floor(a / angle);
    a = mod(a, angle) - angle / 2.0;
    p = vec2(cos(a), sin(a)) * r;
    if (abs(c) >= (repetitions / 2.0)) c = abs(c);
    return c;
}

// SDF primitives (Inigo Quilez)
float sdSphere(vec3 p) {
    return length(p) - 2.2;  // Large sphere to fill background
}

float sdSegment(vec3 p, float h, float r) {
    p.y -= clamp(p.y, 0.0, h);
    return length(p) - r;
}

float smin(float d1, float d2, float k) {
    float h = clamp(0.5 + 0.5 * (d2 - d1) / k, 0.0, 1.0);
    return mix(d2, d1, h) - k * h * (1.0 - h);
}

// Dave Hoskins hash functions
float hash11(float p) {
    p = fract(p * 0.1031);
    p *= p + 33.33;
    p *= p + p;
    return fract(p);
}

vec3 hash31(float p) {
    vec3 p3 = fract(vec3(p) * vec3(0.1031, 0.1030, 0.0973));
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.xxy + p3.yzz) * p3.zyx);
}

// Iridescent color
vec3 irri(float hue) {
    return 0.5 + 0.5 * cos(9.0 * hue + vec3(0, 23.0, 21.0));
}

// Melted sphere distortion
float melted(vec3 samplePoint, float time, float distortAmt, out float aspect) {
    float y = samplePoint.y;
    
    // Bass makes the wobble more intense
    float wobbleAmp = 1.0 + distortAmt * 2.5;
    
    float angle = 0.0;
    angle += sin(y + time) * wobbleAmp;
    angle += sin(y * 1.5 + time * 1.5) * 1.25 * wobbleAmp;
    angle += cos(y * 0.03 + time * 1.7) * 1.563;
    angle += cos(y * 1.1 + time * 1.2) * 1.441 * wobbleAmp;
    
    aspect = angle;
    angle = angle * PI + TAU;
    
    // Distortion amount strongly modulated by bass
    float dist = 0.1 * (1.0 + distortAmt * 3.0);
    vec3 offset = vec3(sin(angle), 0.0, cos(angle)) * dist;
    
    // Scale sphere size with bass (pulsing effect)
    float scale = 1.0 - distortAmt * 0.15;
    return sdSphere(samplePoint * scale + offset);
}

// Scene SDF
float map(vec3 p, float time, float distortAmt, float dropletSpeed) {
    float dist = 100.0;
    float shape = 100.0;
    vec3 pp = p;
    float c;
    float a = 0.0;
    
    // Main sphere with melted distortion
    dist = melted(p, time * 0.5, distortAmt, a);
    
    // Droplets
    c = abs(pModPolar(p.xz, 5.0));
    vec3 rng = hash31(c);
    p.x -= 1.0 - 0.5;
    rng.x += sign(p.x) * 0.5;
    p.x = p.x - 0.2;
    p.y *= -1.0;
    
    // Droplet animation speed modulated by mid frequency
    float animSpeed = 0.2 * (1.0 + dropletSpeed * 0.8);
    float dropTime = animSpeed * time + rng.x;
    float anim = fract(dropTime);
    float wave = sin(anim * PI);
    float h = 0.7 + 0.3 * pow(wave, 4.0);
    float s = 0.03 - 0.08 * (1.0 - wave);
    
    shape = sdSegment(p, h, s);
    dist = smin(dist, shape, 0.2);
    shape = length(p - vec3(0, pow(anim, 8.0) * 400.0 + h, 0)) - 0.025 * (1.0 - p.y);
    dist = smin(dist, shape, 0.3 * pow(anim, 0.5));
    
    return dist * 0.5;
}

// Coloring function
void coloring(inout vec3 color, in vec3 pos, in vec3 normal, in vec3 ray, in vec2 uv, 
              in float shade, float hueOff, float glowIntensity) {
    // Inigo Quilez color palette
    vec3 tint = 0.5 + 0.5 * cos(vec3(0, 0.3, 0.6) * TAU + hueOff * TAU + uv.y * 3.0);
    
    // Lighting
    color = vec3(0.15) * pow(dot(normal, vec3(0, -1, 0)) * 0.5 + 0.5, 10.0);
    vec3 rf = reflect(ray, normal);
    float top = dot(rf, vec3(0, 1, 0)) * 0.5 + 0.5;
    float glow = dot(normal, ray) * 0.5 + 0.5;
    
    color += vec3(0.8) * pow(clamp(top, 0.0, 1.0), 4.5);
    
    // Glow intensity modulated by high frequency
    float glowMult = 2.0 + glowIntensity * 1.5;
    color += vec3(glowMult) * pow(glow, 2.0);
    color *= pow(shade, 0.5);
    
    // Iridescence
    color += irri(top + glow + pos.y * 0.1 + hueOff) * glow;
}

void main() {
    vec2 uv = (gl_FragCoord.xy - u_resolution.xy / 2.0) / u_resolution.y;
    
    // Background
    vec3 color = vec3(0.1);
    
    // Camera - closer to make sphere fill frame
    vec3 pos = vec3(0, 0, 3.5);
    vec3 at = vec3(0, 0, 0);
    pos.zy *= rot(cos(u_time * 0.2) * 0.15);
    vec3 ray = lookAt(pos, at, uv, 0.8);  // Wider FOV
    
    // Audio reactivity parameters
    float distortAmt = u_energy_low;
    float dropletSpeed = u_energy_mid;
    float glowIntensity = u_energy_high;
    
    float maxDist = 7.0;
    
    // Raymarch
    const float count = 50.0;
    float steps = 0.0;
    float total = 0.0;
    for (steps = count; steps > 0.0; --steps) {
        float dist = map(pos, u_time, distortAmt, dropletSpeed);
        if (dist < total * 1.0 / u_resolution.y || total > maxDist) break;
        pos += ray * dist;
        total += dist;
    }
    
    // Normal calculation (NuSan technique)
    vec2 noff = vec2(0.001, 0);
    vec3 normal = normalize(
        map(pos, u_time, distortAmt, dropletSpeed) - vec3(
            map(pos - noff.xyy, u_time, distortAmt, dropletSpeed),
            map(pos - noff.yxy, u_time, distortAmt, dropletSpeed),
            map(pos - noff.yyx, u_time, distortAmt, dropletSpeed)
        )
    );
    
    // Coloring
    float shade = steps / count;
    if (shade > SURF_DIST && total < maxDist) {
        coloring(color, pos, normal, ray, uv, shade, u_hue_offset, glowIntensity);
    }
    
    fragColor = vec4(color, 1.0);
}
"""


@register_shader
class MeltedSphereShader(BaseShader):
    """Melted Sphere shader - raymarched iridescent sphere with droplets.

    Audio reactivity:
    - Low frequency (bass): sphere distortion amplitude
    - Mid frequency: droplet animation speed
    - High frequency: glow/shimmer intensity
    """

    @property
    def name(self) -> str:
        return "Melted Sphere"

    @property
    def main_pass(self) -> ShaderPass:
        return ShaderPass(
            vertex_source=VERTEX_SHADER,
            fragment_source=FRAGMENT_SHADER,
        )

    @property
    def needs_noise_texture(self) -> bool:
        """This shader can optionally use a noise texture."""
        return True

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
        # Note: u_noise_texture is set separately if available
