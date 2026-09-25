#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build shell/tools/qmlapi.json: the QML API (types, properties, signals,
methods, enums, attached types) of Quickshell and Qt Quick, read from their
C++ headers and QML files. qmlcheck.py uses it to verify every property,
handler, attached property and enum the shell touches, without Qt installed.

    git clone https://github.com/quickshell-mirror/quickshell && git -C quickshell checkout v0.3.1
    git clone --depth 1 --branch 6.10.2 --filter=blob:none --sparse https://github.com/qt/qtdeclarative
    git -C qtdeclarative sparse-checkout set src/qml src/qmlmeta src/qmlmodels src/qmlworkerscript \
        src/quick/items src/quick/util src/quick/handlers src/quickshapes src/effects src/quicklayouts
    python3 shell/tools/gen_qmlapi.py QUICKSHELL_DIR QTDECLARATIVE_DIR

Only names are recorded (plus writability, FINAL, notify and C++ types for
grouped properties); argument lists are not.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

OUT = pathlib.Path(__file__).resolve().parent / "qmlapi.json"

# ----------------------------------------------------------------------------- C++ scanning
COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
STRING_RE = re.compile(r'"(?:\\.|[^"\\\n])*"')


def strip_comments(text: str) -> str:
    # keep strings intact (Q_CLASSINFO values), drop comments and preprocessor lines
    text = re.sub(r"\\\n", " ", text)
    text = re.sub(r"^[ \t]*#[^\n]*", "", text, flags=re.M)
    out, i, n = [], 0, len(text)
    while i < n:
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            out.append(" ")
            continue
        if text[i] == '"':
            m = STRING_RE.match(text, i)
            if m:
                out.append(m.group(0))
                i = m.end()
                continue
        if text[i] == "'" and i + 2 < n:
            j = text.find("'", i + 1)
            if 0 < j - i <= 4:
                out.append("' '")
                i = j + 1
                continue
        out.append(text[i])
        i += 1
    return "".join(out)


def match_brace(text: str, start: int) -> int:
    """text[start] == '{' -> index of the matching '}'."""
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
    return len(text) - 1


def macro_args(text: str, name: str) -> list[str]:
    """Arguments (balanced parentheses) of every NAME(...) in text."""
    out = []
    for m in re.finditer(r"\b" + name + r"\s*\(", text):
        i, depth = m.end() - 1, 0
        for j in range(i, len(text)):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    out.append(text[i + 1:j])
                    break
    return out


PROP_KEYS = {"READ", "WRITE", "MEMBER", "NOTIFY", "RESET", "CONSTANT", "FINAL", "BINDABLE", "REVISION",
             "DESIGNABLE", "SCRIPTABLE", "STORED", "USER", "REQUIRED"}


def parse_property(args: str, private: bool) -> dict | None:
    if private:
        # Q_PRIVATE_PROPERTY(d_func(), type name READ ...)
        depth = 0
        for i, c in enumerate(args):
            if c in "(<":
                depth += 1
            elif c in ")>":
                depth -= 1
            elif c == "," and depth == 0:
                args = args[i + 1:]
                break
    words = re.findall(r"[\w:]+|[*&<>,]", args)
    idx = next((i for i, w in enumerate(words) if w in PROP_KEYS), len(words))
    head = words[:idx]
    names = [w for w in head if re.match(r"^[A-Za-z_]\w*$", w)]
    if not names:
        return None
    name = names[-1]
    type_words = head[:len(head) - 1 - head[::-1].index(name)]
    ctype = "".join(w if w in "*&<>," else " " + w for w in type_words).strip()
    rest = words[idx:]
    flags = set(rest)
    notify = None
    if "NOTIFY" in rest:
        k = rest.index("NOTIFY")
        if k + 1 < len(rest):
            notify = rest[k + 1]
    writable = "WRITE" in flags or ("MEMBER" in flags and "CONSTANT" not in flags)
    return {"name": name, "type": ctype.replace(" *", "*").replace(" ", " "), "w": writable,
            "final": "FINAL" in flags, "notify": notify}


ACCESS_RE = re.compile(r"^\s*(public|private|protected)\s*(slots|Q_SLOTS)?\s*:|^\s*(signals|Q_SIGNALS)\s*:", re.M)


def sections(body: str):
    """Yield (label, text) for every access section of a class body."""
    marks = [(m.start(), m.end(), (m.group(3) or ((m.group(1) or "") + (" slots" if m.group(2) else ""))))
             for m in ACCESS_RE.finditer(body)]
    yield ("private", body[:marks[0][0]] if marks else body)
    for k, (s, e, label) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(body)
        yield (label.replace("Q_SIGNALS", "signals"), body[e:end])


def method_names(text: str) -> set[str]:
    names = set()
    for m in re.finditer(r"([A-Za-z_]\w*)\s*\(", text):
        n = m.group(1)
        if n in ("Q_REVISION", "Q_INVOKABLE", "Q_SIGNAL", "Q_SLOT", "if", "return", "sizeof", "decltype",
                 "Q_DECL_DEPRECATED_X", "QT_DEPRECATED_X", "nodiscard", "static_cast", "noexcept"):
            continue
        # skip calls inside inline bodies: a declaration name follows a type or ~
        names.add(n)
    return names


def decl_names(text: str) -> set[str]:
    """Function names declared in a section (inline bodies removed)."""
    flat, i, n = [], 0, len(text)
    while i < n:
        if text[i] == "{":
            j = match_brace(text, i)
            flat.append(";")
            i = j + 1
            continue
        flat.append(text[i])
        i += 1
    flat_s = "".join(flat)
    names = set()
    for stmt in flat_s.split(";"):
        stmt = re.sub(r"\[\[[^\]]*\]\]", " ", stmt)
        m = re.search(r"(~?[A-Za-z_]\w*)\s*\(", stmt)
        if not m or m.group(1).startswith("~"):
            continue
        name = m.group(1)
        if name in ("Q_REVISION", "Q_INVOKABLE", "Q_SIGNAL", "QSDOC_HIDE", "Q_DECL_DEPRECATED_X", "operator",
                    "Q_OBJECT", "Q_GADGET", "QML_ELEMENT", "Q_PROPERTY"):
            rest = stmt[m.end():]
            m2 = re.search(r"([A-Za-z_]\w*)\s*\(", rest)
            while m2 and m2.group(1) in ("Q_INVOKABLE", "Q_REVISION", "QSDOC_HIDE"):
                rest = rest[m2.end():]
                m2 = re.search(r"([A-Za-z_]\w*)\s*\(", rest)
            if not m2:
                continue
            name = m2.group(1)
        names.add(name)
    return names


def enums_in(body: str, wanted: set[str]) -> dict[str, list[str]]:
    out = {}
    for m in re.finditer(r"\benum\s+(?:class\s+|struct\s+)?(\w+)\s*(?::\s*[\w:]+\s*)?\{", body):
        name = m.group(1)
        end = match_brace(body, m.end() - 1)
        vals = []
        for part in body[m.end():end].split(","):
            mm = re.match(r"\s*([A-Za-z_]\w*)", part)
            if mm:
                vals.append(mm.group(1))
        if name in wanted:
            out[name] = vals
    return out


def base_of(bases: str | None) -> str | None:
    if not bases:
        return None
    first = bases.split(",")[0]
    first = re.sub(r"\b(public|protected|private|virtual)\b", " ", first).strip()
    first = re.sub(r"<.*", "", first).strip()
    return first.split("::")[-1] or None


CLASS_RE = re.compile(r"\b(class|struct)\s+((?:Q_\w+_EXPORT\s+|Q_DECL_\w+\s+|QS_\w+\s+)*)(\w+)\s*(?:final\s*)?"
                      r"(?::\s*([^{;()]+?))?\s*\{", re.S)
NS_RE = re.compile(r"\bnamespace\s+([\w:]+)\s*\{")


def scan_header(path: pathlib.Path, module: str, out: dict, qml_names: dict) -> None:
    text = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
    spans = []
    for m in CLASS_RE.finditer(text):
        name = m.group(3)
        if name in ("Q_DECL_EXPORT",):
            continue
        start = m.end() - 1
        end = match_brace(text, start)
        spans.append((start, end, name, m.group(4), m.group(1)))
    ns_spans = []
    for m in NS_RE.finditer(text):
        start = m.end() - 1
        end = match_brace(text, start)
        ns_spans.append((start, end, m.group(1).split("::")[-1]))

    def own_text(start, end):
        """Body without nested class/struct bodies."""
        parts, cur = [], start + 1
        for s, e, *_ in sorted(spans):
            if s > start and e < end and s >= cur:
                parts.append(text[cur:s])
                cur = e + 1
        parts.append(text[cur:end])
        return "".join(parts)

    for start, end, name, bases, kind in spans:
        body = own_text(start, end)
        if not re.search(r"\bQ_OBJECT\b|\bQ_GADGET\b|\bQML_\w+", body):
            continue
        record_class(name, base_of(bases), body, module, out, qml_names, str(path))

    for start, end, name in ns_spans:
        # a namespace body minus nested namespaces/classes
        parts, cur = [], start + 1
        for s, e, *_ in sorted(spans + [(a, b, c, None, None) for a, b, c in ns_spans]):
            if s > start and e < end and s >= cur:
                parts.append(text[cur:s])
                cur = e + 1
        parts.append(text[cur:end])
        body = "".join(parts)
        if not re.search(r"\bQ_NAMESPACE(_EXPORT)?\b", body):
            continue
        record_class(name, None, body, module, out, qml_names, str(path), namespace=True)


def record_class(name, base, body, module, out, qml_names, src, namespace=False):
    cls = {"base": base, "module": module, "props": {}, "signals": [], "methods": [], "enums": {},
           "default": None, "attached": None, "extended": None, "foreign": None, "qml": [], "src": src}
    for args in macro_args(body, "Q_PROPERTY"):
        p = parse_property(args, False)
        if p:
            cls["props"][p["name"]] = p
    for args in macro_args(body, "Q_PRIVATE_PROPERTY"):
        p = parse_property(args, True)
        if p:
            cls["props"][p["name"]] = p
    for args in macro_args(body, "Q_CLASSINFO"):
        m = re.match(r'\s*"DefaultProperty"\s*,\s*"(\w+)"', args)
        if m:
            cls["default"] = m.group(1)
    for args in macro_args(body, "QML_ATTACHED"):
        cls["attached"] = args.strip().split("::")[-1]
    for macro in ("QML_EXTENDED", "QML_EXTENDED_NAMESPACE"):
        for args in macro_args(body, macro):
            cls["extended"] = args.strip().split("::")[-1]
    for args in macro_args(body, "QML_FOREIGN"):
        cls["foreign"] = args.strip().split("::")[-1]
    for args in macro_args(body, "QML_FOREIGN_NAMESPACE"):
        cls["foreign"] = args.strip().split("::")[-1]
    for args in macro_args(body, "QML_NAMED_ELEMENT"):
        cls["qml"].append(args.strip())
    if re.search(r"\bQML_ELEMENT\b", body):
        cls["qml"].append(name)
    for args in macro_args(body, "QML_VALUE_TYPE"):
        cls.setdefault("valuetype", []).append(args.strip())
    cls["singleton"] = bool(re.search(r"\bQML_SINGLETON\b", body))
    cls["uncreatable"] = bool(re.search(r"\bQML_UNCREATABLE\b", body))
    cls["anonymous"] = bool(re.search(r"\bQML_ANONYMOUS\b", body))
    # enums
    wanted = set()
    for macro in ("Q_ENUM", "Q_ENUMS", "Q_ENUM_NS", "Q_FLAG", "Q_FLAGS", "Q_FLAG_NS"):
        for args in macro_args(body, macro):
            wanted |= {a.strip() for a in args.split(",") if a.strip()}
    flags_map = {}
    for args in macro_args(body, "Q_DECLARE_FLAGS"):
        a = [x.strip() for x in args.split(",")]
        if len(a) == 2:
            flags_map[a[0]] = a[1]
    wanted |= {flags_map[w] for w in list(wanted) if w in flags_map}
    cls["enums"] = enums_in(body, wanted)
    # methods / signals / slots
    signals, methods = set(), set()
    for label, sec in sections(body):
        if label == "signals":
            signals |= decl_names(sec)
        elif label == "public slots":
            methods |= decl_names(sec)
        for m in re.finditer(r"\bQ_INVOKABLE\b", sec):
            stmt = sec[m.end():]
            stmt = re.sub(r"\[\[[^\]]*\]\]", " ", stmt)
            mm = re.search(r"([A-Za-z_]\w*)\s*\(", stmt)
            if mm:
                methods.add(mm.group(1))
        for m in re.finditer(r"\bQ_SIGNAL\b", sec):
            mm = re.search(r"([A-Za-z_]\w*)\s*\(", sec[m.end():])
            if mm:
                signals.add(mm.group(1))
        for m in re.finditer(r"\bQ_SLOT\b", sec):
            mm = re.search(r"([A-Za-z_]\w*)\s*\(", sec[m.end():])
            if mm:
                methods.add(mm.group(1))
    signals.discard(name)
    methods.discard(name)
    cls["signals"] = sorted(signals)
    cls["methods"] = sorted(methods - signals)
    cls["namespace"] = namespace
    key = name
    if key in out and out[key]["module"] != module:
        key = module + "::" + name
    if key in out:
        # same class declared twice (e.g. #if branches): merge
        prev = out[key]
        prev["props"].update(cls["props"])
        prev["signals"] = sorted(set(prev["signals"]) | set(cls["signals"]))
        prev["methods"] = sorted(set(prev["methods"]) | set(cls["methods"]))
        prev["enums"].update(cls["enums"])
        prev["qml"] = sorted(set(prev["qml"]) | set(cls["qml"]))
        for k in ("default", "attached", "extended", "foreign", "base"):
            prev[k] = prev[k] or cls[k]
        return
    out[key] = cls


# ----------------------------------------------------------------------------- module maps
def quickshell_modules(qs: pathlib.Path) -> dict[pathlib.Path, str]:
    mods = {}
    for cm in qs.glob("src/**/CMakeLists.txt"):
        t = cm.read_text(encoding="utf-8")
        m = re.search(r"qt_add_qml_module\s*\(\s*[\w-]+\s+URI\s+([\w.]+)", t)
        if m:
            mods[cm.parent] = m.group(1)
    return mods


def module_for(path: pathlib.Path, mods: dict[pathlib.Path, str]) -> str | None:
    for p in [path.parent] + list(path.parents):
        if p in mods:
            return mods[p]
    return None


QT_DIRS = {
    "src/qml": "QtQml",
    "src/qmlmeta": "QtQml",
    "src/qmlmodels": "QtQml.Models",
    "src/qmlworkerscript": "QtQml.WorkerScript",
    "src/quick": "QtQuick",
    "src/quickshapes": "QtQuick.Shapes",
    "src/effects": "QtQuick.Effects",
    "src/quicklayouts": "QtQuick.Layouts",
}

# qtbase classes the QML types derive from (not in qtdeclarative)
QTBASE = {
    "QObject": {"props": {"objectName": {"name": "objectName", "type": "QString", "w": True, "final": False,
                                         "notify": "objectNameChanged"}},
                "signals": ["destroyed", "objectNameChanged"], "methods": ["deleteLater"]},
    "QAbstractItemModel": {"signals": ["dataChanged", "rowsInserted", "rowsRemoved", "modelReset", "layoutChanged",
                                       "rowsMoved", "columnsInserted", "columnsRemoved", "headerDataChanged",
                                       "rowsAboutToBeInserted", "rowsAboutToBeRemoved", "modelAboutToBeReset"],
                           "methods": ["index", "parent", "rowCount", "columnCount", "data", "setData", "hasChildren",
                                       "roleNames"], "base": "QObject"},
    "QAbstractListModel": {"base": "QAbstractItemModel"},
    "QAbstractTableModel": {"base": "QAbstractItemModel"},
    "QValidator": {"props": {"locale": {"name": "locale", "type": "QLocale", "w": True, "final": False,
                                        "notify": None}}, "signals": ["changed"], "base": "QObject"},
    "QQmlParserStatus": {},
    "QQmlPropertyValueSource": {},
    "QQmlPropertyValueInterceptor": {},
    "QQmlFinalizerHook": {},
    "QWindow": {"base": "QObject", "open": True},
    "QEvent": {},
    "QSGTextureProvider": {"base": "QObject"},
    "QQuickPaintedItem": {"base": "QQuickItem"},
}

VALUE_TYPE_FOREIGN = {}  # C++ type -> value type class (filled from QML_FOREIGN on QML_VALUE_TYPE)


def qml_file_type(path: pathlib.Path, module: str) -> dict:
    """A QML-defined type (Quickshell's FileView.qml, widgets): root type + declarations."""
    text = path.read_text(encoding="utf-8")
    body = re.sub(r"//[^\n]*", "", text)
    root = re.search(r"^\s*([A-Z][\w.]*)\s*\{", body, re.M)
    props = {}
    for m in re.finditer(r"^\s*(readonly\s+)?property\s+(?:/\*\w+\*/)?([\w<>.]+)\s+(\w+)", body, re.M):
        props[m.group(3)] = {"name": m.group(3), "type": m.group(2), "w": not m.group(1), "final": False,
                             "notify": m.group(3) + "Changed"}
    methods = re.findall(r"^\s*function\s+(\w+)", body, re.M)
    signals = re.findall(r"^\s*signal\s+(\w+)", body, re.M)
    return {"base": root.group(1) if root else "QtObject", "base_is_qml": True, "module": module, "props": props,
            "signals": sorted(signals), "methods": sorted(methods), "enums": {}, "default": None,
            "attached": None, "extended": None, "foreign": None, "qml": [path.stem], "singleton": False,
            "uncreatable": False, "anonymous": False, "namespace": False, "src": str(path)}


def build(qs_dir: pathlib.Path, qt_dir: pathlib.Path) -> dict:
    classes: dict[str, dict] = {}
    qml_names: dict = {}
    mods = quickshell_modules(qs_dir)
    for h in sorted(qs_dir.glob("src/**/*.hpp")):
        if "/test/" in str(h) or "/build/" in str(h):
            continue
        mod = module_for(h, mods)
        if mod is None:
            continue
        scan_header(h, mod, classes, qml_names)
    qs_qml = {}
    for f in sorted(qs_dir.glob("src/**/*.qml")):
        if "/test/" in str(f):
            continue
        mod = module_for(f, mods)
        if mod and not mod.startswith("Quickshell._Internal"):
            qs_qml[f.stem] = qml_file_type(f, mod)

    for sub, mod in QT_DIRS.items():
        for h in sorted((qt_dir / sub).glob("**/*.h")):
            if any(part in ("doc", "tests", "designer") for part in h.parts):
                continue
            scan_header(h, mod, classes, qml_names)

    for name, spec in QTBASE.items():
        classes.setdefault(name, {"base": spec.get("base"), "module": "QtCore", "props": spec.get("props", {}),
                                  "signals": spec.get("signals", []), "methods": spec.get("methods", []),
                                  "enums": {}, "default": None, "attached": None, "extended": None,
                                  "foreign": None, "qml": [], "singleton": False, "uncreatable": True,
                                  "anonymous": True, "namespace": False, "open": spec.get("open", False),
                                  "src": "qtbase"})

    # QML type names per module: name -> class key
    modules: dict[str, dict[str, str]] = {}
    for key, c in classes.items():
        for qn in c["qml"]:
            modules.setdefault(c["module"], {})[qn] = key
    for name, t in qs_qml.items():
        key = "qml:" + t["module"] + "." + name
        classes[key] = t
        modules.setdefault(t["module"], {})[name] = key

    # PanelWindow comes from the Wayland backend, registered into Quickshell (src/wayland/init.cpp)
    if "WaylandPanelInterface" in classes:
        modules.setdefault("Quickshell", {})["PanelWindow"] = "WaylandPanelInterface"

    # value type wrappers derive from the C++ value class (QQuickFontValueType : QFont): their
    # QML members are all declared on the wrapper
    for key, c in classes.items():
        if c.get("valuetype") and c.get("base") and c["base"] not in classes:
            c["base"] = None

    # value types: C++ foreign type -> value type class
    value_types = {}
    for key, c in classes.items():
        if c.get("valuetype") and c.get("foreign"):
            value_types[c["foreign"]] = c.get("extended") or key
    # Quickshell's structured values (Anchors, Margins, surfaceFormat) are their own classes
    for key, c in classes.items():
        if c.get("valuetype") and not c.get("foreign"):
            value_types[key.split("::")[-1]] = key

    # module imports: importing M also brings these
    imports = {
        "Quickshell": ["Quickshell._Window", "Quickshell._WaylandOverlay"],
        "Quickshell.Wayland": sorted(m for m in modules if m.startswith("Quickshell.Wayland._")),
        "Quickshell.Hyprland": sorted(m for m in modules if m.startswith("Quickshell.Hyprland._")),
        "QtQuick": ["QtQml", "QtQml.Models", "QtQml.WorkerScript"],
        "QtQml": ["QtQml.Models", "QtQml.WorkerScript"],
    }

    # compact: drop empty fields
    compact = {}
    for key, c in classes.items():
        d = {"m": c["module"]}
        if c.get("base"):
            d["b"] = c["base"]
        if c.get("base_is_qml"):
            d["bq"] = 1
        if c["props"]:
            d["p"] = {n: [p["type"], int(p["w"]), int(p["final"]), p["notify"] or ""] for n, p in
                      sorted(c["props"].items())}
        if c["signals"]:
            d["s"] = c["signals"]
        if c["methods"]:
            d["f"] = c["methods"]
        if c["enums"]:
            d["e"] = sorted({v for vals in c["enums"].values() for v in vals})
        for k, short in (("default", "d"), ("attached", "a"), ("extended", "x"), ("foreign", "fo")):
            if c.get(k):
                d[short] = c[k]
        if c.get("singleton"):
            d["single"] = 1
        if c.get("open"):
            d["open"] = 1
        compact[key] = d
    return {"classes": compact, "modules": modules, "imports": imports, "valuetypes": value_types,
            "sources": {"quickshell": "v0.3.1", "qtdeclarative": "6.10.2"}}


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    data = build(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
    lines = ["{"]
    lines.append(' "sources": ' + json.dumps(data["sources"]) + ",")
    lines.append(' "imports": ' + json.dumps(data["imports"], sort_keys=True) + ",")
    lines.append(' "valuetypes": ' + json.dumps(data["valuetypes"], sort_keys=True) + ",")
    lines.append(' "modules": {')
    mods = sorted(data["modules"].items())
    for i, (m, types) in enumerate(mods):
        lines.append("  " + json.dumps(m) + ": " + json.dumps(types, sort_keys=True, ensure_ascii=False)
                     + ("," if i < len(mods) - 1 else ""))
    lines.append(" },")
    lines.append(' "classes": {')
    items = sorted(data["classes"].items())
    for i, (k, c) in enumerate(items):
        lines.append("  " + json.dumps(k) + ": " + json.dumps(c, sort_keys=True, ensure_ascii=False)
                     + ("," if i < len(items) - 1 else ""))
    lines.append(" }")
    lines.append("}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{OUT}: {len(data['classes'])} classes, {sum(len(t) for t in data['modules'].values())} QML types")
    return 0


if __name__ == "__main__":
    sys.exit(main())
