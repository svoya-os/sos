"""Accent system: OKLCH math, WCAG contrast, name parsing, resolution, and every template for every
accent × base theme (design/DESIGN.md §10–§11)."""
import configparser
import datetime as dt
import json
import random
import re
import unittest

from svoya_cli.paths import Paths
from svoya_cli.theme import accents as AC
from svoya_cli.theme import apply as A
from svoya_cli.theme import engine
from svoya_cli.theme.colors import Color, terminal_palette

from .helpers import FakeRunner, SandboxTest

BASES = ("graphite", "paper", "phosphor")
CHECKOUT = Paths(env={"HOME": "/nonexistent"})
C = Color.parse


class OklchTest(unittest.TestCase):
    def test_round_trip_every_8bit_color_sample(self):
        rnd = random.Random(7)
        samples = [Color(r, g, b) for r in range(0, 256, 15) for g in range(0, 256, 15) for b in range(0, 256, 15)]
        samples += [Color(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)) for _ in range(3000)]
        samples += [C("#000000"), C("#ffffff"), C("#ff0000"), C("#00ff00"), C("#0000ff"), C("#808080")]
        for c in samples:
            self.assertEqual(Color.from_oklch(*c.oklch()), c, c.hex)

    def test_reference_values(self):
        # Ottosson's reference: sRGB red = oklch(0.628 0.2577 29.23)
        L, Cc, h = C("#ff0000").oklch()
        self.assertAlmostEqual(L, 0.6280, places=3)
        self.assertAlmostEqual(Cc, 0.2577, places=3)
        self.assertAlmostEqual(h, 29.23, places=1)
        self.assertAlmostEqual(C("#ffffff").oklch()[0], 1.0, places=6)
        self.assertEqual(C("#000000").oklch(), (0.0, 0.0, 0.0))
        self.assertLess(C("#808080").oklch()[1], 1e-6)                    # grays have no chroma

    def test_out_of_gamut_keeps_lightness_and_hue(self):
        c = Color.from_oklch(0.9, 0.4, 150)                               # far outside sRGB
        L, Cc, h = c.oklch()
        self.assertAlmostEqual(L, 0.9, delta=0.01)
        self.assertAlmostEqual(h, 150, delta=2)
        self.assertLess(Cc, 0.4)
        self.assertEqual(Color.from_oklch(1.2, 0.1, 10), C("#ffffff"))   # clamped


class ContrastTest(unittest.TestCase):
    def test_wcag_values(self):
        self.assertAlmostEqual(C("#000000").contrast(C("#ffffff")), 21.0, places=6)
        self.assertAlmostEqual(C("#777777").contrast(C("#ffffff")), 4.48, places=2)
        self.assertAlmostEqual(C("#2b3af7").contrast(C("#f8f7f3")), C("#f8f7f3").contrast(C("#2b3af7")))
        self.assertEqual(C("#123456").contrast(C("#123456")), 1.0)

    def test_fit_contrast_moves_only_lightness(self):
        dark_surface, light_surface = C("#141518"), C("#f8f7f3")
        for hexv in ("#3a0ca3", "#202020", "#5a2a00", "#003300", "#7f00ff"):
            src = C(hexv)
            out, adjusted = AC.fit_contrast(src, dark_surface)
            self.assertTrue(adjusted, hexv)
            self.assertGreaterEqual(out.contrast(dark_surface), AC.MIN_CONTRAST, hexv)
            self.assertGreater(out.oklch()[0], src.oklch()[0])                     # lighter on dark bases
            if src.oklch()[1] > 0.02:
                self.assertAlmostEqual(out.oklch()[2], src.oklch()[2], delta=3, msg=hexv)   # hue kept
            # minimal: a step darker would fail
            L, Cc, h = out.oklch()
            self.assertLess(Color.from_oklch(L - 0.01, Cc, h).contrast(dark_surface), AC.MIN_CONTRAST + 0.2)
        for hexv in ("#ffff00", "#9fe2bf", "#ffc0cb"):
            out, adjusted = AC.fit_contrast(C(hexv), light_surface)
            self.assertTrue(adjusted)
            self.assertGreaterEqual(out.contrast(light_surface), AC.MIN_CONTRAST)
            self.assertLess(out.oklch()[0], C(hexv).oklch()[0])                    # darker on light bases
        same, adjusted = AC.fit_contrast(C("#bba4ff"), dark_surface)
        self.assertEqual((same, adjusted), (C("#bba4ff"), False))
        # chroma is kept where the gamut allows it
        out, _ = AC.fit_contrast(C("#6a3fd6"), dark_surface)
        self.assertAlmostEqual(out.oklch()[1], C("#6a3fd6").oklch()[1], delta=0.02)

    def test_derived_tokens(self):
        self.assertEqual(C("#ffb547").ink(), C("#141518"))
        self.assertEqual(C("#2b3af7").ink(), C("#ffffff"))
        up = AC.strong_variant(C("#ffb547"), "dark")
        self.assertAlmostEqual(up.oklch()[0] - C("#ffb547").oklch()[0], 0.06, delta=0.005)
        down = AC.strong_variant(C("#2b3af7"), "light")
        self.assertAlmostEqual(down.oklch()[0] - C("#2b3af7").oklch()[0], -0.06, delta=0.005)
        flipped = AC.strong_variant(C("#ffffff"), "dark")                # no room above white → darker
        self.assertLess(flipped.oklch()[0], 1.0)
        self.assertEqual(engine.render("{{ c | ink | hex }}", {"c": C("#f5cf52")}), "#141518")
        self.assertEqual(engine.render("{{ c | ink | hex }}", {"c": C("#8a6100")}), "#ffffff")


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.cat = AC.load_catalog(CHECKOUT)

    def test_ids_names_and_color_words(self):
        p = lambda t: AC.parse_choice(t, self.cat)  # noqa: E731
        for aid in ("signal", "amber", "ink", "phosphor", "ice", "lilac", "rose", "mono"):
            self.assertEqual(p(aid), aid)
            self.assertEqual(p(aid.upper()), aid)
        ru = {"сигнал": "signal", "янтарь": "amber", "чернила": "ink", "фосфор": "phosphor", "лёд": "ice",
              "лед": "ice", "сирень": "lilac", "роза": "rose", "моно": "mono", "Сирень": "lilac", "ЛЁД": "ice"}
        words = {"фиолетовый": "lilac", "синий": "ink", "зелёный": "phosphor", "зеленый": "phosphor",
                 "голубой": "ice", "розовый": "rose", "оранжевый": "amber", "жёлтый": "amber", "желтый": "amber",
                 "белый": "mono", "чёрный": "mono", "серый": "mono",
                 # inflections Jackson passes through: «сделай акцент фиолетовым»
                 "фиолетовым": "lilac", "сиреневый": "lilac", "ледяной": "ice", "синего": "ink", "зелёным": "phosphor",
                 "«Сирень»": "lilac", "violet": "lilac", "purple": "lilac", "Blue": "ink", "green": "phosphor",
                 "pink": "rose", "orange": "amber", "yellow": "amber", "grey": "mono", "gray": "mono",
                 "сделай фиолетовым": "lilac"}
        for text, want in {**ru, **words}.items():
            self.assertEqual(p(text), want, text)

    def test_hex_and_reset(self):
        p = lambda t: AC.parse_choice(t, self.cat)  # noqa: E731
        self.assertEqual(p("#7F5AF0"), "#7f5af0")
        self.assertEqual(p("7f5af0"), "#7f5af0")
        self.assertEqual(p("#abc"), "#aabbcc")
        for w in ("default", "по-умолчанию", "сброс", "стандартный"):
            self.assertIsNone(p(w), w)

    def test_rejections(self):
        p = lambda t: AC.parse_choice(t, self.cat)  # noqa: E731
        for bad in ("", "xyz", "#12345678", "#ggg", "add"):
            with self.assertRaises(AC.AccentError, msg=bad):
                p(bad)
        for red in ("красный", "red", "красным"):            # red belongs to errors (DESIGN §10)
            with self.assertRaises(AC.AccentError) as e:
                p(red)
            self.assertEqual(e.exception.hint, "rose")

    def test_catalog(self):
        self.assertEqual(self.cat.default, "signal")
        self.assertEqual(list(self.cat.accents), ["signal", "amber", "ink", "phosphor", "ice", "lilac", "rose", "mono"])
        self.assertEqual(self.cat.get("signal").dark, C("#ffb547"))
        self.assertEqual(self.cat.get("signal").light, C("#2b3af7"))
        self.assertEqual(self.cat.get("ice").name["ru"], "Лёд")


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self.cat = AC.load_catalog(CHECKOUT)
        self.themes = {b: A.load_theme(CHECKOUT, b) for b in BASES}

    def resolve(self, choice, base):
        t = self.themes[base]
        return AC.resolve(choice, mode=t.mode, colors=t.colors, catalog=self.cat, theme_default=t.data.get("accentDefault"))

    def test_builtins_pass_design_contrast_on_every_base(self):
        """DESIGN §10: every accent variant ≥ 5:1 on its surfaces and ≥ 5.4:1 for accentInk — unadjusted."""
        for base in BASES:
            for aid in self.cat.accents:
                r = self.resolve(aid, base)
                self.assertFalse(r.adjusted, (aid, base))
                self.assertEqual(r.color, self.cat.get(aid).variant(self.themes[base].mode), (aid, base))
                self.assertGreaterEqual(r.contrast, 5.0, (aid, base))
                self.assertGreaterEqual(r.ink_contrast, 5.4, (aid, base))
                self.assertIn(r.ink, (C("#141518"), C("#ffffff")))
                alpha = 0x24 if self.themes[base].mode == "dark" else 0x17               # 14 % / 9 %
                self.assertEqual(r.soft.a8, alpha, (aid, base))
                self.assertEqual((r.soft.r, r.soft.g, r.soft.b), (r.color.r, r.color.g, r.color.b))

    def test_signal_and_defaults(self):
        self.assertEqual(self.resolve("signal", "graphite").color, C("#ffb547"))       # amber by night
        self.assertEqual(self.resolve("signal", "paper").color, C("#2b3af7"))          # ink blue by day
        self.assertEqual(self.resolve(None, "graphite").id, "signal")                   # accentDefault
        self.assertEqual(self.resolve(None, "phosphor").id, "phosphor")
        r = self.resolve("nonsense", "paper")
        self.assertEqual((r.id, r.fallback), ("signal", "unknown accent: nonsense"))

    def test_custom_is_adjusted_per_base_and_reported(self):
        for base in BASES:
            r = self.resolve("#3a0ca3", base)                   # dark indigo: fine on paper, too dark at night
            self.assertEqual((r.id, r.custom), ("custom", "#3a0ca3"))
            self.assertEqual(r.adjusted, self.themes[base].mode == "dark", base)
            self.assertGreaterEqual(r.contrast, AC.MIN_CONTRAST)
            self.assertEqual(r.requested, C("#3a0ca3"))
        self.assertEqual(self.resolve("#f5cf52", "graphite").clash, "warn")          # looks like a warning
        self.assertIsNone(self.resolve("#bba4ff", "graphite").clash)

    def test_gnome_accent_names(self):
        want = {("signal", "graphite"): "yellow", ("signal", "paper"): "blue", ("amber", "paper"): "orange",
                ("ink", "graphite"): "blue", ("phosphor", "graphite"): "green", ("ice", "graphite"): "teal",
                ("ice", "paper"): "teal", ("lilac", "graphite"): "purple", ("lilac", "paper"): "purple",
                ("rose", "graphite"): "pink", ("rose", "paper"): "pink", ("mono", "graphite"): "slate",
                ("mono", "paper"): "slate"}
        for (aid, base), name in want.items():
            self.assertEqual(self.resolve(aid, base).gnome, name, (aid, base))

    def test_listing_shape(self):
        rows = AC.listing(self.cat, "lilac")
        self.assertEqual([r["id"] for r in rows][-1], "custom")
        lilac = next(r for r in rows if r["id"] == "lilac")
        self.assertEqual({k: lilac[k] for k in ("dark", "light", "current")}, {"dark": "#bba4ff", "light": "#6a3fd6", "current": True})
        self.assertEqual(lilac["ink"], {"dark": "#141518", "light": "#ffffff"})
        self.assertEqual(lilac["name"], {"en": "Lilac", "ru": "Сирень"})
        custom = AC.listing(self.cat, "custom", "#3a0ca3", {"dark": C("#141518"), "light": C("#f8f7f3")})[-1]
        self.assertTrue(custom["current"])
        self.assertEqual(custom["light"], "#3a0ca3")
        self.assertNotEqual(custom["dark"], "#3a0ca3")


class TemplatesEveryAccentTest(SandboxTest):
    """Every template × every accent (and a custom one) × every base theme."""

    SENTINEL = "#ff00ff"      # a custom accent no theme token uses: wherever it shows up, the accent is used

    def render_all(self, base, accent):
        ctx = self.sb.ctx()
        theme = A.load_theme(ctx.paths, base)
        acc = A.resolve_accent(theme, {"theme": {"accent": accent}}, ctx.paths)
        vars_ = A.template_context(theme, ctx.paths, acc)
        return theme, acc, {t.id: A.render_target(t, vars_, ctx.paths) for t in A.load_manifest(ctx.paths)}

    def test_every_accent_every_base(self):
        cat = AC.load_catalog(self.sb.ctx().paths)
        for base in BASES:
            for accent in list(cat.accents) + [self.SENTINEL, "#3a0ca3"]:
                theme, acc, out = self.render_all(base, accent)
                a, ink, c = acc.color, acc.ink, theme.colors
                where = f"{base}/{accent}"
                for tid, text in out.items():
                    self.assertNotIn("{{", text, f"{where}/{tid}")
                h = out["hyprland"]
                # DESIGN §11: borders and group tabs are neutral; the accent only shows on hover glyphs
                self.assertIn(f"col.active_border = rgb({c['lineStrong'].strip})", h, where)
                for line in h.splitlines():
                    if "border" in line or "locked" in line:
                        self.assertNotIn(f"rgb({a.strip})", line, f"{where}: {line}")
                self.assertIn(f"col.inactive_border = rgb({c['line'].strip})", h, where)
                self.assertEqual(h.count(f", rgb({a.strip})\n"), 3, where)                   # hyprbars glyphs
                self.assertIn("icon_on_hover = true", h)
                self.assertIn(f"$svoya_warn = rgb({c['warn'].strip})", h)
                self.assertIn(f"$svoya_accentStrong = rgb({acc.strong.strip})", h)
                k = out["kitty"]
                self.assertRegex(k, rf"(?m)^cursor\s+{a.hex}$")
                self.assertRegex(k, rf"(?m)^cursor_text_color\s+{ink.hex}$")
                self.assertRegex(k, rf"(?m)^url_color\s+{a.hex}$")
                self.assertRegex(k, rf"(?m)^bell_border_color\s+{c['warn'].hex}$")
                self.assertRegex(k, rf"(?m)^color1\s+{c['bad'].hex}$")
                self.assertRegex(k, rf"(?m)^color3\s+{c['warn'].hex}$")
                self.assertEqual(len(re.findall(r"(?m)^color\d+\s+#[0-9a-f]{6}$", k)), 16)
                foot = configparser.ConfigParser(interpolation=None, strict=False)
                foot.read_string("[main]\n" + out["foot"])
                self.assertEqual(foot["colors"]["cursor"], f"{ink.strip} {a.strip}")
                self.assertEqual(foot["colors"]["urls"], a.strip)
                self.assertEqual(foot["colors"]["regular3"], c["warn"].strip)
                for tid in ("gtk3", "gtk4"):
                    g = out[tid]
                    self.assertIn(f"@define-color accent_bg_color {a.hex};", g)
                    self.assertIn(f"@define-color accent_fg_color {ink.hex};", g)
                    self.assertIn(f"@define-color warning_color {c['warn'].hex};", g)
                    self.assertIn(f"@define-color error_color {c['bad'].hex};", g)
                    self.assertIn(f"@define-color warning_fg_color {c['warn'].ink().hex};", g)
                    self.assertEqual(g.count("{"), g.count("}"))
                cp = configparser.ConfigParser(interpolation=None)
                cp.read_string(out["qt6ct-colors"])
                roles = [x.strip() for x in cp["ColorScheme"]["active_colors"].split(",")]
                self.assertEqual(len(roles), 22)
                self.assertEqual((roles[12], roles[13], roles[21]), (a.hexa, ink.hexa, a.hexa))  # Highlight, HighlightedText, Accent
                fz = configparser.ConfigParser(interpolation=None, strict=False)
                fz.read_string("[main]\n" + out["fuzzel"])
                self.assertEqual(fz["colors"]["prompt"], a.stripa)
                self.assertEqual(fz["colors"]["border"], c["lineStrong"].stripa)
                self.assertIn(f'theme[temp_mid]="{c["warn"].hex}"', out["btop-theme"])
                self.assertIn(f'theme[temp_end]="{c["bad"].hex}"', out["btop-theme"])
                self.assertIn(f'theme[hi_fg]="{a.hex}"', out["btop-theme"])
                ff = json.loads("\n".join(ln for ln in out["fastfetch"].splitlines() if not ln.lstrip().startswith("//")))
                self.assertEqual(ff["logo"]["color"]["2"], a.ansi)
                self.assertEqual(ff["display"]["color"]["title"], c["text"].ansi)          # headings never accent

    def test_sentinel_accent_never_in_semantic_slots(self):
        for base in BASES:
            theme, acc, out = self.render_all(base, self.SENTINEL)
            if theme.mode == "dark":
                self.assertEqual(acc.color, C(self.SENTINEL))
            s = acc.color.strip                            # on Paper the magenta is darkened for contrast
            semantic = re.compile(r"(warn|warning|error|destructive|bad|success|temp_|bell|color[0-9]|regular|bright|"
                                  r"\$svoya_(ok|warn|bad|cloud))", re.I)
            for tid, text in out.items():
                for ln in text.splitlines():
                    if semantic.search(ln) and not ln.lstrip().startswith(("#", "//", "/*")):
                        self.assertNotIn(s, ln.lower(), f"{base}/{tid}: {ln}")
            pal = terminal_palette(A.with_accent(theme, acc).colors, theme.mode)
            self.assertNotIn(acc.color, pal.values())

    def test_theme_json_accent_keys(self):
        ctx = self.sb.ctx()
        now = dt.datetime(2026, 9, 25, tzinfo=dt.timezone.utc)
        g = A.load_theme(ctx.paths, "graphite")
        tj = A.theme_json(g, "graphite", now, A.resolve_accent(g, {"theme": {"accent": "lilac"}}, ctx.paths))
        self.assertEqual({k: tj[k] for k in ("accent", "accentSoft", "accentInk", "accentStrong")},
                         {"accent": "#ffbba4ff", "accentSoft": "#24bba4ff", "accentInk": "#ff141518",
                          "accentStrong": "#ff" + AC.strong_variant(C("#bba4ff"), "dark").strip})
        self.assertEqual({k: tj[k] for k in ("accentId", "accentNameEn", "accentNameRu", "accentCustom", "accentAdjusted")},
                         {"accentId": "lilac", "accentNameEn": "Lilac", "accentNameRu": "Сирень", "accentCustom": None,
                          "accentAdjusted": False})
        self.assertEqual(tj["warn"], "#fff5cf52")
        self.assertTrue(all(not isinstance(v, (dict, list)) for v in tj.values()))
        p = A.load_theme(ctx.paths, "paper")
        tj = A.theme_json(p, "paper", now, A.resolve_accent(p, {"theme": {"accent": "#ffff00"}}, ctx.paths))
        self.assertEqual((tj["accentId"], tj["accentCustom"], tj["accentAdjusted"]), ("custom", "#ffff00", True))
        self.assertGreaterEqual(tj["accentContrast"], 4.5)
        self.assertEqual(tj["accentSoft"][:3], "#17")                                     # 9 % on light bases

    def test_apply_sets_gnome_accent_only_when_it_changes(self):
        r = FakeRunner({"gsettings writable org.gnome.desktop.interface accent-color": "true\n"}, available={"gsettings"})
        ctx = self.sb.ctx(r, WAYLAND_DISPLAY="wayland-1")
        rep = A.apply_theme(ctx, "graphite", cfg={"theme": {"accent": "rose"}, "location": {}})
        self.assertTrue(r.called("gsettings", "set", "org.gnome.desktop.interface", "accent-color", "pink"))
        self.assertEqual(rep["accent"]["id"], "rose")
        r2 = FakeRunner({"gsettings writable org.gnome.desktop.interface accent-color": "true\n"}, available={"gsettings"})
        A.apply_theme(self.sb.ctx(r2, WAYLAND_DISPLAY="wayland-1"), "graphite", cfg={"theme": {"accent": "rose"}, "location": {}})
        self.assertFalse(r2.called("gsettings", "set"))
        r3 = FakeRunner({"gsettings writable org.gnome.desktop.interface accent-color": "true\n"}, available={"gsettings"})
        A.apply_theme(self.sb.ctx(r3, WAYLAND_DISPLAY="wayland-1"), "graphite", cfg={"theme": {"accent": "ice"}, "location": {}})
        self.assertTrue(r3.called("gsettings", "set", "org.gnome.desktop.interface", "accent-color", "teal"))
        # no such key (GNOME < 47): nothing is set
        r4 = FakeRunner(available={"gsettings"})
        A.apply_theme(self.sb.ctx(r4, WAYLAND_DISPLAY="wayland-1"), "graphite", cfg={"theme": {"accent": "mono"}, "location": {}})
        self.assertFalse(r4.called("gsettings", "set", "org.gnome.desktop.interface", "accent-color"))

    def test_missing_accents_file_keeps_theme_tokens(self):
        themes = self.sb.dir / "themes"
        themes.mkdir()
        src = A.load_theme(CHECKOUT, "graphite").path
        (themes / "graphite.toml").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        ctx = self.sb.ctx(SVOYA_THEMES_DIR=str(themes))
        g = A.load_theme(ctx.paths, "graphite")
        acc = A.resolve_accent(g, {"theme": {}}, ctx.paths)
        self.assertEqual((acc.id, acc.color), ("theme", g.colors["accent"]))
        acc = A.resolve_accent(g, {"theme": {"accent": "#3a0ca3"}}, ctx.paths)      # custom still works
        self.assertEqual(acc.id, "custom")


if __name__ == "__main__":
    unittest.main()
