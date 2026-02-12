"""Retro Terrain background shader - wireframe terrain with perspective projection."""

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

# Retro terrain fragment shader - wireframe terrain scrolling into the distance
# Based on XBE Shadertoy shader, converted to GLSL 330 with audio reactivity
FRAGMENT_SHADER = """
#version 330

uniform float u_time;
uniform vec2 u_resolution;
uniform float u_energy_low;   // Sub-bass/kick energy (0-1) - terrain height amplitude
uniform float u_energy_mid;   // Mid frequency (0-1) - subtle brightness
uniform float u_energy_high;  // Hi-hat/treble (0-1) - shape evolution / warp
uniform float u_energy_avg;   // Moving average of total energy (0-1) - camera tilt
uniform float u_progress;     // Playback progress (0-1) - line reveal
uniform float u_hue_offset;   // Randomized hue offset (0-1)

in vec2 v_uv;
out vec4 fragColor;

const float PI = 3.141592654;

vec2 hash( vec2 p )
{
    p = vec2( dot(p,vec2(127.1,311.7)),
             dot(p,vec2(269.5,183.3)) );
    return -1.0 + 2.0*fract(sin(p)*43758.5453123);
}

float noise( in vec2 p )
{
    const float K1 = 0.366025404;
    const float K2 = 0.211324865;

    vec2 i = floor( p + (p.x+p.y)*K1 );

    vec2 a = p - i + (i.x+i.y)*K2;
    vec2 o = (a.x>a.y) ? vec2(1.0,0.0) : vec2(0.0,1.0);
    vec2 b = a - o + K2;
    vec2 c = a - 1.0 + 2.0*K2;

    vec3 h = max( 0.5-vec3(dot(a,a), dot(b,b), dot(c,c) ), 0.0 );

    vec3 n = h*h*h*h*vec3( dot(a,hash(i+0.0)), dot(b,hash(i+o)), dot(c,hash(i+1.0)));

    return dot( n, vec3(70.0) );
}

const mat2 m = mat2( 0.80,  0.60, -0.60,  0.80 );

float fbm4( in vec2 p )
{
    float f = 0.0;
    f += 0.5000*noise( p ); p = m*p*2.02;
    f += 0.2500*noise( p ); p = m*p*2.03;
    f += 0.1250*noise( p ); p = m*p*2.01;
    f += 0.0625*noise( p );
    return f;
}

mat4 CreatePerspectiveMatrix(in float fov, in float aspect, in float nearZ, in float farZ)
{
    mat4 pm = mat4(0.0);
    float angle = (fov / 180.0) * PI;
    float f = 1.0 / tan( angle * 0.5 );
    pm[0][0] = f / aspect;
    pm[1][1] = f;
    pm[2][2] = (farZ + nearZ) / (nearZ - farZ);
    pm[2][3] = -1.0;
    pm[3][2] = (2.0 * farZ * nearZ) / (nearZ - farZ);
    return pm;
}

mat4 CamControl( vec3 eye, float pitch )
{
    float cosPitch = cos(pitch);
    float sinPitch = sin(pitch);
    vec3 xaxis = vec3( 1.0, 0.0, 0.0 );
    vec3 yaxis = vec3( 0.0, cosPitch, sinPitch );
    vec3 zaxis = vec3( 0.0, -sinPitch, cosPitch );
    mat4 viewMatrix = mat4(
        vec4(       xaxis.x,            yaxis.x,            zaxis.x,      0.0 ),
        vec4(       xaxis.y,            yaxis.y,            zaxis.y,      0.0 ),
        vec4(       xaxis.z,            yaxis.z,            zaxis.z,      0.0 ),
        vec4( -dot( xaxis, eye ), -dot( yaxis, eye ), -dot( zaxis, eye ), 1.0 )
    );
    return viewMatrix;
}

// HSV to RGB for hue-based line coloring
vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void main()
{
    vec2 uv = gl_FragCoord.xy / u_resolution.xy;
    vec2 p = 2.0 * uv - 1.0;
    p.x *= u_resolution.x / u_resolution.y;

    // Audio-reactive parameters
    float heightScale = 0.1 + 0.9 * u_energy_low;      // Bass controls terrain amplitude
    float shapeEvolve = u_energy_high * 0.4;             // Treble subtly warps terrain shape
    float brightness = 1.0 + 0.3 * u_energy_mid;         // Mids: gentle brightness lift

    // Camera tilt driven by moving-average energy: silent → 0° (head-on), loud → ~18°
    float pitchDeg = mix(0.0, 18.0, u_energy_avg);

    vec3 eye = vec3(0.0, 0.25, -1.0);
    float aspect = u_resolution.x / u_resolution.y;
    mat4 projmat = CreatePerspectiveMatrix(50.0, aspect, 0.1, 10.0);
    mat4 viewmat = CamControl(eye, -pitchDeg * PI / 180.0);
    mat4 vpmat = viewmat * projmat;

    vec3 acc = vec3(0.0);
    float d;

    vec4 pos = vec4(0.0);
    float lh = -u_resolution.y;
    float off = 0.1 * u_time;          // Constant scroll speed, no jitter
    float z = 0.1;
    float zi = 0.05;
    float lineWidth = 0.005;            // Fixed line width, no vibration
    float bloomWidth = 0.03;             // Wider soft glow radius
    vec3 bloomAcc = vec3(0.0);

    // Reveal lines back-to-front over the first 50% of playback.
    // reveal ramps 0→1 during progress 0→0.5, then stays at 1.
    float reveal = clamp(u_progress / 0.5, 0.0, 1.0);

    for (int i = 0; i < 24; ++i)
    {
        // Line threshold: back (i=23) → 0.0, front (i=0) → 1.0
        float lineThresh = 1.0 - float(i) / 23.0;
        // Smooth fade-in: each line fades from 0→1 over a small window
        float lineAlpha = smoothstep(lineThresh - 0.08, lineThresh, reveal);

        // shapeEvolve shifts noise coords so treble morphs the terrain surface
        pos = vec4(p.x, heightScale * fbm4(0.5 * vec2(eye.x + p.x + shapeEvolve, z + off)), eye.z + z, 1.0);
        float h = (vpmat * pos).y - p.y;
        if (h > lh)
        {
            d = abs(h);
            float fade = exp(-0.1 * float(i)) * lineAlpha;
            // Sharp line
            vec3 col = vec3( d < lineWidth ? smoothstep(1.0, 0.0, d / lineWidth) : 0.0 );
            col *= fade;
            acc += col;
            // Soft bloom halo
            vec3 bloom = vec3( d < bloomWidth ? smoothstep(1.0, 0.0, d / bloomWidth) : 0.0 );
            bloom *= fade * 0.15;
            bloomAcc += bloom;
            lh = h;
        }
        z += zi;
    }

    // Tint lines using hue offset, apply mid-frequency brightness
    vec3 lineColor = hsv2rgb(vec3(u_hue_offset, 0.7, 1.0));
    vec3 col = (sqrt(clamp(acc, 0.0, 1.0)) + clamp(bloomAcc, 0.0, 1.0)) * lineColor * brightness;

    // Pure black background
    fragColor = vec4(col, 1.0);
}
"""


@register_shader
class RetroTerrainShader(BaseShader):
    """Retro Terrain shader - wireframe terrain with perspective projection.

    Audio reactivity:
    - Low frequency (bass): terrain height amplitude
    - Mid frequency: subtle brightness lift
    - High frequency: terrain shape evolution / warp
    - Total energy (moving average): camera tilt angle
    """

    # EMA smoothing factor — lower = smoother. ~0.5s time constant at 60fps.
    _EMA_ALPHA = 0.03

    def __init__(self) -> None:
        self._energy_avg: float = 0.0
        self.progress: float = 1.0  # 0-1 playback progress; default fully revealed

    @property
    def name(self) -> str:
        return "Retro Terrain"

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
    ) -> None:
        """Set shader uniforms (contrast is ignored for Retro Terrain)."""
        # Update exponential moving average of total energy
        total = (energy_low + energy_mid + energy_high) / 3.0
        self._energy_avg += self._EMA_ALPHA * (total - self._energy_avg)

        program["u_time"].value = time
        program["u_resolution"].value = resolution
        program["u_energy_low"].value = energy_low
        program["u_energy_mid"].value = energy_mid
        program["u_energy_high"].value = energy_high
        program["u_energy_avg"].value = self._energy_avg
        program["u_progress"].value = self.progress
        program["u_hue_offset"].value = hue_offset
