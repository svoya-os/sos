#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Stage branding/ into system paths, following the packaging map in branding/README.md:
#   plymouth/<theme>/ (a dir with <theme>.plymouth or .script) -> /usr/share/plymouth/themes/<theme>/
#       (plymouth/frames = preview renders and plymouth/harness = a test tool: not shipped)
#   grub/svoya/ + PFF2 fonts from grub/make-fonts.sh -> /usr/share/grub/themes/svoya/ (postinst copies
#       it to /boot/grub/themes/svoya), grub/default-grub.cfg -> /etc/default/grub.d/90-sos-theme.cfg
#   sounds/svoya/          -> /usr/share/sounds/svoya/ (+ /usr/share/svoya/sounds -> ../sounds/svoya;
#                             branding/README.md says ../../sounds/svoya, which would be /usr/sounds)
#   wallpapers/            -> /usr/share/svoya/wallpapers/ (+ /usr/share/backgrounds/svoya link)
#   logo/icon/             -> hicolor icon "sos" (png sizes, scalable sos.svg, symbolic sos-symbolic.svg)
#   logo/svg/*, out/logo/* -> /usr/share/svoya/branding/logo/
#   fastfetch/*            -> /usr/share/svoya/fastfetch/ (config.jsonc also -> /etc/xdg/fastfetch/)
#   adw-gtk3 (downloaded, pinned) -> /usr/share/themes/adw-gtk3{,-dark}/
# os/root/** (os-release, lsb-release, issue, motd) ships in svoya-base, which diverts base-files.
set -euo pipefail
: "${SVOYA_SRC:?}" "${PKG_DIR:?}"
b=$SVOYA_SRC/branding
f=$PKG_DIR/files
mkdir -p "$f"

copy_tree() { # SRC DEST (skips generators, docs and caches)
    [ -d "$1" ] || return 0
    mkdir -p "$2"
    tar -C "$1" --exclude='*.py' --exclude='__pycache__' --exclude='*.md' --exclude='*.sh' \
        -cf - . | tar -C "$2" -xf -
}

# Plymouth: only real themes.
for t in "$b"/plymouth/*/; do
    name=$(basename "$t")
    [ -f "$t/$name.plymouth" ] || [ -f "$t/$name.script" ] || continue
    dest=$f/usr/share/plymouth/themes/$name
    copy_tree "$t" "$dest"
    if [ ! -f "$dest/$name.plymouth" ]; then
        cat >"$dest/$name.plymouth" <<PLY
[Plymouth Theme]
Name=SOS ($name)
Description=SOS boot splash
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/$name
ScriptFile=/usr/share/plymouth/themes/$name/$name.script
PLY
    fi
    echo "    plymouth theme: $name" >&2
done
[ -f "$f/usr/share/plymouth/themes/svoya-signal/svoya-signal.plymouth" ] ||
    echo "warning: the svoya-signal Plymouth theme is missing (branding/plymouth/svoya-signal)" >&2

# GRUB theme and its fonts ("Svoya Mono", converted from IBM Plex Mono by grub-mkfont).
if [ -f "$b/grub/svoya/theme.txt" ]; then
    theme=$f/usr/share/grub/themes/svoya
    copy_tree "$b/grub/svoya" "$theme"
    if command -v grub-mkfont >/dev/null; then
        bash "$b/grub/make-fonts.sh" "$SVOYA_SRC/design/fonts/IBMPlexMono-Regular.ttf" "$theme" >&2 ||
            echo "warning: grub/make-fonts.sh failed; the GRUB theme falls back to GRUB's font" >&2
    else
        echo "warning: grub-mkfont not found (grub2-common); the GRUB theme falls back to GRUB's font" >&2
    fi
    if [ -f "$b/grub/default-grub.cfg" ]; then
        install -D -m 0644 "$b/grub/default-grub.cfg" "$f/etc/default/grub.d/90-sos-theme.cfg"
    fi
fi

# Sounds (freedesktop sound theme "svoya"; ARCHITECTURE §3 path is the link).
if [ -d "$b/sounds/svoya" ]; then
    copy_tree "$b/sounds/svoya" "$f/usr/share/sounds/svoya"
    mkdir -p "$f/usr/share/svoya"
    ln -sfn ../sounds/svoya "$f/usr/share/svoya/sounds"
fi

# Wallpapers (wallpapers.json uses paths relative to /usr/share/svoya/wallpapers).
copy_tree "$b/wallpapers" "$f/usr/share/svoya/wallpapers"
if [ -d "$f/usr/share/svoya/wallpapers" ]; then
    mkdir -p "$f/usr/share/backgrounds"
    ln -sfn ../svoya/wallpapers "$f/usr/share/backgrounds/svoya"
fi

# Logos and the "sos" icon (os-release LOGO=sos).
copy_tree "$b/logo/svg" "$f/usr/share/svoya/branding/logo"
copy_tree "$b/out/logo" "$f/usr/share/svoya/branding/logo"
if [ -f "$b/logo/icon/sos.svg" ]; then
    install -Dm0644 "$b/logo/icon/sos.svg" "$f/usr/share/icons/hicolor/scalable/apps/sos.svg"
fi
if [ -f "$b/logo/icon/sos-symbolic.svg" ]; then
    install -Dm0644 "$b/logo/icon/sos-symbolic.svg" "$f/usr/share/icons/hicolor/symbolic/apps/sos-symbolic.svg"
fi
for png in "$b"/logo/icon/png/sos-*.png; do
    [ -f "$png" ] || continue
    size=$(basename "$png" .png | grep -o '[0-9]\+$' || true)
    [ -n "$size" ] && install -Dm0644 "$png" "$f/usr/share/icons/hicolor/${size}x${size}/apps/sos.png"
done
[ -f "$f/usr/share/icons/hicolor/scalable/apps/sos.svg" ] ||
    echo "warning: branding/logo/icon/sos.svg missing; no scalable \"sos\" icon" >&2

# SOS ASCII: the folders in characters (branding/icons/generate.py) and the cursor
# (branding/cursors/generate.py); the shell switches to them with the symbol layer
for t in "$b"/icons/SOS-Symbols-*/ "$b"/cursors/sos-symbols/; do
    [ -f "$t/index.theme" ] || continue
    copy_tree "$t" "$f/usr/share/icons/$(basename "$t")"
done
# adw-gtk3 (LGPL-2.1, github.com/lassekongo83/adw-gtk3): libadwaita's look for GTK3 apps. Unlike
# Adwaita it draws with the named colors ~/.config/gtk-3.0/gtk.css defines (`sos theme apply`), so
# Files and the other GTK3 apps wear the SOS theme. Ubuntu does not package it: the release
# tarball, pinned by its SHA-256 (the hash GitHub shows for the asset). Without the network the
# build goes on and GTK3 apps keep Adwaita.
ADW_GTK3_VERSION=6.5
ADW_GTK3_SHA256=a81780fadfc432be0fc3d89c4ebb41aa28e4f032d42c36f9789c57dd10cfa41c
adw=$(mktemp -d)
if curl -fsSL --retry 5 --retry-delay 5 -o "$adw/adw-gtk3.tar.xz" \
        "https://github.com/lassekongo83/adw-gtk3/releases/download/v$ADW_GTK3_VERSION/adw-gtk3v$ADW_GTK3_VERSION.tar.xz" &&
    echo "$ADW_GTK3_SHA256  $adw/adw-gtk3.tar.xz" | sha256sum -c --quiet -; then
    mkdir -p "$adw/x"
    tar -C "$adw/x" -xJf "$adw/adw-gtk3.tar.xz"
    for name in adw-gtk3 adw-gtk3-dark; do
        src=$(find "$adw/x" -maxdepth 3 -type d -name "$name" -exec test -f '{}/gtk-3.0/gtk.css' ';' -print -quit)
        if [ -n "$src" ]; then
            copy_tree "$src" "$f/usr/share/themes/$name"
            echo "    GTK theme: $name $ADW_GTK3_VERSION" >&2
        else
            echo "warning: $name is not in adw-gtk3v$ADW_GTK3_VERSION.tar.xz; GTK3 apps keep Adwaita" >&2
        fi
    done
else
    echo "warning: adw-gtk3 $ADW_GTK3_VERSION not downloaded or its hash differs; GTK3 apps keep Adwaita" >&2
fi
rm -rf "$adw"

# fastfetch
copy_tree "$b/fastfetch" "$f/usr/share/svoya/fastfetch"
if [ -f "$b/fastfetch/config.jsonc" ]; then
    install -Dm0644 "$b/fastfetch/config.jsonc" "$f/etc/xdg/fastfetch/config.jsonc"
fi
find "$f" -type d -empty -delete
mkdir -p "$f"
