#!/usr/bin/env bash
# Build a headless harness around Plymouth's own script engine (no DRM, no daemon), then run
# svoya-signal.script through it: parse, execute, every callback, and dump real frames.
#
#   branding/plymouth/harness/build.sh [PLYMOUTH_SRC]      # clones plymouth 24.004 if not given
#   branding/plymouth/harness/run.sh                       # renders frames to branding/plymouth/frames/engine-*.png
#
# Needs: gcc, libpng, freetype2, fontconfig (fc-match, for the label plugin). The harness links
# GPL-2.0-or-later Plymouth code; it is a test tool and is not shipped.
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
build="${HARNESS_BUILD:-$here/.build}"
src="${1:-$build/plymouth}"
mkdir -p "$build"

if [[ ! -d "$src/src/plugins/splash/script" ]]; then
    # mirror of the Debian packaging of plymouth 24.004.60 (upstream lives on gitlab.freedesktop.org)
    git clone --depth 1 https://github.com/deepin-community/plymouth "$src"
fi

S="$src/src"
cat > "$build/config.h" <<EOF
#define PLYMOUTH_PLUGIN_PATH "$build/plugins/"
#define PLYMOUTH_THEME_PATH "/usr/share/plymouth/themes/"
#define PLYMOUTH_RUNTIME_DIR "/run/plymouth"
#define PLYMOUTH_RUNTIME_THEME_PATH "/run/plymouth/themes/"
#define PLYMOUTH_POLICY_DIR "/usr/share/plymouth/"
#define PLYMOUTH_CONF_DIR "/etc/plymouth/"
#define PLYMOUTH_TIME_DIRECTORY "/var/lib/plymouth/"
#define BOOT_TTY "/dev/tty1"
#define SHUTDOWN_TTY "/dev/tty63"
#define RELEASE_FILE "/etc/os-release"
#define PLYMOUTH_LOGO_FILE "/usr/share/plymouth/debian-logo.png"
#define HAVE_UDEV 0
#define PLY_ENABLE_SYSTEMD_INTEGRATION 0
#define PLY_ENABLE_TRACING 0
EOF

for lib in image math plymouth sprite string; do
    python3 "$S/plugins/splash/script/generate_script_string_header.py" \
        "$S/plugins/splash/script/script-lib-$lib.script" > "$build/script-lib-$lib.script.h"
done

inc=(-I"$build" -I"$here/stubs" -I"$S" -I"$S/libply" -I"$S/libply-splash-core" -I"$S/libply-splash-graphics"
     -I"$S/plugins/splash/script" $(pkg-config --cflags libpng freetype2))
cflags=(-std=gnu11 -O1 -g -fPIC -D_GNU_SOURCE -w -include "$build/config.h")

libply=(ply-array ply-bitarray ply-buffer ply-hashtable ply-list ply-logger ply-rectangle ply-region ply-utils ply-key-file)
objs=()
for f in "${libply[@]}"; do objs+=("$S/libply/$f.c"); done
objs+=("$S/libply-splash-core/ply-pixel-buffer.c" "$S/libply-splash-core/ply-rich-text.c"
       "$S/libply-splash-graphics/ply-image.c" "$S/libply-splash-graphics/ply-label.c")
for f in script script-scan script-parse script-execute script-object script-debug \
         script-lib-image script-lib-sprite script-lib-plymouth script-lib-math script-lib-string; do
    objs+=("$S/plugins/splash/script/$f.c")
done

mkdir -p "$build/plugins"
gcc "${cflags[@]}" "${inc[@]}" -rdynamic -o "$build/harness" \
    "$here/harness.c" "$here/fake-display.c" "${objs[@]}" \
    $(pkg-config --libs libpng) -lm -ldl
gcc "${cflags[@]}" "${inc[@]}" -shared -o "$build/plugins/label-freetype.so" \
    "$S/plugins/controls/label-freetype/plugin.c" $(pkg-config --libs freetype2) -lm
echo "built $build/harness"
