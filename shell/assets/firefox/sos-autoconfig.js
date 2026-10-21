// SPDX-License-Identifier: Apache-2.0
// SOS: Firefox reads /usr/lib/firefox/sos.cfg at start (the Phosphor new tab and frame). Shipped by
// svoya-shell (packages/svoya-shell/prepare.sh) as /usr/lib/firefox/defaults/pref/sos-autoconfig.js.
pref("general.config.filename", "sos.cfg");
pref("general.config.obscure_value", 0);
pref("general.config.sandbox_enabled", false);
