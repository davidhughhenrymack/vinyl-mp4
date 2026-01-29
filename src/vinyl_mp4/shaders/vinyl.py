"""Vinyl overlay shader - draws a rotating vinyl record with label."""

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

// High quality hash functions
float hash(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float hash3(vec3 p) {
    p = fract(p * 0.1031);
    p += dot(p, p.yzx + 33.33);
    return fract((p.x + p.y) * p.z);
}

// Smooth noise
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

// Fractal Brownian Motion for organic texture
float fbm(vec2 p, int octaves) {
    float value = 0.0;
    float amplitude = 0.5;
    float frequency = 1.0;
    for (int i = 0; i < octaves; i++) {
        value += amplitude * noise(p * frequency);
        frequency *= 2.0;
        amplitude *= 0.5;
    }
    return value;
}

// Film grain - realistic photographic grain
float filmGrain(vec2 uv, float time, float intensity) {
    // Animate grain at ~24fps for film-like feel
    float t = floor(time * 24.0);
    
    // Multi-frequency grain for realism
    float grain = 0.0;
    grain += (hash(uv * 1000.0 + t) - 0.5) * 0.6;           // Fine grain
    grain += (hash(uv * 400.0 + t * 1.1) - 0.5) * 0.3;      // Medium grain
    grain += (noise(uv * 150.0 + t * 0.9) - 0.5) * 0.1;     // Coarse variation
    
    return grain * intensity;
}

// Vinyl surface imperfections
float vinylSurface(vec2 uv, float angle, float dist, float time) {
    float surface = 0.0;
    
    // Micro-scratches (circular, following grooves)
    float scratch1 = smoothstep(0.998, 1.0, sin(angle * 180.0 + dist * 500.0));
    float scratch2 = smoothstep(0.995, 1.0, sin(angle * 90.0 - dist * 300.0 + 1.5));
    surface += (scratch1 + scratch2) * 0.03;
    
    // Dust specks (static, doesn't rotate with vinyl)
    vec2 dust_uv = uv + 0.5;  // Use non-rotated coords
    float dust = smoothstep(0.85, 0.9, noise(dust_uv * 500.0));
    dust *= smoothstep(0.7, 0.8, hash(floor(dust_uv * 200.0)));
    surface += dust * 0.04;
    
    // Surface variation (subtle waviness in the vinyl)
    surface += (fbm(uv * 50.0, 3) - 0.5) * 0.015;
    
    return surface;
}

// Paper/cardboard texture for label
float paperTexture(vec2 uv, float time) {
    float paper = 0.0;
    
    // Fiber texture
    paper += (fbm(uv * 200.0, 4) - 0.5) * 0.03;
    
    // Subtle print imperfections
    paper += (noise(uv * 80.0) - 0.5) * 0.015;
    
    // Animated film grain overlay
    paper += filmGrain(uv, time, 0.02);
    
    return paper;
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
    
    // Label area
    if (dist < LABEL_RADIUS) {
        // Map to texture coordinates
        vec2 label_uv = (rotated_uv / LABEL_RADIUS) * 0.5 + 0.5;
        vec4 label_color = texture(u_label_texture, label_uv);
        
        // Add paper texture and grain to label
        float paper = paperTexture(label_uv, u_time);
        label_color.rgb += paper;
        
        // Slight color variation in paper (warmer spots)
        label_color.r += fbm(label_uv * 30.0, 2) * 0.01;
        
        fragColor = label_color;
        return;
    }
    
    // Vinyl area with grooves
    float angle = atan(rotated_uv.y, rotated_uv.x);
    
    // Create groove effect - higher frequency for narrower grooves
    float groove_freq = 300.0;
    float groove = sin(dist * groove_freq) * 0.5 + 0.5;
    groove = smoothstep(0.3, 0.7, groove);
    
    // Secondary groove detail
    float fine_groove = sin(dist * 1200.0) * 0.5 + 0.5;
    fine_groove = smoothstep(0.4, 0.6, fine_groove);
    
    // Base vinyl color (dark gray to black)
    vec3 vinyl_color = vec3(0.015, 0.015, 0.018);
    
    // Add groove highlights
    float highlight = groove * 0.06 + fine_groove * 0.02;
    vinyl_color += vec3(highlight);
    
    // Add specular highlight (light reflection)
    vec2 light_dir = normalize(vec2(0.5, 0.5));
    vec2 normal = normalize(uv);
    float spec = pow(max(0.0, dot(normal, light_dir)), 32.0);
    vinyl_color += vec3(spec * 0.12);
    
    // Rainbow/iridescent reflection in grooves
    float iridescence = sin(angle * 2.0 + dist * 80.0) * 0.5 + 0.5;
    iridescence *= spec * 0.5;
    vinyl_color.r += iridescence * 0.015;
    vinyl_color.g += sin(angle * 2.0 + dist * 80.0 + 2.0) * spec * 0.01;
    vinyl_color.b += sin(angle * 2.0 + dist * 80.0 + 4.0) * spec * 0.02;
    
    // Add vinyl surface imperfections
    float surface = vinylSurface(rotated_uv, angle, dist, u_time);
    vinyl_color += surface;
    
    // Film grain on vinyl
    vinyl_color += filmGrain(v_uv, u_time, 0.015);
    
    fragColor = vec4(vinyl_color, 1.0);
}
"""

__all__ = ["VINYL_VERTEX_SHADER", "VINYL_FRAGMENT_SHADER"]
