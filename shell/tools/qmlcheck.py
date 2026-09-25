#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Static checks for the SOS Shell QML (no Qt needed; Python stdlib only).

    python3 shell/tools/qmlcheck.py [shell-dir]

Checks every .qml / .js file under shell/ (symlinked module dirs are followed
once, by real path):

  syntax    balanced () [] {} — aware of strings, template literals, comments
            and JS regex literals
  imports   every object type (`Type {`), attached object and enum prefix
            (`WlrLayershell.layer`, `WlrLayer.Top`) comes from an imported
            module, from the file's own directory or from an imported qs.* module
  members   every `Theme.x`, `Strings.x` (and the other qs.core singletons)
            names a property, function or signal the singleton declares
  ids       no duplicate `id:` inside one file
  children  no child objects inside Quickshell/Qt types that have no default
            property (Process, Socket, IpcHandler, …) — a runtime error in QML
  qmldir    explicit qmldir files list every type of their directory, mark
            `pragma Singleton` files as singletons and name the right module
  glyphs    `glyph: "name"` literals exist in the icon registry (core/Icons.qml), and
            every registry path parses in Qt's PathSvg (no compact arc flags)
  links     greeter/ and setup/ link core, components and assets correctly
  ipc       every `$svoya_ipc <target> <fn>` keybinding in hypr/*.conf and every
            `ipc call <target> <fn>` in QML names an IpcHandler function
  types     no object type is exported by two unqualified imports (ambiguous)
  js        (when `node` is on PATH) every function body, handler and binding
            parses as JavaScript
  api       every property, grouped/attached property, handler, enum value,
            singleton member and `id.member` exists in Quickshell 0.3.1 /
            Qt 6.10 (tools/qmlapi.json, generated from their sources by
            gen_qmlapi.py) or in the shell's own components; no read-only or
            FINAL property is assigned/redeclared; children only go into types
            with a default property (tools/qmlapi_check.py)

Exit status 1 when anything is wrong. Output: one line per problem.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys

SHELL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parent.parent)

# ----------------------------------------------------------------------------- known types
QT = {
    "QtQml": "Binding Component Connections Instantiator QtObject Timer Qt Date Math JSON Number String "
             "Object Array Promise console Locale".split(),
    "QtQuick": ("AnimatedImage AnimatedSprite Animation AnimationController Behavior BorderImage Canvas "
                "ColorAnimation Column DoubleValidator Easing Flickable Flipable Flow FocusScope Font "
                "FontLoader FontMetrics FrameAnimation Gradient GradientStop Grid GridView Image IntValidator "
                "Item ItemGrabResult KeyEvent Keys LayoutMirroring ListElement ListModel ListView Loader "
                "MouseArea MultiPointTouchArea NumberAnimation OpacityAnimator ParallelAnimation "
                "ParentAnimation ParentChange PathView PauseAnimation PropertyAction PropertyAnimation "
                "PropertyChanges Rectangle RegularExpressionValidator Repeater Rotation RotationAnimation "
                "Row Scale ScaleAnimator ScriptAction SequentialAnimation ShaderEffect ShaderEffectSource "
                "SmoothedAnimation SpringAnimation Sprite SpriteSequence State StateChangeScript "
                "StateGroup SystemPalette Text TextEdit TextInput TextMetrics Transition Translate "
                "TapHandler HoverHandler WheelHandler DragHandler PointHandler Accessible EnterKey "
                "Window Screen XAnimator YAnimator Matrix4x4 PathLine PathArc PathSvg PathMove PathCubic "
                "PathQuad PathPolyline PathAngleArc PathRectangle Path PathCurve PathAttribute").split(),
    "QtQuick.Shapes": "Shape ShapePath LinearGradient RadialGradient ConicalGradient".split(),
    "QtQuick.Effects": "MultiEffect RectangularShadow".split(),
    "QtQuick.Layouts": "RowLayout ColumnLayout GridLayout StackLayout Layout".split(),
    "Quickshell": ("ShellRoot Scope Variants Singleton PanelWindow FloatingWindow PopupWindow QsWindow "
                   "LazyLoader Quickshell SystemClock DesktopEntries DesktopEntry Region RegionShape "
                   "Intersection ExclusionMode ElapsedTimer PersistentProperties ObjectModel ScriptModel "
                   "QsMenuAnchor QsMenuOpener BoundComponent ShellScreen Retainable RetainableLock "
                   "TransformWatcher EasingCurve Reloadable ColorQuantizer").split(),
    "Quickshell.Io": ("Process StdioCollector SplitParser Socket SocketServer FileView FileViewError "
                      "JsonAdapter JsonObject IpcHandler DataStream DataStreamParser").split(),
    "Quickshell.Wayland": ("WlrLayershell WlrLayer WlrKeyboardFocus WlSessionLock WlSessionLockSurface "
                           "ToplevelManager Toplevel ScreencopyView IdleMonitor IdleInhibitor "
                           "ShortcutInhibitor").split(),
    "Quickshell.Hyprland": ("Hyprland HyprlandMonitor HyprlandWorkspace HyprlandToplevel HyprlandIpcEvent "
                            "GlobalShortcut HyprlandFocusGrab HyprlandWindow").split(),
    "Quickshell.Services.Pipewire": ("Pipewire PwObjectTracker PwNode PwNodeAudio PwNodeLinkTracker "
                                     "PwNodePeakMonitor PwLink PwLinkGroup PwAudioChannel").split(),
    "Quickshell.Services.UPower": "UPower UPowerDevice UPowerDeviceState UPowerDeviceType PowerProfiles".split(),
    "Quickshell.Services.Notifications": ("NotificationServer Notification NotificationAction "
                                          "NotificationUrgency NotificationCloseReason").split(),
    "Quickshell.Services.Pam": "PamContext PamResult PamError".split(),
    "Quickshell.Services.Greetd": "Greetd GreetdState".split(),
    "Quickshell.Services.Polkit": "PolkitAgent AuthFlow Identity".split(),
    "Quickshell.Widgets": ("IconImage ClippingRectangle WrapperItem WrapperMouseArea WrapperRectangle "
                           "ClippingWrapperRectangle").split(),
}
TYPE_MODULE: dict[str, str] = {}
for mod, types in QT.items():
    for t in types:
        TYPE_MODULE.setdefault(t, mod)
ALWAYS = {"Qt", "Math", "JSON", "Date", "Number", "String", "Object", "Array", "Promise", "console",
          "Component", "Locale", "Boolean", "RegExp", "Error", "Infinity", "NaN", "Symbol", "Map", "Set",
          "ArrayBuffer", "Uint8Array", "Intl"}
IMPLIED = {"QtQuick": {"QtQml"}}  # importing QtQuick makes QtQml types available

# Types without a default property: child objects inside them fail at runtime.
NO_CHILDREN = set("Process Socket IpcHandler GlobalShortcut PamContext NotificationServer SystemClock Timer "
                  "StdioCollector SplitParser IdleMonitor IdleInhibitor PwObjectTracker PwNodePeakMonitor "
                  "JsonAdapter Connections Binding FrameAnimation HyprlandFocusGrab PolkitAgent".split())
# Allowed nested blocks inside them: grouped/attached properties (lowercase or Attached.x)

TOKEN_RE = re.compile(r"""
    (?P<ws>\s+)
  | (?P<lc>//[^\n]*)
  | (?P<bc>/\*.*?\*/)
  | (?P<id>[A-Za-z_$][\w$]*)
  | (?P<num>\d[\w.]*)
  | (?P<punct>=>|===|!==|==|!=|<=|>=|&&|\|\||\?\?|\?\.|\.\.\.|[{}()\[\];,.:?=+\-*%<>!&|^~@#])
""", re.S | re.X)

REGEX_PREV = set("( , = : [ ! & | ? { } ; + - * % < > ~ ^ => && || ?? return typeof case".split())


def tokenize(text: str, path: str, errors: list[str]) -> list[tuple[str, str, int]]:
    """Tokens (kind, value, line). Strings/regex/templates become single tokens."""
    toks: list[tuple[str, str, int]] = []
    i, n, line = 0, len(text), 1
    last_sig = ""
    while i < n:
        c = text[i]
        if c in "'\"":
            j = i + 1
            while j < n and text[j] != c:
                if text[j] == "\\":
                    j += 1
                elif text[j] == "\n":
                    errors.append(f"{path}:{line}: unterminated string")
                    break
                j += 1
            toks.append(("str", text[i + 1:j], line))
            line += text[i:j + 1].count("\n")
            i = j + 1
            last_sig = "str"
            continue
        if c == "`":
            # template literal with ${ ... } (nested braces tracked)
            j, depth = i + 1, 0
            while j < n:
                ch = text[j]
                if ch == "\\":
                    j += 2
                    continue
                if depth == 0 and ch == "`":
                    break
                if ch == "$" and j + 1 < n and text[j + 1] == "{":
                    depth += 1
                    j += 2
                    continue
                if depth and ch == "{":
                    depth += 1
                elif depth and ch == "}":
                    depth -= 1
                j += 1
            if j >= n:
                errors.append(f"{path}:{line}: unterminated template literal")
            toks.append(("str", text[i + 1:j], line))
            line += text[i:j + 1].count("\n")
            i = j + 1
            last_sig = "str"
            continue
        if c == "/" and i + 1 < n and text[i + 1] not in "/*" and (last_sig in REGEX_PREV or last_sig == ""):
            # regex literal
            j, in_class = i + 1, False
            while j < n:
                ch = text[j]
                if ch == "\\":
                    j += 2
                    continue
                if ch == "[":
                    in_class = True
                elif ch == "]":
                    in_class = False
                elif ch == "/" and not in_class:
                    break
                elif ch == "\n":
                    break
                j += 1
            j += 1
            while j < n and text[j].isalpha():
                j += 1
            toks.append(("regex", text[i:j], line))
            i = j
            last_sig = "regex"
            continue
        m = TOKEN_RE.match(text, i)
        if not m:
            toks.append(("punct", c, line))
            i += 1
            last_sig = c
            continue
        kind = m.lastgroup
        val = m.group(kind)
        if kind in ("ws", "lc", "bc"):
            line += val.count("\n")
        else:
            toks.append((kind, val, line))
            last_sig = val if kind in ("punct", "id") else kind
        i = m.end()
    return toks


def check_balance(toks, path, errors):
    stack = []
    pairs = {")": "(", "]": "[", "}": "{"}
    for kind, val, line in toks:
        if kind != "punct":
            continue
        if val in "([{":
            stack.append((val, line))
        elif val in ")]}":
            if not stack or stack[-1][0] != pairs[val]:
                errors.append(f"{path}:{line}: unbalanced '{val}'"
                              + (f" (open '{stack[-1][0]}' from line {stack[-1][1]})" if stack else ""))
                return
            stack.pop()
    if stack:
        errors.append(f"{path}:{stack[-1][1]}: unclosed '{stack[-1][0]}'")


# ----------------------------------------------------------------------------- modules
def real(p: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(os.path.realpath(p))


def parse_qmldir(path: pathlib.Path):
    module, types = None, {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        parts = raw.split("#")[0].split()
        if not parts:
            continue
        if parts[0] == "module":
            module = parts[1]
        elif parts[0] == "singleton" and len(parts) >= 4:
            types[parts[1]] = ("singleton", parts[3])
        elif parts[0] == "internal" and len(parts) >= 3:
            types[parts[1]] = ("internal", parts[2])
        elif len(parts) >= 3 and parts[0][0].isupper():
            types[parts[0]] = ("type", parts[2])
    return module, types


def dir_types(d: pathlib.Path) -> set[str]:
    return {p.stem for p in d.glob("*.qml") if p.stem[:1].isupper()}


def singleton_members(path: pathlib.Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    members = set(re.findall(r"^\s*(?:readonly\s+|required\s+|default\s+)*property\s+(?:alias\s+|[\w.<>]+\s+)(\w+)",
                             text, re.M))
    members |= set(re.findall(r"^\s*function\s+(\w+)\s*\(", text, re.M))
    members |= set(re.findall(r"^\s*signal\s+(\w+)", text, re.M))
    # signal handlers are reachable as members too (e.g. onFoo) - not needed
    members |= {"objectName"}
    return members


# ----------------------------------------------------------------------------- per file checks
IMPORT_RE = re.compile(r"^\s*import\s+(\"[^\"]+\"|[\w.]+)(?:\s+[\d.]+)?(?:\s+as\s+(\w+))?", re.M)


# JavaScript globals that QML forbids as ids, property/alias names, signal names and method names
# ("Illegal method name", "Illegal signal name", …): Qt 6.10 src/qml/compiler/qv4codegen.cpp
# s_globalNames, checked in qqmlirbuilder.cpp. One such name makes the whole file — and every root
# that imports it — fail to load: `signal escape` in TextField.qml stopped the shell in CI run #2.
JS_GLOBAL_NAMES = frozenset(
    "Array ArrayBuffer Atomics Boolean DOMException DataView Date Error EvalError Function Infinity JSON Map "
    "Math NaN Number Object Promise Proxy QT_TRANSLATE_NOOP QT_TRID_NOOP QT_TR_NOOP Qt RangeError "
    "ReferenceError Reflect RegExp SQLException Set SharedArrayBuffer String Symbol SyntaxError TypeError "
    "URIError URL URLSearchParams WeakMap WeakSet XMLHttpRequest console decodeURI decodeURIComponent "
    "encodeURI encodeURIComponent escape eval gc isFinite isNaN parseFloat parseInt print qsTr qsTrId "
    "qsTranslate undefined unescape".split())
RESERVED_DECL_RE = re.compile(
    r"^[ \t]*(?:(?:readonly|required|default|final|virtual|override)\s+)*"
    r"(?:property\s+[\w.<>]+\s+(?P<prop>\w+)|signal\s+(?P<sig>\w+)|function\s+(?P<fn>\w+)\s*\(|id\s*:\s*(?P<id>\w+))",
    re.M)


def check_reserved_names(text: str, rel: str, errors: list[str]) -> None:
    for m in RESERVED_DECL_RE.finditer(text):
        kind, name = next((k, v) for k, v in m.groupdict().items() if v)
        if name in JS_GLOBAL_NAMES:
            line = text.count("\n", 0, m.start()) + 1
            what = {"prop": "property", "sig": "signal", "fn": "function", "id": "id"}[kind]
            errors.append(f"{rel}:{line}: {what} `{name}` is a JavaScript global — QML refuses to load the file")


def check_file(path: pathlib.Path, rel: str, ctx: dict, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    toks = tokenize(text, rel, errors)
    check_balance(toks, rel, errors)
    if path.suffix == ".js":
        return
    check_reserved_names(text, rel, errors)

    # imports
    modules, qualifiers = set(), set()
    for m in IMPORT_RE.finditer(text):
        target, alias = m.group(1), m.group(2)
        if alias:
            qualifiers.add(alias)
        if target.startswith('"'):
            continue
        modules.add(target)
        if target.startswith("qs."):
            if target not in ctx["local_modules"]:
                errors.append(f"{rel}: import {target}: no such module in this shell root")
    for mod in list(modules):
        modules |= IMPLIED.get(mod, set())

    available: set[str] = set(ALWAYS)
    provider: dict[str, str] = {}
    for mod in sorted(modules):
        exported = set(QT.get(mod, [])) | set(ctx["local_modules"].get(mod, set()))
        for t in exported:
            # A name exported by two unqualified imports resolves by import order
            # (and is an error with QML_CHECK_TYPES): never rely on that.
            if t in provider and provider[t] != mod and not {provider[t], mod} <= {"QtQuick", "QtQml"}:
                used = re.search(r"(?<![\w.])" + t + r"\s*\{", text)
                if used:
                    errors.append(f"{rel}: {t} is exported by both {provider[t]} and {mod}")
            provider.setdefault(t, mod)
        available |= exported
    available |= dir_types(path.parent)
    available |= qualifiers
    inline_components = set(re.findall(r"^\s*component\s+(\w+)\s*:", text, re.M))
    available |= inline_components

    # object types and attached/enum prefixes (import/pragma lines excluded)
    header_lines = {i + 1 for i, ln in enumerate(text.splitlines())
                    if re.match(r"\s*(import|pragma)\b", ln)}
    for idx, (kind, val, line) in enumerate(toks):
        if kind != "id" or not val[:1].isupper() or line in header_lines:
            continue
        prev = toks[idx - 1] if idx > 0 else ("", "", 0)
        nxt = toks[idx + 1] if idx + 1 < len(toks) else ("", "", 0)
        if prev[1] == ".":
            continue  # member of something else (Foo.Bar)
        is_decl = nxt[1] == "{"
        is_member = nxt[1] == "."
        if not (is_decl or is_member):
            continue
        if val in available:
            continue
        if val in TYPE_MODULE:
            errors.append(f"{rel}:{line}: {val} needs `import {TYPE_MODULE[val]}`")
        elif is_decl:
            errors.append(f"{rel}:{line}: unknown type {val}")
        elif val in ctx["all_local_types"]:
            errors.append(f"{rel}:{line}: {val} is not imported (module {ctx['all_local_types'][val]})")

    # singleton members
    for idx, (kind, val, line) in enumerate(toks):
        if kind == "id" and val in ctx["singletons"] and val in available:
            if idx + 2 < len(toks) and toks[idx + 1][1] == "." and toks[idx + 2][0] == "id":
                if idx > 0 and toks[idx - 1][1] == ".":
                    continue
                member = toks[idx + 2][1]
                if member not in ctx["singletons"][val]:
                    errors.append(f"{rel}:{line}: {val}.{member} does not exist")

    # duplicate ids
    seen: dict[str, int] = {}
    for idx, (kind, val, line) in enumerate(toks):
        # a QML id is `id: name` starting a line (JS literals like `{ id: x.y }` are not)
        first_on_line = idx == 0 or toks[idx - 1][2] != line or toks[idx - 1][1] in ("{", ";")
        after = toks[idx + 3][1] if idx + 3 < len(toks) else ""
        if kind == "id" and val == "id" and idx + 2 < len(toks) and toks[idx + 1][1] == ":" \
                and toks[idx + 2][0] == "id" and first_on_line and after not in (".", "(", "[") \
                and (idx == 0 or toks[idx - 1][1] != "."):
            name = toks[idx + 2][1]
            if name in seen:
                errors.append(f"{rel}:{line}: duplicate id '{name}' (first on line {seen[name]})")
            else:
                seen[name] = line

    # children inside types without a default property
    check_children(toks, rel, errors)

    # glyph literals: `glyph: "name"` and ternary branches (`c ? "a" : "b"`)
    for idx, (kind, val, line) in enumerate(toks):
        if kind == "id" and val == "glyph" and idx + 1 < len(toks) and toks[idx + 1][1] == ":":
            j, depth = idx + 2, 0
            while j < len(toks) and toks[j][2] == line:
                k, v = toks[j][0], toks[j][1]
                if v in "([{":
                    depth += 1
                elif v in ")]}":
                    if depth == 0:
                        break
                    depth -= 1
                elif depth == 0 and v in (",", ";"):
                    break
                if k == "str" and depth == 0 and toks[j - 1][1] in (":", "?") and v and v not in ctx["icons"]:
                    errors.append(f"{rel}:{line}: glyph '{v}' is not in core/Icons.qml")
                j += 1


def check_children(toks, rel, errors):
    """Track object blocks; flag `Type {` directly inside a NO_CHILDREN object."""
    stack: list[str | None] = []   # object type for object blocks, None for other braces
    for idx, (kind, val, line) in enumerate(toks):
        if kind != "punct" or val not in "{}":
            continue
        if val == "}":
            if stack:
                stack.pop()
            continue
        prev = toks[idx - 1] if idx > 0 else ("", "", 0)
        before = toks[idx - 2] if idx > 1 else ("", "", 0)
        obj = None
        if prev[0] == "id" and prev[1][:1].isupper() and before[1] != ".":
            obj = prev[1]
            parent = next((s for s in reversed(stack) if s is not None), None)
            # a direct child: the enclosing brace is the parent object itself
            if stack and stack[-1] == parent and parent in NO_CHILDREN:
                assign = before[1] == ":"  # `prop: Type {` is a property value, fine
                if not assign:
                    errors.append(f"{rel}:{line}: {obj} declared as a child of {parent} (no default property)")
        stack.append(obj if obj else ("{" if prev[0] == "id" and prev[1][:1].islower() else None))


# ----------------------------------------------------------------------------- qmldir + links
def check_qmldirs(root: pathlib.Path, errors: list[str]) -> None:
    for qd in sorted(root.rglob("qmldir")):
        if any(part in ("tools", "hypr") for part in qd.relative_to(root).parts):
            continue
        d = qd.parent
        if d.is_symlink() or any(p.is_symlink() for p in qd.relative_to(root).parents if (root / p) != root):
            continue
        module, types = parse_qmldir(qd)
        rel = qd.relative_to(root.parent)
        expected = "qs." + ".".join(d.relative_to(root).parts) if d != root else None
        for base in (root / "greeter", root / "setup"):
            if d.is_relative_to(base):
                expected = "qs." + ".".join(d.relative_to(base).parts)
        if expected and module != expected:
            errors.append(f"{rel}: module is '{module}', expected '{expected}'")
        files = {p.stem: p for p in d.glob("*.qml") if p.stem[:1].isupper()}
        for name, p in files.items():
            if name not in types:
                errors.append(f"{rel}: {p.name} is not listed")
                continue
            is_single = re.search(r"^\s*pragma\s+Singleton\b", p.read_text(encoding="utf-8"), re.M) is not None
            if is_single and types[name][0] != "singleton":
                errors.append(f"{rel}: {name} has `pragma Singleton` but is not declared singleton")
            if not is_single and types[name][0] == "singleton":
                errors.append(f"{rel}: {name} is declared singleton but lacks `pragma Singleton`")
            if types[name][1] != p.name:
                errors.append(f"{rel}: {name} points to {types[name][1]}, expected {p.name}")
        for name, (_kind, fname) in types.items():
            if not (d / fname).exists():
                errors.append(f"{rel}: {name} -> {fname} does not exist")


def check_links(root: pathlib.Path, errors: list[str]) -> None:
    for sub in ("greeter", "setup"):
        for link in ("core", "components", "assets"):
            p = root / sub / link
            if not p.is_symlink():
                errors.append(f"shell/{sub}/{link}: must be a symlink to ../{link}")
            elif real(p) != real(root / link):
                errors.append(f"shell/{sub}/{link}: points to {os.readlink(p)}, expected ../{link}")


def ipc_targets(qml: pathlib.Path) -> dict[str, set[str]]:
    """IpcHandler target -> function names declared in one QML file."""
    text = qml.read_text(encoding="utf-8")
    out: dict[str, set[str]] = {}
    for m in re.finditer(r"IpcHandler\s*\{", text):
        depth, i = 0, m.end() - 1
        for j in range(i, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
        body = text[i:j]
        t = re.search(r'target:\s*"([^"]+)"', body)
        if t:
            out[t.group(1)] = set(re.findall(r"^\s*function\s+(\w+)\s*\(", body, re.M))
    return out


SVG_ARGS = {"m": 2, "l": 2, "h": 1, "v": 1, "c": 6, "s": 4, "q": 4, "t": 2, "a": 7, "z": 0}
SVG_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def check_icon_paths(root: pathlib.Path, errors: list[str]) -> None:
    """Icon path data must survive Qt's greedy SVG number reader (QQuickSvgParser): compact arc
    flags like `0 00-2.4` are read as one number and break the icon."""
    reg = root / "core" / "Icons.qml"
    if not reg.exists():
        return
    for n, line in enumerate(reg.read_text(encoding="utf-8").splitlines(), 1):
        m = re.match(r'\s*"([\w-]+)":\s*\{ s: "([^"]*)", f: "([^"]*)"', line)
        if not m:
            continue
        for d in m.group(2, 3):
            for cmd, body in re.findall(r"([A-Za-z])([^A-Za-z]*)", d):
                nums = SVG_NUM.findall(body)
                want = SVG_ARGS.get(cmd.lower())
                bad = want is None or (want and len(nums) % want) or (not want and nums)
                if cmd in "aA" and not bad:
                    bad = any(nums[i] not in ("0", "1") for i in range(len(nums)) if i % 7 in (3, 4))
                if bad:
                    errors.append(f"shell/core/Icons.qml:{n}: icon '{m.group(1)}': '{cmd}{body.strip()}' "
                                  "does not parse in Qt's PathSvg (run tools/gen_icons.py)")
                    break


def check_ipc_binds(root: pathlib.Path, errors: list[str]) -> None:
    """Every `$svoya_ipc <target> <fn>` in hypr/*.conf and `ipc call <target> <fn>` in QML exists."""
    shell_targets = ipc_targets(root / "shell.qml")
    setup_targets = ipc_targets(root / "setup" / "shell.qml") if (root / "setup" / "shell.qml").exists() else {}
    for conf in sorted((root / "hypr").rglob("*.conf")):
        for n, line in enumerate(conf.read_text(encoding="utf-8").splitlines(), 1):
            for m in re.finditer(r"\$svoya_ipc\s+(\w+)\s+(\w+)", line):
                tgt, fn = m.groups()
                if fn not in shell_targets.get(tgt, set()):
                    errors.append(f"{conf.relative_to(root.parent)}:{n}: ipc {tgt} {fn}: no such IpcHandler function "
                                  "in shell.qml")
    for qml in sorted(root.rglob("*.qml")):
        if "tools" in qml.parts:
            continue
        for n, line in enumerate(qml.read_text(encoding="utf-8").splitlines(), 1):
            for m in re.finditer(r"ipc call (\w+) (\w+)", line):
                tgt, fn = m.groups()
                known = setup_targets if tgt == "setup" else shell_targets
                if fn not in known.get(tgt, set()):
                    errors.append(f"{qml.relative_to(root.parent)}:{n}: ipc call {tgt} {fn}: no such IpcHandler function")


# ----------------------------------------------------------------------------- main
def build_context(config_root: pathlib.Path) -> dict:
    """Modules visible from one Quickshell config root (shell/, greeter/, setup/)."""
    local_modules: dict[str, set[str]] = {}
    all_local_types: dict[str, str] = {}
    for d in sorted([config_root] + [p for p in config_root.rglob("*") if p.is_dir()]):
        if "tools" in d.parts or "hypr" in d.parts or "assets" in d.relative_to(config_root).parts:
            continue
        # only one level of symlinked dirs (greeter/core -> ../core); skip nested config roots
        relparts = d.relative_to(config_root).parts
        if config_root == SHELL and relparts[:1] in (("greeter",), ("setup",)):
            continue
        if not any(d.glob("*.qml")) and not (d / "qmldir").exists():
            continue
        name = "qs." + ".".join(relparts) if relparts else None
        if not name:
            continue
        qd = d / "qmldir"
        types = set(parse_qmldir(qd)[1]) if qd.exists() else dir_types(d)
        local_modules[name] = types
        for t in types:
            all_local_types.setdefault(t, name)
    singletons: dict[str, set[str]] = {}
    core = config_root / "core"
    if (core / "qmldir").exists():
        for name, (kind, fname) in parse_qmldir(core / "qmldir")[1].items():
            if kind == "singleton":
                singletons[name] = singleton_members(core / fname)
    icons = set()
    reg = core / "Icons.qml"
    if reg.exists():
        icons = set(re.findall(r'^\s*"([\w-]+)":\s*\{', reg.read_text(encoding="utf-8"), re.M))
    return {"local_modules": local_modules, "all_local_types": all_local_types,
            "singletons": singletons, "icons": icons}


# ---- optional: JavaScript syntax of functions and bindings (needs `node`) -------------------------------
JS_PREV = set("(,=:[!&|?{};+-*%<>~^")


def _scan_block(src: str, start: int) -> int:
    """src[start] == '{': index after the matching '}' (strings, comments and regex literals aware)."""
    i, depth, n, last = start, 0, len(src), "{"
    while i < n:
        c = src[i]
        if c in "\"'`":
            i += 1
            while i < n and src[i] != c:
                i += 2 if src[i] == "\\" else 1
            i += 1
            last = "a"
            continue
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if src.startswith("/*", i):
            i = src.find("*/", i) + 2
            continue
        if c == "/" and last in JS_PREV:
            i += 1
            in_class = False
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == "[":
                    in_class = True
                elif src[i] == "]":
                    in_class = False
                elif src[i] == "/" and not in_class:
                    break
                i += 1
            i += 1
            while i < n and src[i].isalpha():
                i += 1
            last = "a"
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        if not c.isspace():
            if src.startswith("return", i) and not src[i + 6:i + 7].isalnum():
                last = "("
                i += 6
                continue
            last = "a" if (c.isalnum() or c in "_$") else c
        i += 1
    return n


def js_snippets(src: str) -> list[tuple[int, str]]:
    """JS pieces of one QML file: functions, block bindings/handlers, one-line bindings."""
    out = []
    regions: list[tuple[int, int]] = []   # JS already taken (skip nested "key: {" lines)
    line_of = lambda pos: src.count("\n", 0, pos) + 1
    inside = lambda pos: any(a < pos < b for a, b in regions)

    def block(m, template):
        start = src.rfind("{", 0, m.end())
        end = _scan_block(src, start)
        regions.append((start, end))
        out.append((line_of(m.start()), template.format(src[start:end])))

    for m in re.finditer(r"^[ \t]*function\s+(\w+)\s*\(([^)]*)\)\s*(?::\s*\w+\s*)?\{", src, re.M):
        if not inside(m.start()):
            params = ",".join(x.split(":")[0].strip() for x in m.group(2).split(",") if x.strip())
            block(m, "(function " + m.group(1) + "(" + params + ") {})")
    for m in re.finditer(r"^[ \t]*(?:(?:readonly|required|default)\s+)*(?:property\s+[\w<>.]+\s+)?([a-z][\w.]*)\s*:\s*\(\{[ \t]*$", src, re.M):
        if not inside(m.start()):
            block(m, "({})")        # object literal binding: prop: ({ … })
    for m in re.finditer(r"^[ \t]*(on\w+)\s*:\s*(\(?[\w\s,]*\)?)\s*=>\s*\{[ \t]*$", src, re.M):
        if not inside(m.start()):
            block(m, "(" + m.group(2) + " => {})")
    for m in re.finditer(r"^[ \t]*(?:(?:readonly|required|default)\s+)*(?:property\s+[\w<>.]+\s+)?([a-z][\w.]*)\s*:\s*(?:function\s*\([^)]*\)\s*)?\{[ \t]*$", src, re.M):
        if not inside(m.start()):
            block(m, "(function() {})")
    for m in re.finditer(r"^[ \t]*(?:(?:readonly|required|default)\s+)*(?:property\s+[\w<>.]+\s+)?([a-z][\w.]*)\s*:\s*(?!\{)(.+?)\s*$", src, re.M):
        key, expr = m.group(1), m.group(2)
        if inside(m.start()) or key in ("case", "default", "id") or expr.endswith(("{", "[", "(", ",", "=>")):
            continue
        if re.match(r"[A-Z]\w*(\.\w+)*\s*\{", expr):
            continue  # object declaration (mask: Region {})
        if key.startswith("on") and re.match(r"(if|for|while|switch|return|const|let|var)\b", expr):
            out.append((line_of(m.start()), "(function() { " + expr + "\n})"))
            continue
        out.append((line_of(m.start()), "(" + expr + "\n)"))
    return out


def check_js(files: list[tuple[pathlib.Path, str]], errors: list[str]) -> str:
    import json
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        return "js: skipped (no node)"
    items = []
    for path, rel in files:
        if path.suffix != ".qml":
            continue
        for line, code in js_snippets(path.read_text(encoding="utf-8")):
            items.append({"at": f"{rel}:{line}", "code": code})
    runner = ("const items = JSON.parse(require('fs').readFileSync(0, 'utf8')); let n = 0;"
              "for (const it of items) { try { new Function(it.code); } catch (e) {"
              " n++; console.log(it.at + ': js: ' + e.message); } }")
    res = subprocess.run([node, "-e", runner], input=json.dumps(items), capture_output=True, text=True)
    errors.extend(l for l in res.stdout.splitlines() if l.strip())
    return f"js: {len(items)} snippets"


def main() -> int:
    errors: list[str] = []
    roots = [SHELL] + [SHELL / r for r in ("greeter", "setup") if (SHELL / r / "shell.qml").exists()]
    seen_files: set[pathlib.Path] = set()
    checked: list[tuple[pathlib.Path, str]] = []
    count = 0
    for config_root in roots:
        ctx = build_context(config_root)
        for path in sorted(config_root.rglob("*")):
            if path.suffix not in (".qml", ".js") or not path.is_file():
                continue
            relparts = path.relative_to(config_root).parts
            if relparts[0] in ("tools", "hypr", "assets"):
                continue
            if config_root == SHELL and relparts[0] in ("greeter", "setup"):
                continue
            r = real(path)
            if r in seen_files:
                continue  # symlinked module already checked from the main root
            seen_files.add(r)
            count += 1
            check_file(path, str(path.relative_to(SHELL.parent)), ctx, errors)
            checked.append((path, str(path.relative_to(SHELL.parent))))
    check_qmldirs(SHELL, errors)
    check_links(SHELL, errors)
    check_ipc_binds(SHELL, errors)
    check_icon_paths(SHELL, errors)
    js = check_js(checked, errors)
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import qmlapi_check
    errors.extend(qmlapi_check.check(SHELL, [p for p, _ in checked]))
    for e in errors:
        print(e)
    print(f"qmlcheck: {count} files ({js}), {len(errors)} problem(s)", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
