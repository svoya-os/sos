"""`sos theme accent` / `sos theme apply <id>` as undoable look changes, `sos undo`, and `--system`."""
import argparse
import contextlib
import datetime as dt
import io
import json
import pathlib

from svoya_cli import commands, journal, update
from svoya_cli.config import load as load_cfg
from svoya_cli.config import set_user_value, unset_user_value, user_value
from svoya_cli.theme import cli as theme_cli
from svoya_cli.theme import avatar_export, look

from .helpers import NOW, FakeRunner, Result, SandboxTest, capture, fixture


def accent_args(*value, **kw):
    base = dict(theme_cmd="accent", value=list(value), undo=False, system=False, dry_run=False, json=False)
    base.update(kw)
    return argparse.Namespace(**base)


def apply_args(theme=None, **kw):
    base = dict(theme_cmd="apply", theme=theme, dry_run=False, force=False, only=[], system=False, json=False, quiet=False)
    base.update(kw)
    return argparse.Namespace(**base)


class AccentCommandTest(SandboxTest):
    def setUp(self):
        super().setUp()
        self.runner = FakeRunner(available=set())
        self.ctx = self.sb.ctx(self.runner)

    def theme_json(self) -> dict:
        return json.loads(self.ctx.paths.theme_json.read_text())

    def test_set_undo_and_calm_confirmation(self):
        self.assertEqual(theme_cli.main(accent_args("сирень"), self.ctx), 0)
        self.assertEqual(self.output().strip().splitlines(), ["› accent Lilac · undo: sos undo"])
        self.assertEqual(user_value(self.ctx.paths, "theme", "accent"), "lilac")
        tj = self.theme_json()
        self.assertEqual((tj["accentId"], tj["accentNameRu"]), ("lilac", "Сирень"))
        self.assertEqual(tj["accent"], "#ffbba4ff")                               # NOW is evening in Tallinn → Graphite
        e = journal.newest(self.ctx.paths)
        self.assertEqual((e["id"], e["before"], e["after"]), ("look-1", {"theme": None, "accent": None},
                                                              {"theme": None, "accent": "lilac"}))
        self.assertEqual(e["description"], {"en": "accent Lilac", "ru": "акцент Сирень"})
        # the same again: nothing new to undo
        self.buf.truncate(0)
        self.buf.seek(0)
        theme_cli.main(accent_args("lilac"), self.ctx)
        self.assertIn("accent is already Lilac", self.output())
        self.assertEqual(len(journal.entries(self.ctx.paths)), 1)
        # --undo: back to the theme's default (signal), config key removed
        self.assertEqual(theme_cli.main(accent_args(undo=True), self.ctx), 0)
        self.assertIsNone(user_value(self.ctx.paths, "theme", "accent"))
        self.assertEqual(self.theme_json()["accentId"], "signal")
        self.assertEqual(journal.entries(self.ctx.paths), [])
        self.assertNotIn("[theme]", self.ctx.paths.user_config.read_text())         # no empty section left

    def test_custom_hex_reports_adjustment(self):
        rc, out = capture(theme_cli.main, accent_args("#3a0ca3", json=True), self.ctx)
        data = json.loads(out)
        self.assertEqual(rc, 0)
        acc = data["accent"]
        self.assertEqual((acc["id"], acc["custom"], acc["adjusted"]), ("custom", "#3a0ca3", True))
        self.assertGreaterEqual(acc["contrast"], 4.5)
        self.assertEqual(data["undo"], "look-1")
        self.assertEqual(self.theme_json()["accentCustom"], "#3a0ca3")
        self.buf.truncate(0)
        self.buf.seek(0)
        theme_cli.main(accent_args("#1b0a4a"), self.ctx)
        self.assertRegex(self.output(), r"accent #1b0a4a → #[0-9a-f]{6} \(lighter for readability, 4\.\d:1\) · undo: sos undo")

    def test_errors_and_dry_run(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(theme_cli.main(accent_args("красный"), self.ctx), 2)
            self.assertEqual(theme_cli.main(accent_args("lilca"), self.ctx), 2)
        self.assertIn("red is reserved for errors", err.getvalue())
        self.assertIn("Did you mean: lilac", err.getvalue())
        dry = self.sb.ctx(FakeRunner(), dry_run=True)
        rc, out = capture(theme_cli.main, accent_args("rose", json=True, dry_run=True), dry)
        self.assertEqual(json.loads(out)["accent"]["color"], "#ff82b2")               # preview for the swatch hover
        self.assertFalse(dry.paths.user_config.exists())
        self.assertFalse(dry.paths.theme_json.exists())
        self.assertEqual(journal.entries(dry.paths), [])

    def test_theme_apply_is_undoable_too(self):
        theme_cli.main(apply_args("paper"), self.ctx)
        self.assertIn("undo: sos undo", self.output())
        self.assertEqual(user_value(self.ctx.paths, "theme", "id"), "paper")
        theme_cli.main(accent_args("ice"), self.ctx)
        self.assertEqual(self.theme_json()["accent"], "#ff006f8e")                      # Ice, light variant
        # `sos undo` twice: accent first, then the theme
        undo = argparse.Namespace(list=False, json=False, n=None, yes=False, config="root")
        self.assertEqual(update.main_undo(undo, self.ctx), 0)
        self.assertEqual((self.theme_json()["id"], self.theme_json()["accentId"]), ("paper", "signal"))
        self.assertEqual(update.main_undo(undo, self.ctx), 0)
        self.assertEqual((self.theme_json()["id"], self.theme_json()["choice"]), ("graphite", "auto"))
        self.assertIsNone(user_value(self.ctx.paths, "theme", "id"))
        self.assertIn("undone: theme Paper", self.output())

    def test_timer_and_session_applies_are_not_journaled(self):
        theme_cli.main(apply_args(None, quiet=True), self.ctx)
        self.assertEqual(journal.entries(self.ctx.paths), [])


class UndoOrderTest(SandboxTest):
    """`sos undo` without an id takes the newest change: a look change or an sos snapshot pair."""

    def snapper_runner(self):
        self.sb.write("/etc/snapper/configs/root", "")
        return FakeRunner({"snapper --utc --jsonout": fixture("snapper/list.json"),
                           "snapper -c root status": "c..... /etc/x\n", "snapper -c root create": Result(0, "50\n"),
                           "snapper -c root undochange": Result(0)}, available={"snapper"})

    def test_newer_look_change_wins(self):
        r = self.snapper_runner()
        ctx = self.sb.ctx(r)                                           # NOW 18:42 > pair 41/42 at 18:00
        theme_cli.main(accent_args("rose"), ctx)
        rc = update.main_undo(argparse.Namespace(list=False, json=False, n=None, yes=False, config="root"), ctx)
        self.assertEqual(rc, 0)
        self.assertFalse(r.called("snapper", "-c", "root", "undochange"))
        self.assertIsNone(user_value(ctx.paths, "theme", "accent"))

    def test_newer_snapshot_wins_and_list_merges_both(self):
        r = self.snapper_runner()
        early = self.sb.ctx(r, now=NOW - dt.timedelta(hours=2))        # accent changed at 16:42, pair at 18:00
        theme_cli.main(accent_args("rose"), early)
        ctx = self.sb.ctx(r)
        rc, out = capture(update.main_undo, argparse.Namespace(list=True, json=True, n=None, yes=False, config="root"), ctx)
        rows = json.loads(out)
        self.assertEqual([x["id"] for x in rows], ["look-1", "41"])
        self.assertEqual(rows[0]["kind"], "look")
        rc = update.main_undo(argparse.Namespace(list=False, json=False, n=None, yes=True, config="root"), ctx)
        self.assertEqual(rc, 0)
        self.assertTrue(r.called("snapper", "-c", "root", "undochange", "41..42"))
        self.assertEqual(user_value(ctx.paths, "theme", "accent"), "rose")          # the look change is still there
        # … and can be named explicitly
        self.assertEqual(update.main_undo(argparse.Namespace(list=False, json=False, n="look-1", yes=False, config="root"), ctx), 0)
        self.assertIsNone(user_value(ctx.paths, "theme", "accent"))

    def test_snapshot_ids_in_every_spelling(self):
        self.assertEqual([update._snapshot_number(x) for x in (7, "7", "#7", "snap-7", "look-7", None)], [7, 7, 7, 7, None, None])
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = update.main_undo(argparse.Namespace(list=False, json=False, n="look-9", yes=True, config="root"), self.sb.ctx())
        self.assertEqual(rc, 2)

    def test_without_snapper_only_looks(self):
        ctx = self.sb.ctx(FakeRunner())
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(update.main_undo(argparse.Namespace(list=False, json=False, n=None, yes=True, config="root"), ctx), 2)
        theme_cli.main(accent_args("mono"), ctx)
        self.assertEqual(update.main_undo(argparse.Namespace(list=False, json=False, n=None, yes=False, config="root"), ctx), 0)


class SystemWriteTest(SandboxTest):
    def test_non_root_goes_through_pkexec_with_ids_only(self):
        r = FakeRunner({"pkexec": Result(0)}, available={"pkexec"})
        ctx = self.sb.ctx(r)
        rc = theme_cli.main(accent_args("#3a0ca3", system=True), ctx)
        self.assertEqual(rc, 0)
        call = next(c for c in r.calls if c[0] == "pkexec")
        self.assertEqual(call[-8:], ["theme", "system-write", "--theme", "graphite", "--accent", "#3a0ca3", "--avatar", ""])
        self.assertIn("login screen too", self.output())
        self.assertTrue(journal.newest(ctx.paths)["system"])
        # undo also restores the login screen
        update.main_undo(argparse.Namespace(list=False, json=False, n=None, yes=False, config="root"), ctx)
        last = [c for c in r.calls if c[0] == "pkexec"][-1]
        self.assertEqual(last[-4:-2], ["--accent", "default"])

    def test_pkexec_refused_keeps_the_user_change(self):
        r = FakeRunner({"pkexec": Result(126, "", "Not authorized")}, available={"pkexec"})
        ctx = self.sb.ctx(r)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = theme_cli.main(accent_args("ice", system=True), ctx)
        self.assertEqual(rc, 1)
        self.assertIn("login screen was not changed", err.getvalue())
        self.assertEqual(user_value(ctx.paths, "theme", "accent"), "ice")

    def test_root_half_rederives_everything_from_system_files(self):
        ctx = self.sb.ctx(uid=0)
        args = argparse.Namespace(theme_cmd="system-write", theme_id="paper", accent="lilac", dry_run=False, quiet=True)
        self.assertEqual(theme_cli.main(args, ctx), 0)
        data = json.loads(self.sb.path("/etc/svoya/theme.json").read_text())
        # the login screen is dark and neutral: Paper's dark pair (Graphite), lilac's dark variant
        self.assertEqual((data["id"], data["mode"], data["accentId"], data["accent"]), ("graphite", "dark", "lilac", "#ffbba4ff"))
        self.assertEqual(data["choice"], "system")
        for bad in (argparse.Namespace(theme_cmd="system-write", theme_id="../../etc/passwd", accent="lilac", dry_run=False, quiet=True),
                    argparse.Namespace(theme_cmd="system-write", theme_id="graphite", accent="$(reboot)", dry_run=False, quiet=True)):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(theme_cli.main(bad, ctx), 2)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(theme_cli.main(args, self.sb.ctx(uid=1000)), 2)           # never as a user

    def test_root_writes_directly(self):
        ctx = self.sb.ctx(FakeRunner(), uid=0)
        res = look.change(ctx, load_cfg(ctx.paths), accent="rose", set_accent=True, system=True)
        self.assertTrue(res["system"]["ok"])
        self.assertEqual(json.loads(self.sb.path("/etc/svoya/theme.json").read_text())["accentId"], "rose")


class AvatarExportTest(SandboxTest):
    """Jackson's look goes to the login screen with the theme (DESIGN §12–§13)."""

    def write_avatar(self, ctx, data):
        path = ctx.paths.user_config_dir / "avatar.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False))

    def test_user_look_crosses_as_a_validated_spec(self):
        r = FakeRunner({"pkexec": Result(0)}, available={"pkexec"})
        ctx = self.sb.ctx(r)
        self.write_avatar(ctx, {"character": "cat", "skin": "snow", "glasses": "round", "hood": False,
                                "name": "Кеша; rm -rf", "outfit": "$(reboot)", "extra": "kept only at home"})
        theme_cli.main(accent_args("ice", system=True), ctx)
        call = next(c for c in r.calls if c[0] == "pkexec")
        spec = call[call.index("--avatar") + 1]
        self.assertEqual(spec, "character=cat;skin=snow;glasses=round;hood=0;name=%D0%9A%D0%B5%D1%88%D0%B0%3B%20rm%20-rf")
        self.assertEqual(avatar_export.decode(spec), {"character": "cat", "skin": "snow", "glasses": "round",
                                                      "hood": False, "name": "Кеша; rm -rf"})

    def test_root_half_writes_a_world_readable_copy(self):
        ctx = self.sb.ctx(uid=0)
        args = argparse.Namespace(theme_cmd="system-write", theme_id="graphite", accent="lilac", dry_run=False,
                                  quiet=True, avatar="character=imp;skin=mint;outfit=%23123abc;headphones=0")
        self.assertEqual(theme_cli.main(args, ctx), 0)
        path = self.sb.path("/etc/svoya/avatar.json")
        self.assertEqual(json.loads(path.read_text()), {"character": "imp", "skin": "mint", "outfit": "#123abc",
                                                        "headphones": False})
        self.assertEqual(path.stat().st_mode & 0o777, 0o644)
        # an empty look removes the copy: the greeter shows the default Jackson again
        args.avatar = ""
        self.assertEqual(theme_cli.main(args, ctx), 0)
        self.assertFalse(path.exists())

    def test_root_half_refuses_anything_unexpected(self):
        ctx = self.sb.ctx(uid=0)
        for spec in ("character=dragon", "skin=ember;skin=wine", "name=<b>", "hood=yes", "evil=1",
                     "character=imp;skin=snow", "outfit=%24(reboot)", "x" * 500, "name"):
            args = argparse.Namespace(theme_cmd="system-write", theme_id="graphite", accent="lilac", dry_run=False,
                                      quiet=True, avatar=spec)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(theme_cli.main(args, ctx), 2, spec)
        self.assertFalse(self.sb.path("/etc/svoya/avatar.json").exists())

    def test_same_rules_as_jackson(self):
        import ast
        src = pathlib.Path(__file__).resolve().parents[2] / "jackson" / "jackson" / "avatar.py"
        consts = {}
        for node in ast.parse(src.read_text(encoding="utf-8")).body:          # literals only, nothing runs
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                try:
                    consts[node.targets[0].id] = ast.literal_eval(node.value)
                except ValueError:
                    pass
        for name in ("CHARACTERS", "SKINS", "STYLES", "GLASSES", "ACCENT_IDS", "KEYS"):
            self.assertEqual(getattr(avatar_export, name), consts[name], name)


class ConfigAndWordsTest(SandboxTest):
    def test_unset_keeps_other_keys_and_comments(self):
        paths = self.sb.ctx().paths
        set_user_value(paths, "theme", "id", "paper")
        set_user_value(paths, "theme", "accent", "#123456")
        set_user_value(paths, "location", "latitude", 1.5)
        self.assertTrue(unset_user_value(paths, "theme", "accent"))
        self.assertFalse(unset_user_value(paths, "theme", "accent"))
        cfg = load_cfg(paths)
        self.assertEqual((cfg["theme"]["id"], cfg["location"]["latitude"]), ("paper", 1.5))
        self.assertNotIn("accent", cfg["theme"])

    def test_friendly_forms(self):
        n = commands.normalize
        self.assertEqual(n(["акцент", "сирень"]), ["theme", "accent", "сирень"])
        self.assertEqual(n(["accent"]), ["theme", "accent"])
        self.assertEqual(n(["accents", "--json"]), ["theme", "accents", "--json"])
        self.assertEqual(n(["theme", "lilac"]), ["theme", "accent", "lilac"])
        self.assertEqual(n(["тема", "лёд"]), ["theme", "accent", "лёд"])
        self.assertEqual(n(["theme", "#7f5af0"]), ["theme", "accent", "#7f5af0"])
        self.assertEqual(n(["тема", "акцент", "фиолетовый"]), ["theme", "accent", "фиолетовый"])
        self.assertEqual(n(["theme", "phosphor"]), ["theme", "apply", "phosphor"])      # the base theme wins
        self.assertEqual(n(["тема", "фосфор"]), ["theme", "apply", "phosphor"])
        self.assertEqual(n(["ии", "выкл"]), ["ai", "off"])
        self.assertEqual(n(["ai", "вкл", "--system"]), ["ai", "on", "--system"])
        self.assertEqual(n(["ai"]), ["ai", "status"])
        self.assertIn("lilac", commands.complete(["accent", "li"]))
        self.assertIn("сирень", commands.complete(["theme", "accent", "сир"]))
        self.assertEqual(commands.complete(["ai", "o"]), ["off", "on"])


if __name__ == "__main__":
    import unittest
    unittest.main()
