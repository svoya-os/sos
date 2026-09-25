import configparser
import datetime as dt
import json
import re
import tomllib
import unittest

from svoya_cli.config import set_user_value
from svoya_cli.config import load as load_cfg
from svoya_cli.paths import Paths
from svoya_cli.theme import apply as A
from svoya_cli.theme import engine
from svoya_cli.theme.colors import Color, terminal_palette

from .helpers import FakeRunner, SandboxTest

THEMES = ("graphite", "paper", "phosphor")


class ColorTest(unittest.TestCase):
    def test_argb_alpha_first(self):
        c = Color.parse("#24ffb547")
        self.assertEqual((c.r, c.g, c.b), (255, 181, 71))
        self.assertAlmostEqual(c.a, 0x24 / 255)
        self.assertEqual(c.hexa, "#24ffb547")
        self.assertEqual(c.stripa, "ffb54724")          # alpha last for fuzzel/Hyprland rgba()
        self.assertEqual(Color.parse("#ffb547").hexa, "#ffffb547")
        self.assertEqual(Color.parse("#abc").hex, "#aabbcc")
        with self.assertRaises(ValueError):
            Color.parse("ffb547")

    def test_filters(self):
        ctx = {"color": {"accent": Color.parse("#ffb547"), "surface": Color.parse("#141518"),
                         "soft": Color.parse("#24ffb547")}}
        r = lambda t: engine.render(t, ctx)  # noqa: E731
        self.assertEqual(r("{{ color.accent | hex }}"), "#ffb547")
        self.assertEqual(r("{{ color.accent | hexa }}"), "#ffffb547")
        self.assertEqual(r("{{ color.accent | rgb }}"), "255,181,71")
        self.assertEqual(r("{{ color.accent | rgba(0.5) }}"), "rgba(255,181,71,0.5)")
        self.assertEqual(r("{{ color.accent | strip }}"), "ffb547")
        self.assertEqual(r("{{ color.accent | ansi }}"), "38;2;255;181;71")
        self.assertEqual(r("{{ color.accent | mix(color.surface, 1) | hex }}"), "#141518")
        self.assertEqual(r("{{ color.soft | over(color.surface) | hex }}"), "#352c1f")
        self.assertEqual(r('{{ color.accent | mix("#000000", 0.5) | hex }}'), "#805b24")
        self.assertEqual(r("{{ color.soft }}"), "#24ffb547")     # translucent → ARGB
        self.assertEqual(r("a {{color.accent|hex}} b"), "a #ffb547 b")

    def test_errors_are_loud(self):
        with self.assertRaises(engine.TemplateError) as e:
            engine.render("x\n{{ color.nope }}", {"color": {}}, "t.conf")
        self.assertIn("t.conf:2", str(e.exception))
        with self.assertRaises(engine.TemplateError):
            engine.render("{{ color.a | shout }}", {"color": {"a": Color(1, 2, 3)}})
        with self.assertRaises(engine.TemplateError):
            engine.render("{{ name | hex }}", {"name": "x"})

    def test_terminal_palette(self):
        p = A.load_theme(Paths(env={"HOME": "/nonexistent"}), "paper")
        pal = terminal_palette(p.colors, p.mode)
        self.assertEqual(len([k for k in pal if re.fullmatch(r"c\d+", k)]), 16)
        # the accent never becomes an ANSI color: terminal programs look the same with every accent
        self.assertNotIn(p.colors["accent"], pal.values())
        self.assertEqual((pal["red"], pal["yellow"], pal["green"]), (p.colors["bad"], p.colors["warn"], p.colors["ok"]))
        other = dict(p.colors, accent=Color.parse("#ff00ff"))
        self.assertEqual(terminal_palette(other, p.mode), pal)


class TemplatesTest(SandboxTest):
    def rendered(self, theme_id: str) -> dict[str, str]:
        ctx = self.sb.ctx()
        theme = A.load_theme(ctx.paths, theme_id)
        vars_ = A.template_context(theme, ctx.paths)
        return {t.id: A.render_target(t, vars_, ctx.paths) for t in A.load_manifest(ctx.paths)}

    def test_all_templates_all_themes(self):
        for theme_id in THEMES:
            out = self.rendered(theme_id)
            self.assertEqual(set(out), {"hyprland", "kitty", "foot", "gtk3", "gtk4", "qt6ct-colors", "qt6ct",
                                        "btop-theme", "btop", "fastfetch", "fuzzel"})
            for tid, text in out.items():
                self.assertNotIn("{{", text, f"{theme_id}/{tid}")
            # hyprland: balanced braces, rgb()/rgba() hex only, hyprbars colors, no gaps
            h = out["hyprland"]
            self.assertEqual(h.count("{"), h.count("}"))
            self.assertIn("plugin {", h)
            self.assertIn("col.active_border = rgb(", h)
            self.assertNotIn("gaps_in", h)
            for m in re.findall(r"rgba?\(([^)]*)\)", h):
                self.assertRegex(m, r"^[0-9a-f]{6}([0-9a-f]{2})?$")
            # kitty: key value pairs, 16 colors
            self.assertEqual(len(re.findall(r"^color\d+\s+#[0-9a-f]{6}$", out["kitty"], re.M)), 16)
            # foot / fuzzel / qt6ct: valid INI
            for tid in ("foot", "fuzzel", "qt6ct", "qt6ct-colors"):
                cp = configparser.ConfigParser(interpolation=None, strict=False)
                cp.read_string("[main]\n" + out[tid] if tid in ("foot", "fuzzel") else out[tid])
            cp = configparser.ConfigParser(interpolation=None)
            cp.read_string(out["qt6ct-colors"])
            for key in ("active_colors", "inactive_colors", "disabled_colors"):
                colors = [c.strip() for c in cp["ColorScheme"][key].split(",")]
                self.assertEqual(len(colors), 22)
                self.assertTrue(all(re.fullmatch(r"#[0-9a-f]{8}", c) for c in colors), colors)
            fz = configparser.ConfigParser(interpolation=None, strict=False)
            fz.read_string("[main]\n" + out["fuzzel"])
            self.assertRegex(fz["colors"]["background"], r"^[0-9a-f]{8}$")    # rrggbbaa
            # gtk: libadwaita names, balanced braces; gtk4 has CSS variables
            for tid in ("gtk3", "gtk4"):
                self.assertIn("@define-color accent_bg_color #", out[tid])
                self.assertEqual(out[tid].count("{"), out[tid].count("}"))
            self.assertIn("--accent-bg-color:", out["gtk4"])
            self.assertNotIn("--accent", out["gtk3"])
            # fastfetch: JSONC → JSON
            j = json.loads("\n".join(ln for ln in out["fastfetch"].splitlines() if not ln.lstrip().startswith("//")))
            self.assertRegex(j["display"]["color"]["keys"], r"^38;2;\d+;\d+;\d+$")
            # btop: every line theme[x]="#rrggbb"
            for ln in out["btop-theme"].splitlines():
                if ln and not ln.startswith("#"):
                    self.assertRegex(ln, r'^theme\[[a-z_]+\]="#[0-9a-f]{6}"$')

    def test_theme_json_is_flat_argb(self):
        theme = A.load_theme(self.sb.ctx().paths, "graphite")
        tj = A.theme_json(theme, "auto", dt.datetime(2026, 9, 24, tzinfo=dt.timezone.utc))
        self.assertEqual(tj["accent"], "#ffffb547")
        self.assertEqual(tj["accentSoft"], "#24ffb547")
        self.assertEqual((tj["id"], tj["mode"], tj["pair"], tj["nameRu"], tj["choice"]), ("graphite", "dark", "paper", "Графит", "auto"))
        self.assertEqual((tj["radius"], tj["fast"], tj["glow"], tj["mono"]), (11, 120, True, "IBM Plex Mono"))
        self.assertTrue(all(not isinstance(v, (dict, list)) for v in tj.values()))
        with open(A.load_theme(self.sb.ctx().paths, "graphite").path, "rb") as f:
            tokens = tomllib.load(f)
        for section in ("color", "font", "shape", "motion", "effects"):
            for k in tokens[section]:
                self.assertIn(k, tj)


class ApplyTest(SandboxTest):
    def test_apply_backups_includes_and_idempotence(self):
        home = self.sb.home
        (home / ".config/kitty").mkdir(parents=True)
        (home / ".config/kitty/kitty.conf").write_text("font_size 13\nmap ctrl+t new_tab\n")
        (home / ".config/btop").mkdir(parents=True)
        (home / ".config/btop/btop.conf").write_text('#? btop\ncolor_theme = "Default"\nvim_keys = True\n')
        r = FakeRunner(available={"hyprctl", "pkill", "gsettings"})
        ctx = self.sb.ctx(r, HYPRLAND_INSTANCE_SIGNATURE="x", WAYLAND_DISPLAY="wayland-1")
        rep = A.apply_theme(ctx, "paper", cfg={"theme": {}, "location": {}})
        kitty = (home / ".config/kitty/kitty.conf").read_text()
        self.assertIn(A.MARKER, kitty)
        self.assertIn(f"include {home}/.config/kitty/kitty.conf.pre-svoya", kitty.splitlines()[2])
        self.assertEqual((home / ".config/kitty/kitty.conf.pre-svoya").read_text(), "font_size 13\nmap ctrl+t new_tab\n")
        btop = (home / ".config/btop/btop.conf").read_text()
        self.assertIn('color_theme = "svoya"', btop)
        self.assertIn("vim_keys = True", btop)                          # user keys kept (merge)
        tj = json.loads(ctx.paths.theme_json.read_text())
        self.assertEqual(tj["id"], "paper")
        self.assertTrue(r.called("hyprctl", "reload"))
        self.assertTrue(r.called("gsettings", "set", "org.gnome.desktop.interface", "color-scheme", "prefer-light"))
        # second run: nothing changes, no reloads
        r2 = FakeRunner(available={"hyprctl", "pkill", "gsettings"})
        rep2 = A.apply_theme(self.sb.ctx(r2, HYPRLAND_INSTANCE_SIGNATURE="x"), "paper", cfg={"theme": {}, "location": {}})
        self.assertFalse(any(t["changed"] for t in rep2["targets"]))
        self.assertEqual(r2.calls, [])
        self.assertTrue(any(t["changed"] for t in rep["targets"]))
        # a merge file svoya created is never backed up
        self.assertFalse((home / ".config/qt6ct/qt6ct.conf.pre-svoya").exists())

    def test_skip_and_dry_run(self):
        ctx = self.sb.ctx(dry_run=True)
        rep = A.apply_theme(ctx, "graphite", cfg={"theme": {"skip": ["kitty"]}, "location": {}})
        self.assertEqual(next(t for t in rep["targets"] if t["id"] == "kitty")["skipped"], "config")
        self.assertFalse((self.sb.home / ".config").exists())
        self.assertFalse(ctx.paths.theme_json.exists())

    def test_user_file_replaced_later_is_kept_with_timestamp(self):
        home = self.sb.home
        ctx = self.sb.ctx()
        (home / ".config/foot").mkdir(parents=True)
        (home / ".config/foot/foot.ini").write_text("font=Mono:size=9\n")
        A.apply_theme(ctx, "graphite", cfg={"theme": {}, "location": {}})
        (home / ".config/foot/foot.ini").write_text("font=Other:size=12\n")      # the user writes their own again
        A.apply_theme(ctx, "paper", cfg={"theme": {}, "location": {}})
        stamped = list((home / ".config/foot").glob("foot.ini.pre-svoya-*"))
        self.assertEqual(len(stamped), 1)
        self.assertEqual(stamped[0].read_text(), "font=Other:size=12\n")

    def test_merge_helpers(self):
        ini = "[Appearance]\nstyle=kvantum\n; keep me\n[Fonts]\nfixed=x\n"
        merged = A.merge_ini(ini, {"Appearance": {"style": "Fusion", "custom_palette": "true"}, "Interface": {"a": "1"}})
        self.assertIn("style=Fusion", merged)
        self.assertIn("; keep me", merged)
        self.assertIn("custom_palette=true", merged.split("[Fonts]")[0])
        self.assertIn("[Interface]\na=1", merged)
        kv = A.merge_keyvalue('#c\ncolor_theme = "Default"\n', {"color_theme": '"svoya"', "truecolor": "true"})
        self.assertEqual(kv, '#c\ncolor_theme = "svoya"\ntruecolor = true\n')


class AutoTest(SandboxTest):
    def test_auto_by_sun_in_tallinn(self):
        cfg = {"theme": {}, "location": {"latitude": 59.437, "longitude": 24.745}}
        paths = self.sb.ctx().paths
        noon = dt.datetime(2026, 6, 21, 10, 0, tzinfo=dt.timezone.utc)
        midnight = dt.datetime(2026, 12, 21, 22, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(A.resolve("auto", cfg, noon, paths), ("paper", "sun"))
        self.assertEqual(A.resolve("auto", cfg, midnight, paths), ("graphite", "sun"))
        self.assertEqual(A.resolve("phosphor", cfg, noon, paths), ("phosphor", "explicit"))

    def test_fallback_without_location(self):
        tid, why = A.resolve("auto", {"theme": {}, "location": {"latitude": "x"}},
                             dt.datetime(2026, 9, 24, 12, tzinfo=dt.timezone.utc), self.sb.ctx().paths)
        self.assertIn("fallback", why)
        self.assertIn(tid, ("paper", "graphite"))

    def test_choice_is_remembered(self):
        paths = self.sb.ctx().paths
        set_user_value(paths, "theme", "id", "paper")
        set_user_value(paths, "location", "latitude", "x")
        set_user_value(paths, "theme", "id", "phosphor")
        cfg = load_cfg(paths)
        self.assertEqual(cfg["theme"]["id"], "phosphor")
        self.assertEqual(paths.user_config.read_text().count("[theme]"), 1)


if __name__ == "__main__":
    unittest.main()
