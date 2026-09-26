#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Static checks for the build/CI side of the repository (also run by .github/workflows/ci.yml):
# syntax (bash -n / sh -n) and ShellCheck, YAML (workflows, Calamares configs), JSON, Python
# byte-compilation. (A comment line must not start with the word "shellcheck": ShellCheck would
# parse it as a directive and fail with SC1073.)
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
rc=0

mapfile -t shell_files < <(
    {
        # Build, packaging, installer and CI code (owned by the release engineering side).
        git ls-files --cached --others --exclude-standard -- \
            'image/*.sh' 'installer/*.sh' 'packages/*.sh' 'scripts/*.sh' 'tests/*.sh' 2>/dev/null ||
            find image installer packages scripts tests -name '*.sh'
        printf '%s\n' image/overlay-live/usr/lib/svoya/vm-test-agent image/overlay-live/usr/lib/svoya/live-user-groups \
            image/overlay-live/usr/lib/svoya/vm-test-installer \
            installer/sos-install installer/scripts/launch \
            packages/svoya-session/files/usr/bin/svoya-session packages/svoya-session/files/usr/lib/svoya/greeter-session \
            packages/svoya-session/files/usr/lib/svoya/session-keyboard packages/svoya-session/files/usr/lib/svoya/shell-run \
            packages/svoya-base/files/usr/lib/svoya/setup-snapper
    } | sort -u | while read -r f; do [ -f "$f" ] && echo "$f"; done
)
mapfile -t maint_scripts < <(find packages -path '*/debian/*' \( -name '*.preinst' -o -name '*.postinst' -o -name '*.prerm' -o -name '*.postrm' -o -name 'qt-private-deps' \) | sort)

echo "== syntax (${#shell_files[@]} bash, ${#maint_scripts[@]} sh)"
for f in "${shell_files[@]}"; do bash -n "$f" || rc=1; done
for f in "${maint_scripts[@]}"; do sh -n "$f" || rc=1; done

if command -v shellcheck >/dev/null; then
    echo "== shellcheck"
    shellcheck -x -S warning "${shell_files[@]}" || rc=1
    shellcheck -S warning -s sh "${maint_scripts[@]}" || rc=1
else
    echo "== shellcheck not installed; skipped"
fi

echo "== YAML"
python3 - <<'PY' || rc=1
import pathlib, sys
import yaml
bad = 0
paths = sorted(pathlib.Path(".github/workflows").glob("*.yml")) + sorted(pathlib.Path("installer").rglob("*.conf")) \
    + sorted(pathlib.Path("installer/branding").rglob("*.desc"))
for p in paths:
    try:
        yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        bad += 1
        print(f"{p}: {exc}", file=sys.stderr)
print(f"{len(paths)} YAML files, {bad} invalid")
sys.exit(1 if bad else 0)
PY

echo "== JSON"
python3 -c 'import json,sys; [json.load(open(p)) for p in sys.argv[1:]]; print(len(sys.argv)-1, "JSON files ok")' tests/vm/*.json || rc=1

echo "== QML (shell/tools/qmlcheck.py: syntax, imports, API, names QML refuses)"
python3 shell/tools/qmlcheck.py || rc=1

echo "== Python"
python3 -m py_compile tests/vm/*.py installer/scripts/*.py image/lib/*.py packages/lib/*.py installer/branding/generate.py || rc=1

exit "$rc"
