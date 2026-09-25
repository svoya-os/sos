#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# UpsiL from the pinned commit of github.com/svoya-os/upsil (or UPSIL_SRC_DIR), staged as:
#   upsil/                      -> /usr/lib/python3/dist-packages/upsil   (importable: `upsil build` output runs)
#   the `upsil` command         -> /usr/bin/upsil
#   editor/upsil.lang           -> GtkSourceView 4 and 5 (Mousepad, GNOME Text Editor)
#   editor/upsil.xml            -> KSyntaxHighlighting (Kate)
#   text/x-upsil for *.upl      -> /usr/share/mime/packages/upsil.xml
#   README, docs, examples      -> /usr/share/doc/upsil/
#   skills/upsil/SKILL.md       -> /usr/share/svoya/jackson/skills/upsil/ (Jackson writes UpsiL)
#   /usr/lib/upsil/path/upsil   -> a folder with only `upsil` in it: `sos run x.upl` puts it on
#                                  PYTHONPATH to run a program in a project's .venv (torch there)
set -euo pipefail
: "${SVOYA_SRC:?}" "${PKG_DIR:?}"
# shellcheck source=packages/lib/common.sh
. "$SVOYA_SRC/packages/lib/common.sh"
# shellcheck source=packages/versions.env
. "$SVOYA_SRC/packages/versions.env"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
if [ -n "${UPSIL_SRC_DIR:-}" ]; then
    [ -f "$UPSIL_SRC_DIR/upsil/__init__.py" ] || die "UPSIL_SRC_DIR=$UPSIL_SRC_DIR is not an UpsiL checkout"
    mkdir -p "$work/src"
    cp -a "$UPSIL_SRC_DIR/." "$work/src/"
else
    case $UPSIL_COMMIT in *@*|"") die "UPSIL_COMMIT is not pinned (packages/versions.env)" ;; esac
    git_fetch_commit "$UPSIL_REPO" "$UPSIL_COMMIT" "$work/src"
fi
src=$work/src

# the checkout must be the version the package claims to be
got=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$src/upsil/__init__.py")
[ "$got" = "$UPSIL_VERSION" ] || die "UpsiL source is $got, versions.env says $UPSIL_VERSION"

files=$PKG_DIR/files
rm -rf "$files"
python3 "$SVOYA_SRC/packages/lib/stage_pyapp.py" --src "$src" --package upsil --dest "$files" \
    --libdir usr/lib/python3/dist-packages >/dev/null

install -d "$files/usr/bin"
cat >"$files/usr/bin/upsil" <<'PY'
#!/usr/bin/python3
# The UpsiL command (packaged for SOS). SPDX-License-Identifier: Apache-2.0
import sys

from upsil.cli import main

sys.exit(main())
PY
chmod 0755 "$files/usr/bin/upsil"

install -D -m 0644 "$src/editor/upsil.lang" "$files/usr/share/gtksourceview-4/language-specs/upsil.lang"
install -D -m 0644 "$src/editor/upsil.lang" "$files/usr/share/gtksourceview-5/language-specs/upsil.lang"
install -D -m 0644 "$src/editor/upsil.xml" "$files/usr/share/org.kde.syntax-highlighting/syntax/upsil.xml"
install -D -m 0644 "$PKG_DIR/debian/upsil-mime.xml" "$files/usr/share/mime/packages/upsil.xml"

doc=$files/usr/share/doc/upsil
install -d "$doc/docs" "$doc/examples"
install -m 0644 "$src/README.md" "$src/README.en.md" "$src/CHANGELOG.md" "$doc/"
install -m 0644 "$src"/docs/*.md "$doc/docs/"
cp -a "$src/examples/." "$doc/examples/"
find "$doc" -name '__pycache__' -prune -exec rm -rf {} +

# the assistant's cheat sheet for the language (an Agent Skill; system skills are read-only)
if [ -f "$src/skills/upsil/SKILL.md" ]; then
    install -D -m 0644 "$src/skills/upsil/SKILL.md" "$files/usr/share/svoya/jackson/skills/upsil/SKILL.md"
else
    warn "no skills/upsil/SKILL.md in this UpsiL tree: Jackson will not know the language"
fi

# only `upsil`, never all of dist-packages (that would shadow a venv's own numpy or torch)
install -d "$files/usr/lib/upsil/path"
ln -s ../../python3/dist-packages/upsil "$files/usr/lib/upsil/path/upsil"
