#!/usr/bin/env bash
# Run svoya-signal.script in Plymouth's real script engine (see build.sh) and write frames to
# branding/plymouth/frames/engine-*.png. Any parse or execution error printed by the engine fails the run.
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
build="${HARNESS_BUILD:-$here/.build}"
theme="$here/../svoya-signal"
frames="$here/../frames"
fonts="$(cd "$here/../../../design/fonts" && pwd)"
mkdir -p "$frames" "$build/out"

# fontconfig that only knows the design fonts, with IBM Plex as sans/monospace — the same setup
# the initrd needs so that Image.Text renders Plex with Cyrillic
cat > "$build/fonts.conf" <<EOF
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <dir>$fonts</dir>
  <cachedir>$build/fc-cache</cachedir>
  <alias><family>monospace</family><prefer><family>IBM Plex Mono</family></prefer></alias>
  <alias><family>sans-serif</family><prefer><family>IBM Plex Sans</family></prefer></alias>
</fontconfig>
EOF
export FONTCONFIG_FILE="$build/fonts.conf"
# plymouthd calls setlocale(LC_ALL, ""): with label-freetype, Cyrillic needs a UTF-8 locale in the initrd
export LANG=C.UTF-8 LC_ALL=C.UTF-8

prompt="Please enter passphrase for disk Samsung SSD 990 PRO (luks-3f1c)"
log="$build/out/engine.log"
: > "$log"
run() {  # run MODE NAME EVENTS...
    local mode="$1" name="$2"; shift 2
    "$build/harness" "$theme/" "$theme/svoya-signal.script" "$mode" 1920 1080 "$build/out/engine-" "$@" >>"$log" 2>&1
}

run boot power-on "0.10:dump:1-power-on"
run boot warm-up "0.52:dump:2-warm-up"
run boot boot24 "0.2:progress:0.24" "1.93:dump:3-boot-24"
run boot boot71 "0.2:progress:0.71" "4.21:message:Проверка файловой системы на /dev/nvme0n1p2 — 37 %" "5.21:dump:4-boot-71-message"
run boot unlock "0.2:progress:0.31" "6.64:password:9:$prompt" "7.64:dump:5-unlock"
run shutdown shutdown "2.43:dump:6-shutdown"
# every other callback and mode, for errors only
run updates updates "0.5:update:10" "1.5:update:42" "3:dump:x-updates"
run system-upgrade upgrade "0.5:update:77" "2:dump:x-upgrade"
run firmware-upgrade firmware "2:dump:x-firmware"
run reboot reboot "2:dump:x-reboot"
run system-reset reset "2:dump:x-reset"
run boot everything "0.2:progress:0.1" "1:status:fsckd-cancel-msg:Нажмите C, чтобы отменить проверку" \
    "1.2:message:one" "1.3:message:two" "1.4:message:three" "1.5:message:four" "1.6:hide:three" \
    "2:password:0:$prompt" "2.1:password:3:$prompt" "2.2:caps:1" "2.4:password:40:$prompt" "2.6:dump:x-caps" \
    "3:normal" "3.5:question:да:Продолжить без сети? [д/н]" "4.5:dump:x-question" "5:normal" "5.5:progress:0.9" "6:quit" "7:dump:x-quit"
SVOYA_LANG=en run boot english "0.2:progress:0.5" "2.5:dump:x-english"
# the failure mode to avoid on real systems: plain C locale → Cyrillic from Image.Text becomes tofu
LANG=C LC_ALL=C run boot c-locale "0.2:progress:0.71" "4.21:message:Проверка файловой системы на /dev/nvme0n1p2 — 37 %" "5.21:dump:x-c-locale"

if grep -E "error|Error|PARSE FAILED" "$log"; then
    echo "engine reported errors (see $log)" >&2
    exit 1
fi
for f in "$build"/out/engine-*.ppm; do
    python3 -c "import sys; from PIL import Image; Image.open(sys.argv[1]).save(sys.argv[2], optimize=True)" \
        "$f" "$frames/engine-$(basename "${f%.ppm}" | sed 's/^engine-//').png"
done
echo "engine frames in $frames (no engine errors)"
