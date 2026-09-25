# SPDX-License-Identifier: Apache-2.0
"""API check for qmlcheck.py: every property, handler, attached property,
grouped property, enum value and `id.member` the shell uses must exist in the
Quickshell / Qt version we ship (tools/qmlapi.json, from gen_qmlapi.py) or in
the shell's own QML components.

What is an error at runtime and flagged here:
  - `foo: …` / `foo.bar: …` / `foo { … }` on a type without property foo (bar)
  - `onFoo: …` without a signal foo (or property for onFooChanged)
  - `Attached.x: …` where Attached has no attached object or no member x
  - `prop: …` assigning a read-only property
  - `property T name` redeclaring a FINAL property of the base type
  - child objects inside a type without a default property
  - `Type.Value` enum values and `Singleton.member` that do not exist
  - `id.member` where the object of `id` has no such property/method/signal
  - `function onX()` in Connections whose target has no signal x
"""
from __future__ import annotations

import json
import pathlib
import re

API_FILE = pathlib.Path(__file__).resolve().parent / "qmlapi.json"

# ----------------------------------------------------------------------------- tokens with columns
PUNCT = ["===", "!==", "...", ">>>", "=>", "==", "!=", "<=", ">=", "&&", "||", "??", "?.", "++", "--", "+=", "-=",
         "*=", "/=", "%=", "**", "<<", ">>"]
REGEX_PREV = set("( , = : [ ! & | ? { } ; + - * % < > ~ ^ => && || ?? return typeof case".split())


class Tok:
    __slots__ = ("k", "v", "line", "col", "nl")

    def __init__(self, k, v, line, col, nl):
        self.k, self.v, self.line, self.col, self.nl = k, v, line, col, nl

    def __repr__(self):
        return f"{self.v}@{self.line}:{self.col}"


def tokenize(text: str) -> list[Tok]:
    toks: list[Tok] = []
    i, n, line, col0 = 0, len(text), 1, 0  # col0 = index of line start
    last = ""
    first_on_line = True
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            col0 = i + 1
            first_on_line = True
            i += 1
            continue
        if c in " \t\r":
            i += 1
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            line += text.count("\n", i, j)
            if "\n" in text[i:j]:
                col0 = text.rfind("\n", i, j) + 1
            i = j
            continue
        start, sline, scol = i, line, i - col0
        if c in "'\"":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            toks.append(Tok("str", text[i + 1:j], sline, scol, first_on_line))
            i = j + 1
            last = "str"
            first_on_line = False
            continue
        if c == "`":
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
            toks.append(Tok("str", text[i + 1:j], sline, scol, first_on_line))
            line += text.count("\n", i, j)
            if "\n" in text[i:j]:
                col0 = text.rfind("\n", i, j) + 1
            i = j + 1
            last = "str"
            first_on_line = False
            continue
        if c == "/" and (last in REGEX_PREV or last == ""):
            j, in_class = i + 1, False
            while j < n and text[j] != "\n":
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
                j += 1
            j += 1
            while j < n and text[j].isalpha():
                j += 1
            toks.append(Tok("regex", text[i:j], sline, scol, first_on_line))
            i = j
            last = "regex"
            first_on_line = False
            continue
        m = re.match(r"[A-Za-z_$][\w$]*", text[i:i + 200])
        if m:
            v = m.group(0)
            toks.append(Tok("id", v, sline, scol, first_on_line))
            i += len(v)
            last = v
            first_on_line = False
            continue
        m = re.match(r"\d[\w.]*|\.\d[\w]*", text[i:i + 60])
        if m:
            toks.append(Tok("num", m.group(0), sline, scol, first_on_line))
            i += len(m.group(0))
            last = "num"
            first_on_line = False
            continue
        for p in PUNCT:
            if text.startswith(p, i):
                toks.append(Tok("p", p, sline, scol, first_on_line))
                i += len(p)
                last = p
                break
        else:
            toks.append(Tok("p", c, sline, scol, first_on_line))
            i += 1
            last = c
        first_on_line = False
    return toks


# ----------------------------------------------------------------------------- QML object tree
class Obj:
    def __init__(self, type_name, line):
        self.type = type_name
        self.line = line
        self.id = None
        self.props = {}        # declared: name -> dict(type, readonly, alias, default, required, line)
        self.signals = {}      # declared signals
        self.functions = {}    # declared functions: name -> line
        self.bindings = []     # (dotted name, line, value_tokens or None, is_object)
        self.handlers = []     # (dotted name, line)
        self.children = []     # child Obj (default property)
        self.values = []       # (property dotted name, Obj) object-valued bindings
        self.on = []           # (property, Obj) for `Behavior on x`
        self.groups = []       # (name, line, sub-members) for `name { a: 1 }`
        self.components = {}   # inline components: name -> Obj
        self.exprs = []        # token lists of every expression (for id.member / Type.x checks)
        self.parent = None
        self.enums = set()


class ParseError(Exception):
    pass


class Parser:
    def __init__(self, toks: list[Tok], path: str):
        self.t = toks
        self.i = 0
        self.path = path

    def peek(self, k=0):
        j = self.i + k
        return self.t[j] if j < len(self.t) else Tok("eof", "", 10 ** 9, 0, True)

    def next(self):
        tok = self.peek()
        self.i += 1
        return tok

    def expect(self, v):
        tok = self.next()
        if tok.v != v:
            raise ParseError(f"{self.path}:{tok.line}: expected '{v}', got '{tok.v}'")
        return tok

    def document(self):
        # skip imports / pragmas
        while self.peek().k != "eof":
            tok = self.peek()
            if tok.v in ("import", "pragma") and tok.nl:
                line = tok.line
                while self.peek().k != "eof" and self.peek().line == line:
                    self.next()
                continue
            break
        name, line = self.qualified()
        return self.object(name, line)

    def qualified(self):
        tok = self.next()
        if tok.k != "id":
            raise ParseError(f"{self.path}:{tok.line}: expected a type name, got '{tok.v}'")
        parts = [tok.v]
        while self.peek().v == "." and self.peek(1).k == "id":
            self.next()
            parts.append(self.next().v)
        return ".".join(parts), tok.line

    def object(self, type_name, line):
        obj = Obj(type_name, line)
        self.expect("{")
        self.members(obj)
        self.expect("}")
        return obj

    def skip_expression(self, member_col):
        """Skip one binding value / statement; returns its tokens."""
        start = self.i
        depth = 0
        first = True
        while True:
            tok = self.peek()
            if tok.k == "eof":
                break
            if depth == 0 and not first:
                if tok.v == ";":
                    self.next()
                    break
                if tok.v == "}":
                    break
                if tok.nl and tok.col <= member_col:
                    break
            if tok.v in "([{" and tok.k == "p":
                depth += 1
            elif tok.v in ")]}" and tok.k == "p":
                depth -= 1
            self.next()
            first = False
        return self.t[start:self.i]

    def members(self, obj: Obj):
        while True:
            tok = self.peek()
            if tok.k == "eof":
                raise ParseError(f"{self.path}: unexpected end of file")
            if tok.v == "}":
                return
            if tok.v == ";":
                self.next()
                continue
            self.member(obj)

    def member(self, obj: Obj):
        tok = self.peek()
        col = tok.col
        v = tok.v
        # id
        if v == "id" and self.peek(1).v == ":":
            self.next()
            self.next()
            obj.id = self.next().v
            return
        # property declarations
        mods = []
        j = 0
        while self.peek(j).v in ("readonly", "required", "default", "final") and self.peek(j + 1).k == "id":
            mods.append(self.peek(j).v)
            j += 1
        if self.peek(j).v == "property" and self.peek(j + 1).k == "id" and self.peek(j + 1).v not in (":",):
            for _ in range(j + 1):
                self.next()
            # type (may be list<T> or qualified)
            ptype = self.next().v
            if self.peek().v == "<":
                self.next()
                inner = []
                while self.peek().v != ">":
                    inner.append(self.next().v)
                self.next()
                ptype += "<" + "".join(inner) + ">"
            while self.peek().v == "." and self.peek(1).k == "id":
                self.next()
                ptype += "." + self.next().v
            name_tok = self.next()
            decl = {"type": ptype, "readonly": "readonly" in mods, "alias": ptype == "alias",
                    "default": "default" in mods, "required": "required" in mods, "line": name_tok.line}
            if name_tok.v in obj.props:
                obj.dup = getattr(obj, "dup", []) + [(name_tok.v, name_tok.line)]
            obj.props[name_tok.v] = decl
            if self.peek().v == ":":
                self.next()
                self.value(obj, name_tok.v, col, declared=True)
            return
        if v == "required" and self.peek(1).k == "id" and self.peek(2).v != ":":
            # `required text`: an inherited property made required (counts for delegates too)
            self.next()
            obj.req_posthoc = getattr(obj, "req_posthoc", set()) | {self.next().v}
            return
        if v == "signal" and self.peek(1).k == "id":
            self.next()
            name = self.next().v
            obj.signals[name] = tok.line
            if self.peek().v == "(":
                depth = 0
                while True:
                    t = self.next()
                    if t.v == "(":
                        depth += 1
                    elif t.v == ")":
                        depth -= 1
                        if depth == 0:
                            break
            return
        if v == "function" and self.peek(1).k == "id":
            self.next()
            name = self.next().v
            obj.functions[name] = tok.line
            body = self.skip_function()
            obj.signatures = getattr(obj, "signatures", {})
            obj.signatures[name] = body
            obj.exprs.append([Tok("id", "function", tok.line, tok.col, False)] + body)
            return
        if v == "async" and self.peek(1).v == "function":
            self.next()
            return self.member(obj)
        if v == "component" and self.peek(1).k == "id" and self.peek(2).v == ":":
            self.next()
            name = self.next().v
            self.next()
            tname, line = self.qualified()
            comp = self.object(tname, line)
            comp.parent = obj
            comp.inline_name = name
            comp.component_root = True
            obj.components[name] = comp
            return
        if v == "enum" and self.peek(1).k == "id" and self.peek(2).v == "{":
            self.next()
            self.next()
            self.next()
            while self.peek().v != "}":
                t = self.next()
                if t.k == "id":
                    obj.enums.add(t.v)
            self.next()
            return
        if tok.k != "id":
            raise ParseError(f"{self.path}:{tok.line}: unexpected '{v}' in object {obj.type}")
        # dotted name
        parts = [self.next().v]
        while self.peek().v == "." and self.peek(1).k == "id":
            self.next()
            parts.append(self.next().v)
        name = ".".join(parts)
        nxt = self.peek()
        if nxt.v == "on" and self.peek(1).k == "id":
            # Behavior on x { … }
            self.next()
            target = [self.next().v]
            while self.peek().v == "." and self.peek(1).k == "id":
                self.next()
                target.append(self.next().v)
            child = self.object(name, tok.line)
            child.parent = obj
            obj.on.append((".".join(target), child, tok.line))
            return
        if nxt.v == "{":
            if parts[-1][:1].isupper():
                child = self.object(name, tok.line)
                child.parent = obj
                obj.children.append(child)
            else:
                # grouped property block: font { family: … }
                sub = Obj("<group>", tok.line)
                self.expect("{")
                self.members(sub)
                self.expect("}")
                obj.groups.append((name, tok.line, sub))
            return
        if nxt.v == ":":
            self.next()
            self.value(obj, name, col)
            return
        raise ParseError(f"{self.path}:{tok.line}: cannot parse member '{name}' ('{nxt.v}' follows)")

    def skip_function(self):
        start = self.i
        # params
        depth = 0
        while True:
            t = self.next()
            if t.v == "(":
                depth += 1
            elif t.v == ")":
                depth -= 1
                if depth == 0:
                    break
            if t.k == "eof":
                raise ParseError(f"{self.path}: unterminated function")
        # optional return type
        if self.peek().v == ":":
            self.next()
            self.next()
            while self.peek().v in (".", "<", ">") or (self.peek().k == "id" and self.peek(-1).v in (".", "<")):
                self.next()
        if self.peek().v != "{":
            raise ParseError(f"{self.path}:{self.peek().line}: expected function body")
        depth = 0
        while True:
            t = self.next()
            if t.v == "{" and t.k == "p":
                depth += 1
            elif t.v == "}" and t.k == "p":
                depth -= 1
                if depth == 0:
                    break
            if t.k == "eof":
                raise ParseError(f"{self.path}: unterminated function body")
        return self.t[start:self.i]

    def value(self, obj: Obj, name: str, col: int, declared=False):
        tok = self.peek()
        # object value: Type { … }
        if tok.k == "id" and tok.v[:1].isupper():
            j = 1
            while self.peek(j).v == "." and self.peek(j + 1).k == "id":
                j += 2
            if self.peek(j).v == "{":
                tname, line = self.qualified()
                child = self.object(tname, line)
                child.parent = obj
                obj.values.append((name, child, tok.line, declared))
                if not declared:
                    obj.bindings.append((name, tok.line, None, True))
                return
        # list of objects: [ Type { … }, … ]
        if tok.v == "[" and self.peek(1).k == "id" and self.peek(1).v[:1].isupper():
            j = 2
            while self.peek(j).v == "." and self.peek(j + 1).k == "id":
                j += 2
            if self.peek(j).v == "{":
                self.next()
                while True:
                    tname, line = self.qualified()
                    child = self.object(tname, line)
                    child.parent = obj
                    obj.values.append((name, child, line, declared))
                    if self.peek().v == ",":
                        self.next()
                        continue
                    self.expect("]")
                    break
                if not declared:
                    obj.bindings.append((name, tok.line, None, True))
                return
        toks = self.skip_expression(col)
        obj.exprs.append(toks)
        if declared:
            obj.decl_values = getattr(obj, "decl_values", []) + [(name, tok.line, toks)]
            return
        last = name.split(".")[-1]
        if re.match(r"^on[A-Z]", last):
            obj.handlers.append((name, tok.line))
        else:
            obj.bindings.append((name, tok.line, toks, False))


def parse_file(path: pathlib.Path) -> Obj:
    text = path.read_text(encoding="utf-8")
    p = Parser(tokenize(text), str(path))
    root = p.document()
    return root


# ----------------------------------------------------------------------------- API model
class Api:
    def __init__(self, data):
        self.classes = data["classes"]
        self.modules = data["modules"]
        self.imports = data["imports"]
        self.valuetypes = data["valuetypes"]

    def module_types(self, module):
        out = {}
        mods = [module] + self.imports.get(module, [])
        for m in reversed(mods):
            out.update({n: ("cpp", k) for n, k in self.modules.get(m, {}).items()})
        return out

    def chain(self, key, seen=None):
        """Class keys contributing members (class, bases, extensions, foreign)."""
        out = []
        seen = seen if seen is not None else set()
        while key and key not in seen:
            seen.add(key)
            c = self.classes.get(key)
            if c is None:
                out.append(None)  # unknown base: open
                break
            if c.get("fo") and c["fo"] in self.classes:
                out += self.chain(c["fo"], seen)
            out.append(key)
            if c.get("x"):
                if c["x"] in self.classes:
                    out += self.chain(c["x"], seen)
                else:
                    out.append(("enums-open", c["x"]))  # QML_EXTENDED_NAMESPACE(QGradient): extra enums
            if c.get("bq"):
                out.append(("qml", c["b"]))
                break
            key = c.get("b")
        return out


class Members:
    """Everything a QML object of some type exposes."""

    def __init__(self):
        self.props = {}      # name -> dict(type, w, final, notify, src)
        self.signals = set()
        self.methods = set()
        self.enums = set()
        self.default = False
        self.attached = None  # class key
        self.open = False     # unknown parts (unknown base class): do not report missing members
        self.singleton = False
        self.enums_open = False
        self.names = []

    def has_member(self, name):
        return name in self.props or name in self.signals or name in self.methods

    def handler_ok(self, handler):
        sig = handler[2].lower() + handler[3:]
        if sig in self.signals:
            return True
        if sig.endswith("Changed"):
            prop = sig[:-7]
            p = self.props.get(prop)
            if p is not None and p.get("notify", True):
                return True
        return False


COMMON_METHODS = {"destroy", "toString", "deleteLater", "hasOwnProperty"}
ITEM_METHODS = set()


class Checker:
    def __init__(self, api: Api, shell: pathlib.Path):
        self.api = api
        self.shell = shell
        self.errors: list[str] = []
        self.file_cache: dict[pathlib.Path, Obj] = {}
        self.members_cache: dict = {}

    # -------------------------------------------------------------- files & scopes
    def parse(self, path: pathlib.Path) -> Obj | None:
        path = path.resolve() if False else path
        if path in self.file_cache:
            return self.file_cache[path]
        try:
            obj = parse_file(path)
        except ParseError as e:
            self.errors.append(f"{self.rel(path)}: api: parse: {e}")
            obj = None
        self.file_cache[path] = obj
        return obj

    def rel(self, path: pathlib.Path) -> str:
        try:
            return str(path.relative_to(self.shell.parent))
        except ValueError:
            return str(path)

    def scope_for(self, path: pathlib.Path, root_dir: pathlib.Path):
        """name -> ("cpp", class key) | ("qml", file path) | ("js", None) for one file."""
        text = path.read_text(encoding="utf-8")
        scope = {}
        # implicit import: own directory (lowest precedence)
        for f in path.parent.glob("*.qml"):
            if f.stem[:1].isupper():
                scope[f.stem] = ("qml", f)
        for m in re.finditer(r"^\s*import\s+(\"[^\"]+\"|[\w.]+)(?:\s+[\d.]+)?(?:\s+as\s+(\w+))?", text, re.M):
            target, alias = m.group(1), m.group(2)
            if target.startswith('"'):
                if alias:
                    scope[alias] = ("js", None)
                continue
            if target.startswith("qs."):
                d = root_dir.joinpath(*target.split(".")[1:])
                types = {}
                for f in d.glob("*.qml"):
                    if f.stem[:1].isupper():
                        types[f.stem] = ("qml", f)
                if alias:
                    scope[alias] = ("ns", types)
                else:
                    scope.update(types)
                continue
            types = self.api.module_types(target)
            if alias:
                scope[alias] = ("ns", types)
            else:
                scope.update(types)
        return scope

    # -------------------------------------------------------------- members
    def cpp_members(self, key) -> Members:
        ck = ("cpp", key)
        if ck in self.members_cache:
            return self.members_cache[ck]
        mem = Members()
        self.members_cache[ck] = mem
        for k in self.api.chain(key):
            if k is None:
                mem.open = True
                continue
            if isinstance(k, tuple) and k[0] == "enums-open":
                mem.enums_open = True
                continue
            if isinstance(k, tuple):
                # QML-defined base (Quickshell FileView.qml -> FileViewInternal)
                base = self.lookup_any(k[1])
                if base is not None:
                    self.merge(mem, base)
                continue
            c = self.api.classes[k]
            mem.names.append(k)
            for n, (t, w, final, notify) in c.get("p", {}).items():
                if n not in mem.props:
                    mem.props[n] = {"type": t, "w": bool(w), "final": bool(final), "notify": bool(notify),
                                    "src": k}
            mem.signals |= set(c.get("s", []))
            mem.methods |= set(c.get("f", []))
            mem.enums |= set(c.get("e", []))
            if c.get("d"):
                mem.default = True
            if c.get("a") and mem.attached is None:
                mem.attached = c["a"]
            if c.get("single"):
                mem.singleton = True
            if c.get("open"):
                mem.open = True
        mem.methods |= COMMON_METHODS
        return mem

    def merge(self, mem: Members, other: Members):
        for n, p in other.props.items():
            mem.props.setdefault(n, p)
        mem.signals |= other.signals
        mem.methods |= other.methods
        mem.enums |= other.enums
        mem.default = mem.default or other.default
        mem.enums_open = mem.enums_open or other.enums_open
        mem.attached = mem.attached or other.attached
        mem.open = mem.open or other.open
        mem.names += other.names

    def lookup_any(self, qml_name):
        """A type name from any Quickshell/Qt module (for QML-defined Quickshell types)."""
        for m, types in self.api.modules.items():
            if qml_name in types:
                return self.cpp_members(types[qml_name])
        return None

    def obj_members(self, obj: Obj, scope, path) -> Members:
        """Members of an object: its type plus what the object itself declares."""
        base = self.type_members(obj.type, scope, path)
        mem = Members()
        if base is None:
            mem.open = True
        else:
            self.merge(mem, base)
            mem.singleton = base.singleton
        for n, d in obj.props.items():
            mem.props[n] = {"type": d["type"], "w": not d["readonly"], "final": False, "notify": True,
                            "src": "decl", "decl": d}
            if d["default"]:
                mem.default = True
        mem.signals |= set(obj.signals)
        mem.methods |= set(obj.functions)
        mem.enums |= obj.enums
        return mem

    def type_members(self, type_name, scope, path) -> Members | None:
        entry = self.resolve(type_name, scope)
        if entry is None:
            return None
        kind, ref = entry
        if kind == "cpp":
            return self.cpp_members(ref)
        if kind == "qml":
            return self.qml_file_members(ref)
        if kind == "inline":
            return self.inline_members(ref, path)
        return None

    def resolve(self, type_name, scope):
        if "." in type_name:
            ns, _, rest = type_name.partition(".")
            e = scope.get(ns)
            if e and e[0] == "ns":
                return e[1].get(rest)
            return None
        return scope.get(type_name)

    def root_dir_of(self, path: pathlib.Path) -> pathlib.Path:
        # the config root: nearest ancestor with shell.qml (greeter/, setup/ or shell/)
        for p in [path.parent] + list(path.parents):
            if (p / "shell.qml").exists():
                return p
        return self.shell

    def qml_file_members(self, fpath: pathlib.Path) -> Members:
        key = ("qml", str(fpath))
        if key in self.members_cache:
            return self.members_cache[key]
        mem = Members()
        mem.open = True  # provisional (recursion guard)
        self.members_cache[key] = mem
        obj = self.parse(fpath)
        if obj is None:
            return mem
        scope = self.scope_for(fpath, self.root_dir_of(fpath))
        scope.update({n: ("inline", c) for n, c in obj.components.items()})
        full = self.obj_members(obj, scope, fpath)
        text = fpath.read_text(encoding="utf-8")
        full.singleton = bool(re.search(r"^\s*pragma\s+Singleton\b", text, re.M))
        mem.__dict__.update(full.__dict__)
        return mem

    def inline_members(self, comp: Obj, path) -> Members:
        key = ("inline", id(comp))
        if key in self.members_cache:
            return self.members_cache[key]
        mem = Members()
        mem.open = True
        self.members_cache[key] = mem
        root_dir = self.root_dir_of(path)
        scope = self.scope_for(path, root_dir)
        full = self.obj_members(comp, scope, path)
        mem.__dict__.update(full.__dict__)
        return mem

    # -------------------------------------------------------------- checks
    def err(self, path, line, msg):
        self.errors.append(f"{self.rel(path)}:{line}: api: {msg}")

    def check_file(self, path: pathlib.Path):
        root = self.parse(path)
        if root is None:
            return
        root_dir = self.root_dir_of(path)
        scope = self.scope_for(path, root_dir)
        scope.update({n: ("inline", c) for n, c in root.components.items()})
        ids: dict[str, Obj] = {}
        objs: list[Obj] = []

        def walk(o: Obj):
            objs.append(o)
            if o.id:
                ids[o.id] = o
            for c in o.children:
                walk(c)
            for _, c, *_ in o.values:
                walk(c)
            for _, c, _ in o.on:
                walk(c)
            for c in o.components.values():
                walk(c)

        walk(root)
        root.component_root = True
        mem_of = {}
        for o in objs:
            mem_of[id(o)] = self.obj_members(o, scope, path)
        self.mark_component_roots(objs, mem_of)
        for o in objs:
            self.check_obj(o, mem_of[id(o)], scope, path, ids, mem_of)
            # Variants sets `modelData` as an initial property (variants.cpp:152-156): the delegate
            # must have it, else "Could not set property modelData" and no screen/model value
            creator = getattr(o, "creator", ("", None))[0]
            if creator.split(".")[-1] == "Variants" and not mem_of[id(o)].open \
                    and "modelData" not in mem_of[id(o)].props:
                self.err(path, o.line, f"{o.type}: Variants delegate without a 'modelData' property")
        for o in objs:
            for toks in o.exprs:
                self.check_refs(toks, o, scope, path, ids, mem_of)

    def prop_type_members(self, ctype: str) -> Members | None:
        t = ctype.replace("const ", "").replace("&", "").strip()
        ptr = t.endswith("*")
        t = t.rstrip("*").strip().split("::")[-1]
        if t in self.api.valuetypes:
            vt = self.api.valuetypes[t]
            if vt in self.api.classes:
                return self.cpp_members(vt)
        if t in self.api.classes:
            return self.cpp_members(t)
        return None

    def check_grouped(self, o, mem, name, line, path, scope):
        """name = 'a.b[.c]' binding; returns False when reported."""
        first, rest = name.split(".", 1)
        if first[:1].isupper():
            # attached property: Keys.onPressed, WlrLayershell.layer, Layout.fillWidth
            e = self.resolve(first, scope)
            if e is None:
                self.err(path, line, f"{first}.{rest}: {first} is not a type in scope")
                return
            if e[0] != "cpp":
                self.err(path, line, f"{first}.{rest}: {first} has no attached properties")
                return
            tm = self.cpp_members(e[1])
            if not tm.attached:
                self.err(path, line, f"{first}.{rest}: {first} has no attached properties")
                return
            am = self.cpp_members(tm.attached)
            if am.open:
                return
            sub = rest.split(".")[0]
            if re.match(r"^on[A-Z]", sub):
                if not am.handler_ok(sub):
                    self.err(path, line, f"{first}.{sub}: attached {tm.attached} has no signal for {sub}")
            elif sub not in am.props:
                self.err(path, line, f"{first}.{sub}: attached {tm.attached} has no property {sub}")
            elif not am.props[sub]["w"] and "." not in rest:
                self.err(path, line, f"{first}.{sub}: read-only attached property")
            return
        p = mem.props.get(first)
        if p is None:
            if not mem.open:
                self.err(path, line, f"{o.type}: no property '{first}' (in '{name}')")
            return
        sub = rest.split(".")[0]
        if p.get("src") == "decl":
            decl = p.get("decl", {})
            if decl.get("alias"):
                return
            ptype = decl.get("type", "")
            pm = self.type_members(ptype, scope, path) if ptype[:1].isupper() else None
        else:
            pm = self.prop_type_members(p["type"])
        if pm is None or pm.open:
            return
        if re.match(r"^on[A-Z]", sub):
            if not pm.handler_ok(sub):
                self.err(path, line, f"{name}: {p['type']} has no signal for {sub}")
            return
        if sub not in pm.props:
            self.err(path, line, f"{name}: '{first}' ({p['type']}) has no property '{sub}'")

    def check_obj(self, o: Obj, mem: Members, scope, path, ids, mem_of):
        if mem.open and not mem.names and o.type != "<group>":
            if self.resolve(o.type, scope) is None:
                self.err(path, o.line, f"unknown type {o.type}")
                return
        for name, line in getattr(o, "dup", []):
            self.err(path, line, f"{o.type}: property '{name}' declared twice")
        # declared properties must not redeclare FINAL base properties
        base = self.type_members(o.type, scope, path)
        if base is not None:
            for n, d in o.props.items():
                bp = base.props.get(n)
                if bp is not None and bp.get("final"):
                    self.err(path, d["line"], f"{o.type}: 'property {d['type']} {n}' overrides a FINAL property")
                elif bp is not None and bp.get("src") not in ("decl", None):
                    # shadowing a Qt property (Item.state, Item.enabled…) confuses Qt's own logic
                    # and needs `override` from Qt 6.11 on
                    self.err(path, d["line"], f"{o.type}: 'property {d['type']} {n}' shadows {bp['src']}.{n}")
        # initial values of declared properties: `property string s: 5` fails like a binding
        for name, line, toks in getattr(o, "decl_values", []):
            if name in mem.props:
                self.check_literal(o, name, mem.props[name], toks, path, line)
        # plain and grouped bindings
        for name, line, toks, is_obj in o.bindings:
            if "." in name:
                self.check_grouped(o, mem, name, line, path, scope)
                continue
            p = mem.props.get(name)
            if p is None:
                if not mem.open:
                    self.err(path, line, f"{o.type}: no property '{name}'")
                continue
            if not p["w"] and not p["type"].startswith("QQmlListProperty"):
                self.err(path, line, f"{o.type}: '{name}' is read-only")
            elif toks:
                self.check_literal(o, name, p, toks, path, line)
        for name, line, sub in o.groups:
            if name[:1].isupper():
                for sname, sline, _t, _o in sub.bindings:
                    self.check_grouped(o, mem, name + "." + sname, sline, path, scope)
                continue
            if name not in mem.props:
                if not mem.open:
                    self.err(path, line, f"{o.type}: no property group '{name}'")
                continue
            for sname, sline, _t, _o in sub.bindings:
                self.check_grouped(o, mem, name + "." + sname, sline, path, scope)
            for hname, hline in sub.handlers:
                self.check_grouped(o, mem, name + "." + hname, hline, path, scope)
        for name, line in o.handlers:
            if "." in name:
                self.check_grouped(o, mem, name, line, path, scope)
                continue
            if not mem.handler_ok(name) and not mem.open:
                self.err(path, line, f"{o.type}: no signal for handler '{name}'")
        for target, child, line in o.on:
            first = target.split(".")[0]
            if first not in mem.props and not mem.open:
                self.err(path, line, f"{child.type} on {target}: {o.type} has no property '{first}'")
        # object values must match the property's class: `mask: Region {}`, `stdout: SplitParser {}`
        for name, child, line, declared in o.values:
            if declared or "." in name:
                continue
            p = mem.props.get(name)
            if p is None or p.get("src") == "decl":
                continue
            t = p["type"].replace("const ", "").strip()
            m = re.match(r"QQmlListProperty<\s*([\w:]+)\s*>", t)
            cls = (m.group(1) if m else t.rstrip("*").strip()).split("::")[-1]
            if not (m or t.endswith("*")) or cls in ("QObject", "QQmlComponent") or cls not in self.api.classes:
                continue
            cm = mem_of.get(id(child))
            if cm is None or cm.open:
                continue
            if cls not in cm.names:
                self.err(path, line, f"{o.type}.{name}: a {child.type} is not a {cls}")
        # children need a default property
        if o.children and not mem.default and not mem.open and o.type not in ("Component",):
            c = o.children[0]
            self.err(path, c.line, f"{c.type} declared inside {o.type}, which has no default property")
        # IpcHandler: only fully typed functions are registered (io/ipchandler.hpp)
        if "IpcHandler" in mem.names:
            for fn, sig in getattr(o, "signatures", {}).items():
                if not self.fully_typed(sig):
                    self.err(path, o.functions[fn], f"IpcHandler.{fn}: arguments and return type must be typed "
                                                    f"(string/int/bool/real/color/void), or `qs ipc` cannot see it")
        # `visible: x.visibleChildren.length > 0` latches: hidden items have no visible children
        for name, line, toks, _o in o.bindings:
            if name == "visible" and toks and any(t.v == "visibleChildren" for t in toks):
                self.err(path, line, f"{o.type}: visible bound to visibleChildren never recovers once hidden")
        # Connections: function onX() must match the target's signals
        if o.type == "Connections":
            self.check_connections(o, scope, path, ids, mem_of)
        # expressions: id.member and Type.member
        for toks in o.exprs:
            self.check_expr(toks, scope, path, ids, mem_of, o)
        for _n, _l, toks, _isobj in o.bindings:
            pass

    # literal bindings are type-checked by the QML compiler (QQmlPropertyValidator::validateLiteralBinding):
    # `text: 5`, `visible: 1`, `width: "10"` fail to load the component
    LITERAL_KIND = {"bool": "bool", "int": "number", "qint32": "number", "quint32": "number", "uint": "number",
                    "qint64": "number", "qreal": "number", "double": "number", "float": "number", "real": "number",
                    "QString": "string", "string": "string", "QUrl": "string", "url": "string",
                    "QColor": "color", "color": "color"}

    def check_literal(self, o, name, p, toks, path, line):
        vals = [t for t in toks if t.v != ";"]
        if len(vals) == 2 and vals[0].v == "-" and vals[1].k == "num":
            kind = "number"
        elif len(vals) == 1 and vals[0].k == "num":
            kind = "number"
        elif len(vals) == 1 and vals[0].k == "str":
            kind = "string"
        elif len(vals) == 1 and vals[0].k == "id" and vals[0].v in ("true", "false"):
            kind = "bool"
        else:
            return
        ptype = p.get("decl", {}).get("type") if p.get("src") == "decl" else p["type"]
        want = self.LITERAL_KIND.get((ptype or "").strip())
        if want is None:
            return
        ok = kind == want or (want == "color" and kind == "string")
        if want == "color" and kind == "string":
            v = vals[0].v
            ok = bool(re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})|[a-z]+", v))
        if not ok:
            self.err(path, line, f"{o.type}: '{name}: {' '.join(t.v for t in vals)}' — {want} expected ({ptype})")

    def check_connections(self, o: Obj, scope, path, ids, mem_of):
        target = None
        for name, line, toks, is_obj in o.bindings:
            if name == "target" and toks:
                names = [t.v for t in toks if t.k == "id" and t.v not in ("null", "undefined")]
                # `cond ? Target : null` -> the last identifier that names an id/singleton
                cands = [n for n in names if n in ids or (self.resolve(n, scope) is not None)]
                if cands:
                    target = cands[-1]
        if not target:
            return
        if target in ids:
            tm = mem_of[id(ids[target])]
        else:
            tm = self.type_members(target, scope, path)
        if tm is None or tm.open:
            return
        for fn, line in o.functions.items():
            if re.match(r"^on[A-Z]", fn) and not tm.handler_ok(fn):
                self.err(path, line, f"Connections: target {target} has no signal for {fn}")

    JS_GLOBALS = {"Qt", "Math", "JSON", "Date", "Number", "String", "Object", "Array", "console", "parseInt",
                  "parseFloat", "isNaN", "Infinity", "NaN", "RegExp", "Error", "Promise", "Map", "Set", "Symbol",
                  "Boolean", "encodeURIComponent", "decodeURIComponent", "Intl", "undefined", "null", "this",
                  "parent", "modelData", "model", "index", "arguments", "Uint8Array", "ArrayBuffer"}

    # ---------------------------------------------------------------- unresolved names (ReferenceError)
    def mark_component_roots(self, objs, mem_of):
        """Objects that start a new QML context: delegates, sourceComponent, Component children…
        `creator` records who instantiates them: (type of the owning object, property)."""
        for o in objs:
            mem = mem_of[id(o)]
            for name, child, _line, declared in o.values:
                p = mem.props.get(name)
                if name.endswith("effect") or name in ("delegate", "sourceComponent", "cursorDelegate",
                                                        "component", "surface", "handler"):
                    child.component_root = True
                    child.creator = (o.type, name)
                elif p is not None and "QQmlComponent" in str(p.get("type", "")):
                    child.component_root = True
                    child.creator = (o.type, name)
            if o.type == "Component":
                for c in o.children:
                    c.component_root = True
                    c.creator = ("Component", None)  # used elsewhere: creator unknown
                continue
            # default property of type Component (Repeater/Variants delegate, WlSessionLock surface)
            dprop = self.default_prop(mem)
            if dprop and "QQmlComponent" in str(mem.props.get(dprop, {}).get("type", "")):
                for c in o.children:
                    c.component_root = True
                    c.creator = (o.type, dprop)

    # Views whose delegates get `index`/`model`/`modelData` (+ roles) as context properties via
    # QQmlDelegateModel — unless the delegate has required properties: then the context object is
    # cleared and only the required properties are set (qqmldelegatemodel.cpp:966-976, Qt 6.10).
    # Required properties of the delegate's own QML type count too: the sub-creator inherits
    # isContextObject (qqmlobjectcreator.cpp:1380-1384, 1727).
    MODEL_VIEWS = {"Repeater", "ListView", "GridView", "PathView", "TableView", "TreeView", "Instantiator",
                   "DelegateModel"}
    # Creators that set no context properties at all (Quickshell Variants passes only the initial
    # property `modelData`, variants.cpp:152-156; loaders pass nothing).
    NO_MODEL_CREATORS = {"Variants", "Loader", "LazyLoader", "WlSessionLock"}

    def has_required(self, obj: Obj, scope, path, seen=None) -> bool:
        """Does instantiating `obj` involve top-level required properties (own or inherited)?"""
        if any(d.get("required") for d in obj.props.values()) or getattr(obj, "req_posthoc", None):
            return True
        seen = seen if seen is not None else set()
        e = self.resolve(obj.type, scope)
        if e is None or e[0] not in ("qml", "inline"):
            return False
        if e[0] == "inline":
            if id(e[1]) in seen:
                return False
            seen.add(id(e[1]))
            return self.has_required(e[1], scope, path, seen)
        if e[1] in seen:
            return False
        seen.add(e[1])
        fo = self.parse(e[1])
        if fo is None:
            return False
        fscope = self.scope_for(e[1], self.root_dir_of(e[1]))
        fscope.update({n: ("inline", c) for n, c in fo.components.items()})
        return self.has_required(fo, fscope, e[1], seen)

    def model_names_owner(self, chain, scope, path):
        """The component root whose context supplies bare modelData/index/model, or None.
        Returns (root, skipped) where `skipped` lists inner delegates that have required
        properties (their bare names fall through to an outer context)."""
        skipped = []
        for o in chain:
            if not getattr(o, "component_root", False):
                continue
            ctype, prop = getattr(o, "creator", ("<file>", None))
            if ctype in self.NO_MODEL_CREATORS or ctype.split(".")[-1] in self.NO_MODEL_CREATORS:
                continue
            known_view = ctype.split(".")[-1] in self.MODEL_VIEWS
            if not known_view and ctype not in ("<file>", "Component"):
                continue  # Loader-like creators (sourceComponent, effects…): names come from outside
            if self.has_required(o, scope, path):
                if known_view:
                    skipped.append(o)
                continue
            return o, skipped
        return None, skipped

    def default_prop(self, mem: Members):
        for k in mem.names:
            c = self.api.classes.get(k)
            if c and c.get("d"):
                return c["d"]
        return None

    QML_TYPES = {"string", "int", "bool", "real", "double", "var", "void", "color", "url", "date", "list",
                 "point", "rect", "size", "font", "vector2d", "vector3d", "vector4d", "matrix4x4", "quaternion",
                 "variant"}
    JS_WORDS = set("""if else for while do return const let var function new typeof instanceof in of delete void
        switch case default break continue throw try catch finally class extends super yield async await import
        export debugger with true false null undefined this NaN Infinity arguments get set static""".split())
    JS_NAMES = {"Qt", "Math", "JSON", "Date", "Number", "String", "Object", "Array", "console", "parseInt",
                "parseFloat", "isNaN", "isFinite", "RegExp", "Error", "TypeError", "RangeError", "Promise", "Map",
                "Set", "WeakMap", "WeakSet", "Symbol", "Boolean", "encodeURIComponent", "decodeURIComponent",
                "encodeURI", "decodeURI", "Intl", "BigInt", "globalThis", "Uint8Array", "ArrayBuffer",
                "DataView", "Reflect", "Proxy", "qsTr", "qsTranslate", "print", "gc", "XMLHttpRequest",
                "Component", "parent"}

    def check_refs(self, toks, owner: Obj, scope, path, ids, mem_of):
        if not toks:
            return
        known = set(self.JS_WORDS) | self.JS_NAMES | self.QML_TYPES | set(ids) | set(scope)
        before = set(known)
        for k, t in enumerate(toks):
            if t.k != "id":
                continue
            nxt = toks[k + 1] if k + 1 < len(toks) else None
            prv = toks[k - 1] if k > 0 else None
            if nxt is not None and nxt.v == "=>":
                known.add(t.v)
            if prv is not None and prv.v in ("let", "const", "var", "function", "catch", ","):
                known.add(t.v)  # `,`: `let a = 1, b = 2` (over-approximates, fine)
            if prv is not None and prv.v == "(" and k > 1 and toks[k - 2].v == "catch":
                known.add(t.v)
        for k, t in enumerate(toks):
            if t.v == "function" or (t.v == "(" and self._arrow_params(toks, k)):
                j = k + 1
                while j < len(toks) and toks[j].v != "(" and t.v == "function":
                    j += 1
                depth = 0
                while j < len(toks):
                    if toks[j].v in ("(", "[", "{"):
                        depth += 1
                    elif toks[j].v in (")", "]", "}"):
                        depth -= 1
                        if depth == 0:
                            break
                    elif toks[j].k == "id" and (toks[j - 1].v in ("(", ",", "{", "[", "...")):
                        known.add(toks[j].v)
                    j += 1
        local = known - before  # JS locals and parameters shadow QML names
        # names reachable without qualification: the scope object, then the context objects
        # (roots of the enclosing components, innermost first)
        chain = [owner]
        o = owner
        while o is not None:
            if getattr(o, "component_root", False) and o is not owner:
                chain.append(o)
            o = o.parent
        # `name = v` on a read-only property of the scope/context objects
        for k, t in enumerate(toks):
            if t.k != "id" or t.v in local or k + 1 >= len(toks) or toks[k + 1].v not in self.ASSIGN_OPS:
                continue
            if k > 0 and toks[k - 1].v in (".", "?.", "let", "const", "var"):
                continue
            for o in chain:
                m = mem_of.get(id(o))
                if m is None or m.open:
                    break
                if t.v in m.props:
                    self.check_assign(toks, k, m, t.v, path)
                    break
        open_scope = False
        for o in chain:
            m = mem_of.get(id(o))
            if m is None or m.open:
                open_scope = True
                continue
            known |= set(m.props) | m.signals | m.methods
        # delegates get model roles as context properties (not with required properties)
        mroot, skipped = self.model_names_owner(chain, scope, path)
        outer = set()
        if mroot is not None:
            outer = {"modelData", "index", "model"} - known
            known |= {"modelData", "index", "model"}
        if open_scope:
            return
        if skipped and outer:
            # legal QML, but the name resolves in an outer delegate's context: almost surely a bug
            for k, t in enumerate(toks):
                if t.k != "id" or t.v not in outer:
                    continue
                prv = toks[k - 1] if k > 0 else None
                nxt = toks[k + 1] if k + 1 < len(toks) else None
                if prv is not None and prv.v in (".", "?."):
                    continue
                if nxt is not None and nxt.v == ":" and prv is not None and prv.v in ("{", ","):
                    continue
                inner = f"{skipped[0].type}:{skipped[0].line}"
                if getattr(mroot, "creator", ("<file>", None))[0].split(".")[-1] in self.MODEL_VIEWS:
                    why = f"is the OUTER delegate's ({mroot.type}:{mroot.line})"
                else:
                    why = "is not set there (ReferenceError unless this file is itself a delegate)"
                self.err(path, t.line, f"bare '{t.v}' in a delegate with required properties ({inner}) "
                                       f"{why} — declare 'required property … {t.v}'")
        for k, t in enumerate(toks):
            if t.k != "id" or t.v in known:
                continue
            prv = toks[k - 1] if k > 0 else None
            nxt = toks[k + 1] if k + 1 < len(toks) else None
            if prv is not None and prv.v in (".", "?."):
                continue
            # object literal keys: `{ key: v }`, `, key: v` inside braces
            if nxt is not None and nxt.v == ":" and prv is not None and prv.v in ("{", ","):
                continue
            # shorthand property in object literal `{ a, b }` is rare; labels are not used
            self.err(path, t.line, f"'{t.v}' is not defined here (ReferenceError at runtime)")

    def check_expr(self, toks, scope, path, ids, mem_of, owner: Obj):
        if not toks:
            return
        # names declared inside the expression (params, locals) shadow ids
        local = set()
        for k, t in enumerate(toks):
            if t.k != "id":
                continue
            nxt = toks[k + 1] if k + 1 < len(toks) else None
            prv = toks[k - 1] if k > 0 else None
            if nxt is not None and nxt.v == "=>":
                local.add(t.v)
            if prv is not None and prv.v in ("let", "const", "var", "function", "catch"):
                local.add(t.v)
        # params in (a, b) => and function (a, b)
        for k, t in enumerate(toks):
            if t.v == "function" or (t.v == "(" and self._arrow_params(toks, k)):
                j = k + 1 if t.v == "(" else k + 1
                while j < len(toks) and toks[j].v != "(" and t.v == "function":
                    j += 1
                depth = 0
                while j < len(toks):
                    if toks[j].v == "(":
                        depth += 1
                    elif toks[j].v == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    elif toks[j].k == "id":
                        local.add(toks[j].v)
                    j += 1
            if t.v == "catch" and k + 2 < len(toks) and toks[k + 1].v == "(":
                local.add(toks[k + 2].v)
        for k, t in enumerate(toks):
            if t.k != "id" or k + 2 >= len(toks):
                continue
            prv = toks[k - 1] if k > 0 else None
            if prv is not None and prv.v in (".", "?."):
                continue
            if toks[k + 1].v not in (".", "?.") or toks[k + 2].k != "id":
                continue
            # object literal key `{ root: x }` is not an access
            name, member = t.v, toks[k + 2].v
            if name in local or name in self.JS_GLOBALS:
                continue
            if name in ids:
                m = mem_of[id(ids[name])]
                if m.open:
                    continue
                if not m.has_member(member) and member not in ids[name].functions and not self._attached_ok(m, member):
                    self.err(path, t.line, f"{name}.{member}: {ids[name].type} has no member '{member}'")
                    continue
                self.follow(toks, k + 2, m, name + "." + member, scope, path)
                continue
            e = scope.get(name)
            if e is None:
                continue
            if e[0] == "cpp":
                tm = self.cpp_members(e[1])
            elif e[0] == "qml":
                tm = self.qml_file_members(e[1])
            elif e[0] == "inline":
                tm = self.inline_members(e[1], path)
            else:
                continue
            if tm.open:
                continue
            if member[:1].isupper():
                # enum value (Text.ElideRight) or nested type
                if member not in tm.enums and not tm.enums_open:
                    self.err(path, t.line, f"{name}.{member}: no such enum value")
                continue
            if tm.singleton:
                if not tm.has_member(member):
                    self.err(path, t.line, f"{name}.{member}: singleton {name} has no member '{member}'")
                    continue
                self.follow(toks, k + 2, tm, name + "." + member, scope, path)
                continue
            if tm.attached:
                am = self.cpp_members(tm.attached)
                if not am.open and not am.has_member(member):
                    self.err(path, t.line, f"{name}.{member}: attached {tm.attached} has no member '{member}'")
                continue

    # QML basic types that are value types with members, and types we never look into
    BASIC = {"color": "QColor", "font": "QFont", "point": "QPointF", "size": "QSizeF", "rect": "QRectF",
             "vector2d": "QVector2D", "vector3d": "QVector3D", "vector4d": "QVector4D"}
    GENERIC = {"QObject", "QQuickItem", "QVariant", "QJSValue", "QVariantMap", "QVariantList", "QString",
               "QUrl", "QDateTime", "QByteArray", "QStringList"}

    def member_type(self, mem: Members, member: str, scope, path) -> Members | None:
        p = mem.props.get(member)
        if p is None:
            return None
        if p.get("src") == "decl":
            d = p.get("decl", {})
            if d.get("alias"):
                return None
            t = d.get("type", "")
            if t in self.BASIC:
                return self.prop_type_members(self.BASIC[t])
            if t[:1].isupper() and t not in ("QtObject", "Item"):
                return self.type_members(t, scope, path)
            return None
        t = p["type"].replace("const ", "").replace("&", "").strip()
        base = t.rstrip("*").strip().split("::")[-1]
        if base in self.GENERIC or "<" in base:
            return None
        return self.prop_type_members(t)

    ASSIGN_OPS = {"=", "+=", "-=", "*=", "/=", "%=", "++", "--"}

    def check_assign(self, toks, k, mem: Members, label, path):
        """`x.member = v` / `member++` on a read-only property is a TypeError at runtime."""
        if k + 1 >= len(toks) or toks[k + 1].v not in self.ASSIGN_OPS:
            return
        p = mem.props.get(toks[k].v)
        if p is not None and not p.get("w", True):
            what = "readonly property" if p.get("src") == "decl" else f"read-only {p.get('src')} property"
            self.err(path, toks[k].line, f"{label}: assigning a {what} (TypeError at runtime)")

    def follow(self, toks, k, mem: Members, label, scope, path):
        """toks[k] is a checked member of `mem`: check `.next` members along C++-typed properties."""
        self.check_assign(toks, k, mem, label, path)
        while k + 2 < len(toks) and toks[k + 1].v in (".", "?.") and toks[k + 2].k == "id":
            nxt_mem = self.member_type(mem, toks[k].v, scope, path)
            if nxt_mem is None or nxt_mem.open:
                return
            member = toks[k + 2].v
            if not nxt_mem.has_member(member):
                self.err(path, toks[k].line, f"{label}.{member}: {mem.props[toks[k].v]['type']} has no member "
                                             f"'{member}'")
                return
            label += "." + member
            mem = nxt_mem
            k += 2
            self.check_assign(toks, k, mem, label, path)

    IPC_TYPES = {"string", "int", "bool", "real", "color", "void"}

    def fully_typed(self, toks):
        # toks: ( params ) : type { body }
        depth, params, cur, i = 0, [], [], 0
        for i, t in enumerate(toks):
            if t.v == "(":
                depth += 1
                if depth == 1:
                    continue
            elif t.v == ")":
                depth -= 1
                if depth == 0:
                    break
            if depth == 1 and t.v == ",":
                params.append(cur)
                cur = []
            elif depth >= 1:
                cur.append(t.v)
        if cur:
            params.append(cur)
        for prm in params:
            if len(prm) != 3 or prm[1] != ":" or prm[2] not in self.IPC_TYPES:
                return False
        rest = toks[i + 1:i + 3]
        return len(rest) == 2 and rest[0].v == ":" and rest[1].v in self.IPC_TYPES

    @staticmethod
    def _arrow_params(toks, k):
        depth = 0
        for j in range(k, min(len(toks), k + 40)):
            if toks[j].v == "(":
                depth += 1
            elif toks[j].v == ")":
                depth -= 1
                if depth == 0:
                    return j + 1 < len(toks) and toks[j + 1].v == "=>"
        return False

    @staticmethod
    def _attached_ok(m, member):
        return False


def check(shell: pathlib.Path, files: list[pathlib.Path]) -> list[str]:
    if not API_FILE.exists():
        return []
    api = Api(json.loads(API_FILE.read_text(encoding="utf-8")))
    ch = Checker(api, shell)
    for f in files:
        if f.suffix == ".qml":
            ch.check_file(f)
    return ch.errors
