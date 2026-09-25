#!/usr/bin/env bash
# SOS module helpers, sourced by modules/<id>/*.sh.  SPDX-License-Identifier: Apache-2.0
#
# House rules for module scripts:
#   * idempotent: running install twice changes nothing the second time
#   * never `curl | sh`: downloads go to a temp file, are verified (sha256 from the publisher or the
#     GitHub release "digest"), then installed; every command that changes the system is echoed first
#   * honest: say how much disk/VRAM a step costs; never start AI services by themselves
#   * environment is clean (sos passes PATH, LANG and SVOYA_* only)
set -euo pipefail

sv_say() { # sv_say "English" "Русский"
  if [[ "${SVOYA_LANG:-en}" == ru ]]; then printf '  › %s\n' "$2"; else printf '  › %s\n' "$1"; fi
}
sv_warn() { printf '  ! %s\n' "$*" >&2; }
sv_die() { printf '  × %s\n' "$*" >&2; exit 1; }
sv_run() { printf '  $ %s\n' "$*"; "$@"; }          # show, then run
sv_have() { command -v "$1" >/dev/null 2>&1; }
sv_require_root() { [[ $(id -u) -eq 0 ]] || sv_die "run through sos (it elevates with pkexec)"; }

# sv_write PATH [MODE] < content — write only when the content differs (idempotent)
sv_write() {
  local path=$1 mode=${2:-0644} tmp
  tmp=$(mktemp)
  cat >"$tmp"
  if [[ -f "$path" ]] && cmp -s "$tmp" "$path"; then rm -f "$tmp"; return 0; fi
  install -D -m "$mode" "$tmp" "$path"
  rm -f "$tmp"
  printf '  › wrote %s\n' "$path"
}

# sv_apt_available PKG — is the package known to apt (archive or configured repos)?
sv_apt_available() { apt-cache show "$1" >/dev/null 2>&1; }

# sv_fetch URL SHA256 OUT — download to a temp file, verify, then move into place
sv_fetch() {
  local url=$1 sha=$2 out=$3 tmp
  [[ "$sha" =~ ^[0-9a-f]{64}$ ]] || sv_die "refusing to download without a sha256: $url"
  tmp=$(mktemp "${TMPDIR:-/tmp}/sos-fetch.XXXXXX")
  printf '  ↓ %s\n' "$url"
  if ! curl --proto '=https' --tlsv1.2 -fL --retry 3 --silent --show-error -o "$tmp" "$url"; then
    rm -f "$tmp"; sv_die "download failed: $url"
  fi
  if ! echo "$sha  $tmp" | sha256sum -c --quiet - >/dev/null 2>&1; then
    rm -f "$tmp"; sv_die "checksum mismatch for $url (expected $sha)"
  fi
  install -D -m 0644 "$tmp" "$out"
  rm -f "$tmp"
}

# sv_github_asset OWNER/REPO TAG|latest REGEX → prints "<name> <url> <sha256>" of the first matching asset.
# The sha256 is the "digest" GitHub computes for every release asset (API field), so a tampered
# mirror cannot pass; no digest → empty field → sv_fetch refuses.
sv_github_asset() {
  local repo=$1 tag=$2 regex=$3 api
  if [[ "$tag" == latest ]]; then api="https://api.github.com/repos/$repo/releases/latest"
  else api="https://api.github.com/repos/$repo/releases/tags/$tag"; fi
  curl --proto '=https' -fsSL "$api" | python3 -c '
import json, re, sys
rel = json.load(sys.stdin)
for a in rel.get("assets", []):
    if re.fullmatch(sys.argv[1], a["name"]):
        d = a.get("digest") or ""
        print(a["name"], a["browser_download_url"], d.split(":", 1)[1] if d.startswith("sha256:") else "")
        break
' "$regex"
}

# sv_github_install OWNER/REPO TAG REGEX BIN [MEMBER] — install a verified release binary to BIN.
# Archives (.tar.gz/.tgz/.tar.zst/.zip) are unpacked in a temp dir and MEMBER (default: basename BIN)
# is taken from inside.
sv_github_install() {
  local repo=$1 tag=$2 regex=$3 bin=$4 member=${5:-} line name url sha tmpd
  line=$(sv_github_asset "$repo" "$tag" "$regex") || sv_die "cannot query GitHub releases of $repo"
  read -r name url sha <<<"$line"
  [[ -n "${url:-}" ]] || sv_die "no asset matching $regex in $repo $tag"
  tmpd=$(mktemp -d)
  sv_fetch "$url" "${sha:-}" "$tmpd/$name"
  member=${member:-$(basename "$bin")}
  case "$name" in
    *.tar.gz|*.tgz) tar -xzf "$tmpd/$name" -C "$tmpd" ;;
    *.tar.zst) tar --zstd -xf "$tmpd/$name" -C "$tmpd" ;;
    *.zip) python3 -m zipfile -e "$tmpd/$name" "$tmpd" ;;
    *) mv "$tmpd/$name" "$tmpd/$member" ;;
  esac
  local found
  found=$(find "$tmpd" -type f -name "$member" | head -n1)
  [[ -n "$found" ]] || { rm -rf "$tmpd"; sv_die "$member not found in $name"; }
  sv_run install -D -m 0755 "$found" "$bin"
  rm -rf "$tmpd"
}

# System-wide uv tools: /opt/svoya/uv-tools, shims in /usr/local/bin, pinned Python in /opt/svoya/python.
sv_uv_tool() {
  sv_have uv || sv_die "uv is missing (install base-ai first)"
  sv_run env UV_TOOL_DIR=/opt/svoya/uv-tools UV_TOOL_BIN_DIR=/usr/local/bin \
    UV_PYTHON_INSTALL_DIR=/opt/svoya/python uv tool install --upgrade "$@"
}
sv_uv_tool_remove() {
  sv_have uv || return 0
  env UV_TOOL_DIR=/opt/svoya/uv-tools UV_TOOL_BIN_DIR=/usr/local/bin uv tool uninstall "$@" 2>/dev/null || true
}

# sv_venv NAME PACKAGES... — isolated venv in /opt/svoya/venvs/NAME with the machine's torch backend
sv_venv() {
  local name=$1; shift
  local dir=/opt/svoya/venvs/$name
  sv_have uv || sv_die "uv is missing (install base-ai first)"
  [[ -x "$dir/bin/python" ]] || sv_run env UV_PYTHON_INSTALL_DIR=/opt/svoya/python uv venv --python 3.12 "$dir"
  sv_run env VIRTUAL_ENV="$dir" UV_PYTHON_INSTALL_DIR=/opt/svoya/python \
    uv pip install --python "$dir/bin/python" --torch-backend="${SVOYA_TORCH_BACKEND:-cpu}" "$@"
}

# Run a command as the human who asked (root scripts only).
sv_as_user() { runuser -u "$SVOYA_TARGET_USER" -- "$@"; }

# User scripts: systemctl --user without failing when there is no session bus (e.g. over ssh).
sv_user_systemctl() { systemctl --user "$@" 2>/dev/null || sv_warn "systemctl --user $* (no user session?)"; }

# Packages a script installs itself (vendor-specific, i386, …) are tracked so `remove` can undo
# exactly those: /var/lib/svoya/module-extra/<module>.apt
SV_EXTRA_DIR=${SVOYA_VAR_LIB:-/var/lib/svoya}/module-extra
sv_apt_track_install() { # sv_apt_track_install PKG... (only installs what is missing)
  local p new=()
  for p in "$@"; do dpkg-query -W -f='${db:Status-Abbrev}' "$p" 2>/dev/null | grep -q '^ii' || new+=("$p"); done
  ((${#new[@]})) || return 0
  sv_run apt-get install -y "${new[@]}"
  install -d "$SV_EXTRA_DIR"
  printf '%s\n' "${new[@]}" >>"$SV_EXTRA_DIR/${SVOYA_MODULE:?}.apt"
}
sv_apt_track_remove() {
  local f="$SV_EXTRA_DIR/${SVOYA_MODULE:?}.apt"
  [[ -f "$f" ]] || return 0
  mapfile -t pk <"$f"
  ((${#pk[@]})) && sv_run apt-get remove -y "${pk[@]}" || true
  rm -f "$f"
}
sv_flathub() { sv_run flatpak remote-add --system --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo; }
sv_flatpak_install() { sv_flathub; sv_run flatpak install --system -y --noninteractive flathub "$@"; }
sv_flatpak_remove() { local a; for a in "$@"; do flatpak info --system "$a" >/dev/null 2>&1 && sv_run flatpak uninstall --system -y --noninteractive "$a"; done; return 0; }
sv_arch() { case $(uname -m) in x86_64) echo x86_64 ;; aarch64|arm64) echo aarch64 ;; *) sv_die "unsupported CPU $(uname -m)" ;; esac; }
