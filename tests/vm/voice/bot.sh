#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# The voice bot's hands inside the VM (tests/vm/voice.json). Fetched from the CI host, so that the
# bot types one short line instead of a long one (a long line lags and garbles in the VM).
#   bot.sh URL setup   the phrases, a virtual microphone (pw-loopback) the voice service listens to
#   bot.sh URL talk    say each phrase when the voice service says it listens, then press the mic
set -u
serve=${1:?}
case "${2:-setup}" in
setup)
    if ! curl -sf "$serve/q1.wav" -o /tmp/q1.wav || ! curl -sf "$serve/q2.wav" -o /tmp/q2.wav; then
        logger -t sos-vm-test SOS-STEP phrases-missing
        exit 1
    fi
    mkdir -p ~/.config/svoya
    echo SVOYA_VOICE_SOURCE=vmic >~/.config/svoya/voice.env
    pw-loopback -m '[ MONO ]' --capture-props='media.class=Audio/Sink node.name=vmic-in' \
        --playback-props='media.class=Audio/Source node.name=vmic node.description=vmic' >/dev/null 2>&1 &
    sleep 2
    systemctl --user restart svoya-voice
    wpctl status | grep -iA5 sources
    logger -t sos-vm-test SOS-STEP mic-ready
    ;;
talk)
    journalctl --user -f -n0 -u svoya-voice | while read -r line; do
        case "$line" in
        *"listening (tap)"*) sleep 1; pw-play --target vmic-in /tmp/q1.wav ;;
        *"listening (follow)"*) sleep 1; pw-play --target vmic-in /tmp/q2.wav ;;
        esac
    done >/dev/null 2>&1 &
    sleep 1
    quickshell -p /usr/share/svoya/shell ipc call jackson talk
    ;;
esac
