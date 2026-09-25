/* Run a Plymouth script theme through Plymouth's own script engine, headless.
 *
 *   harness THEME_DIR SCRIPT MODE WIDTH HEIGHT OUT_PREFIX EVENTS...
 *
 * EVENTS are "<seconds>:<action>[:args]" and are applied before the refresh of that frame:
 *   progress:<fraction>   password:<bullets>:<prompt>   question:<entry>:<prompt>
 *   message:<text>        hide:<text>                   normal
 *   update:<percent>      status:<text>                 quit
 *   caps:<0|1>            dump:<name>   (writes OUT_PREFIX<name>.ppm)
 * The script's errors are printed by the engine itself ("Execution error ...").
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <locale.h>
#include "ply-list.h"
#include "ply-logger.h"
#include "ply-pixel-buffer.h"
#include "ply-pixel-display.h"
#include "ply-keyboard.h"
#include "script.h"
#include "script-parse.h"
#include "script-execute.h"
#include "script-object.h"
#include "script-lib-image.h"
#include "script-lib-sprite.h"
#include "script-lib-plymouth.h"
#include "script-lib-math.h"
#include "script-lib-string.h"

ply_pixel_display_t *fake_display_new (unsigned long width, unsigned long height);
ply_pixel_buffer_t *fake_display_get_buffer (ply_pixel_display_t *d);

static int caps_state;
bool ply_keyboard_get_capslock_state (ply_keyboard_t *keyboard) { (void) keyboard; return caps_state; }

static void
dump (ply_pixel_buffer_t *buf, const char *path)
{
        unsigned long w = ply_pixel_buffer_get_width (buf), h = ply_pixel_buffer_get_height (buf);
        uint32_t *px = ply_pixel_buffer_get_argb32_data (buf);
        FILE *f = fopen (path, "wb");
        fprintf (f, "P6\n%lu %lu\n255\n", w, h);
        for (unsigned long i = 0; i < w * h; i++) {
                unsigned char rgb[3] = { (px[i] >> 16) & 0xff, (px[i] >> 8) & 0xff, px[i] & 0xff };
                fwrite (rgb, 1, 3, f);
        }
        fclose (f);
        printf ("wrote %s\n", path);
}

static ply_boot_splash_mode_t
parse_mode (const char *m)
{
        if (!strcmp (m, "shutdown")) return PLY_BOOT_SPLASH_MODE_SHUTDOWN;
        if (!strcmp (m, "reboot")) return PLY_BOOT_SPLASH_MODE_REBOOT;
        if (!strcmp (m, "updates")) return PLY_BOOT_SPLASH_MODE_UPDATES;
        if (!strcmp (m, "system-upgrade")) return PLY_BOOT_SPLASH_MODE_SYSTEM_UPGRADE;
        if (!strcmp (m, "firmware-upgrade")) return PLY_BOOT_SPLASH_MODE_FIRMWARE_UPGRADE;
        if (!strcmp (m, "system-reset")) return PLY_BOOT_SPLASH_MODE_SYSTEM_RESET;
        return PLY_BOOT_SPLASH_MODE_BOOT_UP;
}

int
main (int argc, char **argv)
{
        if (argc < 7) {
                fprintf (stderr, "usage: harness THEME_DIR SCRIPT MODE W H OUT_PREFIX EVENTS...\n");
                return 2;
        }
        const char *theme_dir = argv[1], *script_file = argv[2], *prefix = argv[6];
        unsigned long w = strtoul (argv[4], NULL, 10), h = strtoul (argv[5], NULL, 10);
        setlocale (LC_ALL, "");   /* as plymouthd does: the label-freetype plugin decodes UTF-8 with mbrtowc() */
        ply_logger_set_output_fd (ply_logger_get_error_default (), 2);

        ply_list_t *displays = ply_list_new ();
        ply_pixel_display_t *display = fake_display_new (w, h);
        ply_list_append_data (displays, display);

        script_op_t *main_op = script_parse_file (script_file);
        if (!main_op) {
                fprintf (stderr, "PARSE FAILED: %s\n", script_file);
                return 1;
        }
        script_state_t *state = script_state_new (NULL);
        /* [script-env-vars] */
        script_obj_t *target = script_obj_hash_get_element (state->global, "svoya_lang");
        script_obj_t *value = script_obj_new_string (getenv ("SVOYA_LANG") ? getenv ("SVOYA_LANG") : "ru");
        script_obj_assign (target, value);
        script_obj_unref (target);
        script_obj_unref (value);

        script_lib_image_data_t *image_lib = script_lib_image_setup (state, (char *) theme_dir);
        script_lib_sprite_data_t *sprite_lib = script_lib_sprite_setup (state, displays);
        script_lib_plymouth_data_t *ply_lib = script_lib_plymouth_setup (state, parse_mode (argv[3]), 50, NULL);
        script_lib_math_data_t *math_lib = script_lib_math_setup (state);
        script_lib_string_data_t *string_lib = script_lib_string_setup (state);
        script_return_t ret = script_execute (state, main_op);
        script_obj_unref (ret.object);

        int last_frame = 0;
        for (int i = 7; i < argc; i++) {
                char *ev = strdup (argv[i]);
                char *action = strchr (ev, ':');
                *action++ = '\0';
                int frame = (int) (atof (ev) * 50 + 0.5);
                for (; last_frame < frame; last_frame++) {
                        script_lib_plymouth_on_refresh (state, ply_lib);
                        script_lib_sprite_refresh (sprite_lib);
                }
                char *arg = strchr (action, ':');
                if (arg) *arg++ = '\0';
                if (!strcmp (action, "progress"))
                        script_lib_plymouth_on_boot_progress (state, ply_lib, frame / 50.0, atof (arg));
                else if (!strcmp (action, "password")) {
                        char *prompt = strchr (arg, ':');
                        *prompt++ = '\0';
                        script_lib_plymouth_on_display_password (state, ply_lib, prompt, atoi (arg));
                } else if (!strcmp (action, "question")) {
                        char *prompt = strchr (arg, ':');
                        *prompt++ = '\0';
                        script_lib_plymouth_on_display_question (state, ply_lib, prompt, arg);
                } else if (!strcmp (action, "message"))
                        script_lib_plymouth_on_display_message (state, ply_lib, arg);
                else if (!strcmp (action, "hide"))
                        script_lib_plymouth_on_hide_message (state, ply_lib, arg);
                else if (!strcmp (action, "normal"))
                        script_lib_plymouth_on_display_normal (state, ply_lib);
                else if (!strcmp (action, "update"))
                        script_lib_plymouth_on_system_update (state, ply_lib, atoi (arg));
                else if (!strcmp (action, "status"))
                        script_lib_plymouth_on_update_status (state, ply_lib, arg);
                else if (!strcmp (action, "quit"))
                        script_lib_plymouth_on_quit (state, ply_lib);
                else if (!strcmp (action, "caps"))
                        caps_state = atoi (arg);
                else if (!strcmp (action, "dump")) {
                        char path[4096];
                        snprintf (path, sizeof(path), "%s%s.ppm", prefix, arg);
                        dump (fake_display_get_buffer (display), path);
                } else
                        fprintf (stderr, "unknown event %s\n", action);
                free (ev);
        }
        (void) image_lib; (void) math_lib; (void) string_lib;
        return 0;
}
