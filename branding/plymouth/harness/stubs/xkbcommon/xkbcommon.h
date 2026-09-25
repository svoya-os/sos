/* Minimal stand-in so Plymouth's headers compile in the headless harness (no keyboard code is built).
 * SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#include <stdint.h>
typedef uint32_t xkb_mod_mask_t;
typedef uint32_t xkb_keycode_t;
typedef uint32_t xkb_keysym_t;
typedef uint32_t xkb_layout_index_t;
struct xkb_context;
struct xkb_keymap;
struct xkb_state;
