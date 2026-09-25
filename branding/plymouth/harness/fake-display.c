/* Headless stand-in for ply-pixel-display.c: one in-memory display, no renderer.
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
#include <stdlib.h>
#include "ply-pixel-display.h"

struct _ply_pixel_display
{
        unsigned long                    width;
        unsigned long                    height;
        ply_pixel_display_draw_handler_t draw_handler;
        void                            *draw_handler_user_data;
        ply_pixel_buffer_t              *buffer;
        int                              pause_count;
};

ply_pixel_display_t *
fake_display_new (unsigned long width, unsigned long height)
{
        ply_pixel_display_t *d = calloc (1, sizeof(*d));
        d->width = width;
        d->height = height;
        d->buffer = ply_pixel_buffer_new (width, height);
        return d;
}

ply_pixel_buffer_t *fake_display_get_buffer (ply_pixel_display_t *d) { return d->buffer; }
unsigned long ply_pixel_display_get_width (ply_pixel_display_t *d) { return d->width; }
unsigned long ply_pixel_display_get_height (ply_pixel_display_t *d) { return d->height; }
int ply_pixel_display_get_device_scale (ply_pixel_display_t *d) { (void) d; return 1; }
void ply_pixel_display_pause_updates (ply_pixel_display_t *d) { d->pause_count++; }
void ply_pixel_display_unpause_updates (ply_pixel_display_t *d) { d->pause_count--; }

void
ply_pixel_display_set_draw_handler (ply_pixel_display_t             *d,
                                    ply_pixel_display_draw_handler_t handler,
                                    void                            *user_data)
{
        d->draw_handler = handler;
        d->draw_handler_user_data = user_data;
}

void
ply_pixel_display_draw_area (ply_pixel_display_t *d, int x, int y, int width, int height)
{
        ply_rectangle_t clip = { .x = x, .y = y, .width = width, .height = height };

        if (d->draw_handler == NULL)
                return;
        ply_pixel_buffer_push_clip_area (d->buffer, &clip);
        d->draw_handler (d->draw_handler_user_data, d->buffer, x, y, width, height, d);
        ply_pixel_buffer_pop_clip_area (d->buffer);
}
