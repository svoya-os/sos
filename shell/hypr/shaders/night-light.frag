#version 300 es
// SPDX-License-Identifier: Apache-2.0
// SOS night light: the screen a warm ~3400 K in the evening (shell Settings.nightLight, Control
// Center). A Hyprland screen shader (decoration:screen_shader), so no extra program is needed;
// the shell sets and clears it with `hyprctl keyword`.
precision mediump float;

in vec2 v_texcoord;
uniform sampler2D tex;
out vec4 fragColor;

void main() {
    vec4 pix = texture(tex, v_texcoord);
    // 3400 K relative to 6500 K white (Tanner Helland's blackbody approximation): R 1.00, G 0.80, B 0.60
    fragColor = vec4(pix.r, pix.g * 0.80, pix.b * 0.60, pix.a);
}
