"""GLSL shader source code for vinyl-mp4 visualization.

Background shader is based on Shadertoy tdG3Rd "Base warp fBM".
"""

# Simple vertex shader for full-screen quad
BACKGROUND_VERTEX_SHADER = """
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
BACKGROUND_FRAGMENT_SHADER = """
#version 330

uniform float u_time;
uniform vec2 u_resolution;
uniform float u_energy_low;   // Bass/kick energy (0-1)
uniform float u_energy_high;  // Hi-hat/treble energy (0-1)
uniform float u_hue_offset;

in vec2 v_uv;
out vec4 fragColor;

// Colormap functions from Shadertoy tdG3Rd
float colormap_red(float x) {
    if (x < 0.0) {
        return 54.0 / 255.0;
    } else if (x < 20049.0 / 82979.0) {
        return (829.79 * x + 54.51) / 255.0;
    } else {
        return 1.0;
    }
}

float colormap_green(float x) {
    if (x < 20049.0 / 82979.0) {
        return 0.0;
    } else if (x < 327013.0 / 810990.0) {
        return (8546482679670.0 / 10875673217.0 * x - 2064961390770.0 / 10875673217.0) / 255.0;
    } else if (x <= 1.0) {
        return (103806720.0 / 483977.0 * x + 19607415.0 / 483977.0) / 255.0;
    } else {
        return 1.0;
    }
}

float colormap_blue(float x) {
    if (x < 0.0) {
        return 54.0 / 255.0;
    } else if (x < 7249.0 / 82979.0) {
        return (829.79 * x + 54.51) / 255.0;
    } else if (x < 20049.0 / 82979.0) {
        return 127.0 / 255.0;
    } else if (x < 327013.0 / 810990.0) {
        return (792.02249341361393720147485376583 * x - 64.364790735602331034989206222672) / 255.0;
    } else {
        return 1.0;
    }
}

vec3 colormap(float x) {
    return vec3(colormap_red(x), colormap_green(x), colormap_blue(x));
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

// HSV to RGB conversion
vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
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

// Fractal Brownian Motion - with amplitude modulation from low freq
float fbm(vec2 p, float time, float amp_mod) {
    float f = 0.0;

    f += 0.500000 * (1.0 + amp_mod * 0.3) * noise(p + time); p = mtx * p * 2.02;
    f += 0.031250 * noise(p); p = mtx * p * 2.01;
    f += 0.250000 * noise(p); p = mtx * p * 2.03;
    f += 0.125000 * noise(p); p = mtx * p * 2.01;
    f += 0.062500 * noise(p); p = mtx * p * 2.04;
    f += 0.015625 * noise(p + sin(time));

    return f / 0.96875;
}

// Domain warping pattern with amplitude modulation
float pattern(vec2 p, float time, float amp_mod) {
    return fbm(p + fbm(p + fbm(p, time, amp_mod), time, amp_mod), time, amp_mod);
}

void main() {
    // Time runs smoothly - no energy-based speed changes for stable animation
    float time = u_time * 0.3;
    
    // UV coordinates with aspect ratio correction
    vec2 uv = v_uv;
    uv.x *= u_resolution.x / u_resolution.y;
    
    // Low frequency (bass) controls pattern scale - subtle zoom effect
    float scale = 2.8 + u_energy_low * 0.4;
    uv *= scale;
    
    // Calculate pattern value with low freq modulating amplitude
    float shade = pattern(uv, time, u_energy_low);
    
    // Get base color from colormap
    vec3 rgb = colormap(shade);
    
    // Convert to HSV for color manipulation
    vec3 hsv = rgb2hsv(rgb);
    
    // Apply base hue offset from filename hash
    hsv.x = fract(hsv.x + u_hue_offset);
    
    // Slow hue rotation over time (full cycle over ~30 minutes = 1800 seconds)
    float slow_hue_shift = sin(u_time * 3.14159 / 1800.0) * 0.15;
    hsv.x = fract(hsv.x + slow_hue_shift);
    
    // High frequency (treble) boosts brightness
    hsv.z = min(1.0, hsv.z * (0.85 + u_energy_high * 0.3));
    
    rgb = hsv2rgb(hsv);
    
    fragColor = vec4(rgb, 1.0);
}
"""

# Vinyl vertex shader
VINYL_VERTEX_SHADER = """
#version 330

in vec2 in_position;
out vec2 v_uv;

void main() {
    v_uv = in_position * 0.5 + 0.5;
    gl_Position = vec4(in_position, 0.0, 1.0);
}
"""

# Vinyl fragment shader - draws a rotating vinyl record with label
VINYL_FRAGMENT_SHADER = """
#version 330

uniform float u_time;
uniform vec2 u_resolution;
uniform sampler2D u_label_texture;

in vec2 v_uv;
out vec4 fragColor;

const float PI = 3.14159265359;
const float VINYL_RADIUS = 0.35;
const float LABEL_RADIUS = 0.26;  // 3/4 of vinyl radius for large label
const float HOLE_RADIUS = 0.012;
const float RPM = 33.0;

// Simple noise function for film grain effect
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(
        mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
        mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x),
        f.y
    );
}

void main() {
    // Center the coordinates
    vec2 center = vec2(0.5);
    vec2 uv = v_uv - center;
    
    // Correct for aspect ratio
    float aspect = u_resolution.x / u_resolution.y;
    uv.x *= aspect;
    
    float dist = length(uv);
    
    // Outside vinyl - transparent
    if (dist > VINYL_RADIUS) {
        fragColor = vec4(0.0);
        return;
    }
    
    // Center hole
    if (dist < HOLE_RADIUS) {
        fragColor = vec4(0.0);
        return;
    }
    
    // Calculate rotation angle (33 RPM = 33 rotations per 60 seconds)
    float rotation = u_time * RPM / 60.0 * 2.0 * PI;
    
    // Rotate UV coordinates
    float cos_r = cos(rotation);
    float sin_r = sin(rotation);
    vec2 rotated_uv = vec2(
        uv.x * cos_r - uv.y * sin_r,
        uv.x * sin_r + uv.y * cos_r
    );
    
    // Gentle animated noise for film grain effect (changes slowly)
    float grain_time = floor(u_time * 8.0);  // 8 fps grain animation
    float grain = noise(v_uv * 800.0 + grain_time * 100.0) * 0.04 - 0.02;
    
    // Label area
    if (dist < LABEL_RADIUS) {
        // Map to texture coordinates
        vec2 label_uv = (rotated_uv / LABEL_RADIUS) * 0.5 + 0.5;
        vec4 label_color = texture(u_label_texture, label_uv);
        
        // Add subtle grain to label
        label_color.rgb += grain * 0.5;
        
        fragColor = label_color;
        return;
    }
    
    // Vinyl area with grooves
    float angle = atan(rotated_uv.y, rotated_uv.x);
    
    // Create groove effect - higher frequency for narrower grooves
    float groove_freq = 300.0;
    float groove = sin(dist * groove_freq) * 0.5 + 0.5;
    groove = smoothstep(0.3, 0.7, groove);
    
    // Base vinyl color (dark gray to black)
    vec3 vinyl_color = vec3(0.02, 0.02, 0.02);
    
    // Add subtle groove highlights
    float highlight = groove * 0.08;
    vinyl_color += vec3(highlight);
    
    // Add specular highlight
    vec2 light_dir = normalize(vec2(0.5, 0.5));
    vec2 normal = normalize(uv);
    float spec = pow(max(0.0, dot(normal, light_dir)), 32.0);
    vinyl_color += vec3(spec * 0.15);
    
    // Slight color variation in grooves
    vinyl_color.r += sin(angle * 2.0 + dist * 50.0) * 0.01;
    vinyl_color.b += cos(angle * 2.0 + dist * 50.0) * 0.01;
    
    // Add grain to vinyl
    vinyl_color += grain;
    
    fragColor = vec4(vinyl_color, 1.0);
}
"""
