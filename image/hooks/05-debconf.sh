#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Answers for packages that ask questions: keyboard us,ru (Alt+Shift), locales, timezone,
# and the groups casper gives the live user (incl. "ai" for the model store /srv/ai).
set -euo pipefail
root=$1
# shellcheck source=image/lib/common.sh
. "$SVOYA_IMAGE/lib/common.sh"

in_chroot "$root" debconf-set-selections <<EOF
keyboard-configuration keyboard-configuration/modelcode string pc105
keyboard-configuration keyboard-configuration/layoutcode string us,ru
keyboard-configuration keyboard-configuration/variantcode string ,
keyboard-configuration keyboard-configuration/optionscode string grp:alt_shift_toggle
keyboard-configuration keyboard-configuration/toggle select Alt+Shift
console-setup console-setup/charmap47 select UTF-8
console-setup console-setup/codeset47 select Guess optimal character set
locales locales/locales_to_be_generated multiselect en_US.UTF-8 UTF-8, ru_RU.UTF-8 UTF-8
locales locales/default_environment_locale select ${LIVE_LOCALE}
tzdata tzdata/Areas select Etc
tzdata tzdata/Zones/Etc select UTC
user-setup passwd/user-default-groups string adm cdrom dip lpadmin plugdev sudo video render audio ai
EOF
