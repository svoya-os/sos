#!/usr/bin/env bash
# Regenerate every SOS brand asset, then the contact sheet. See branding/README.md.
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

python3 branding/logo/generate.py
python3 branding/wallpapers/generate.py
python3 branding/plymouth/generate.py
python3 branding/grub/generate.py          # uses the wallpaper renderer for its background
python3 branding/sounds/generate.py
python3 branding/os/generate.py
python3 branding/tools/contact_sheet.py

if [[ "${WITH_PLYMOUTH_ENGINE:-0}" == 1 ]]; then   # optional: run the theme in plymouth's own engine
    branding/plymouth/harness/build.sh
    branding/plymouth/harness/run.sh
fi
