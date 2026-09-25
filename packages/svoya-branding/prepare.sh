#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Stage branding/ (branding team) into system paths:
#   branding/plymouth/<theme>/   -> /usr/share/plymouth/themes/<theme>/  (.plymouth generated if missing)
#   branding/grub/svoya/         -> /usr/share/grub/themes/svoya/        (+ GRUB_THEME when theme.txt exists)
#   branding/sounds/svoya/       -> /usr/share/svoya/sounds/  (+ /usr/share/sounds/svoya link)
#   branding/wallpapers/<theme>/ -> /usr/share/svoya/wallpapers/<theme>/ (+ wallpapers.json)
#   branding/logo/**             -> /usr/share/svoya/logo/, icons "sos" and "svoya" in hicolor
#   branding/fastfetch/*         -> /usr/share/svoya/fastfetch/ (config.jsonc -> /etc/xdg/fastfetch/)
set -euo pipefail
: "${SVOYA_SRC:?}" "${PKG_DIR:?}"
b=$SVOYA_SRC/branding
f=$PKG_DIR/files
mkdir -p "$f"

copy_tree() { # SRC DEST (skips generators and caches)
    [ -d "$1" ] || return 0
    mkdir -p "$2"
    tar -C "$1" --exclude='*.py' --exclude='__pycache__' --exclude='*.md' -cf - . | tar -C "$2" -xf -
}

# Plymouth
for t in "$b"/plymouth/*/; do
    [ -d "$t" ] || continue
    name=$(basename "$t")
    dest=$f/usr/share/plymouth/themes/$name
    copy_tree "$t" "$dest"
    if [ ! -f "$dest/$name.plymouth" ] && [ -f "$dest/$name.script" ]; then
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
done

# GRUB
if [ -f "$b/grub/svoya/theme.txt" ]; then
    copy_tree "$b/grub/svoya" "$f/usr/share/grub/themes/svoya"
    mkdir -p "$f/etc/default/grub.d"
    printf '# SOS boot menu theme (svoya-branding).\nGRUB_THEME=/usr/share/grub/themes/svoya/theme.txt\n' \
        >"$f/etc/default/grub.d/51-svoya-theme.cfg"
fi

# Sounds
if [ -d "$b/sounds/svoya" ]; then
    copy_tree "$b/sounds/svoya" "$f/usr/share/svoya/sounds"
    mkdir -p "$f/usr/share/sounds"
    ln -sfn ../svoya/sounds "$f/usr/share/sounds/svoya"
fi

# Wallpapers
copy_tree "$b/wallpapers" "$f/usr/share/svoya/wallpapers"
if [ -d "$f/usr/share/svoya/wallpapers" ]; then
    mkdir -p "$f/usr/share/backgrounds"
    ln -sfn ../svoya/wallpapers "$f/usr/share/backgrounds/svoya"
fi

# Logos and icons
copy_tree "$b/logo/svg" "$f/usr/share/svoya/logo"
copy_tree "$b/out/logo" "$f/usr/share/svoya/logo"
if [ -f "$b/logo/icon/svoya.svg" ]; then
    install -Dm0644 "$b/logo/icon/svoya.svg" "$f/usr/share/icons/hicolor/scalable/apps/svoya.svg"
    install -Dm0644 "$b/logo/icon/svoya.svg" "$f/usr/share/icons/hicolor/scalable/apps/sos.svg"
fi
if [ -f "$b/logo/icon/svoya-symbolic.svg" ]; then
    install -Dm0644 "$b/logo/icon/svoya-symbolic.svg" "$f/usr/share/icons/hicolor/symbolic/apps/sos-symbolic.svg"
fi
for png in "$b"/logo/icon/png/*.png; do
    [ -f "$png" ] || continue
    size=$(basename "$png" .png | grep -o '[0-9]\+$' || true)
    [ -n "$size" ] && install -Dm0644 "$png" "$f/usr/share/icons/hicolor/${size}x${size}/apps/sos.png"
done

# fastfetch
copy_tree "$b/fastfetch" "$f/usr/share/svoya/fastfetch"
if [ -f "$b/fastfetch/config.jsonc" ]; then
    install -Dm0644 "$b/fastfetch/config.jsonc" "$f/etc/xdg/fastfetch/config.jsonc"
fi
find "$f" -type d -empty -delete
mkdir -p "$f"
