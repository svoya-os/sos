# SPDX-License-Identifier: Apache-2.0
import os
import tomllib
import unittest
from pathlib import Path

from jackson.config import ProviderConfig, load_config, set_toml_value
from jackson.i18n import fmt_bytes, fmt_cost, fmt_latency, fmt_number, fmt_tokens, meta_line, plural_ru
from jackson.keys import KeyStore
from jackson.paths import Paths
from jackson.persona import persona_text, style_fast, system_prompt
from jackson.runner import RunResult
from jackson.sandbox import Sandbox
from tests.fakes import FakeRunner, rmtree, short_tmpdir


class FormattingTest(unittest.TestCase):
    def test_meta_line_matches_design(self) -> None:
        self.assertEqual(meta_line(800, 312, 0.0, False, [], "ru"),
                         "0,8 с · 312 токенов · 0 € · данные не покидали компьютер")
        self.assertEqual(meta_line(1234, 1, 0.0042, True, ["Anthropic"], "en"),
                         "1.2 s · 1 token · €0.0042 · data sent to: Anthropic")

    def test_russian_plurals_and_numbers(self) -> None:
        self.assertEqual([plural_ru(n, "токен", "токена", "токенов") for n in (1, 2, 5, 11, 21, 22, 112)],
                         ["токен", "токена", "токенов", "токенов", "токен", "токена", "токенов"])
        self.assertEqual(fmt_tokens(12345, "ru"), "12 345 токенов")
        self.assertEqual(fmt_number(1000, "ru"), "1000")
        self.assertEqual(fmt_number(11.2, "ru", 1), "11,2")
        self.assertEqual(fmt_bytes(11.2 * 1024 ** 3, "ru"), "11,2 ГБ")

    def test_latency_and_cost(self) -> None:
        self.assertEqual(fmt_latency(30, "ru"), "30 мс")
        self.assertEqual(fmt_latency(12_400, "ru"), "12 с")
        self.assertEqual(fmt_latency(65_000, "en"), "1 min 5 s")
        self.assertEqual(fmt_cost(0, "ru"), "0 €")
        self.assertEqual(fmt_cost(0.25, "ru"), "0,25 €")
        self.assertEqual(fmt_cost(0.002, "ru", estimated=True), "≈0,002 €")


class ConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = short_tmpdir()
        self.paths = Paths.for_root(self.root)

    def tearDown(self) -> None:
        rmtree(self.root)

    def test_defaults(self) -> None:
        cfg = load_config(self.paths)
        self.assertEqual(cfg.persona, "kent")
        self.assertEqual(cfg.humor, 1)
        self.assertEqual(cfg.route.policy, "local-only")
        self.assertEqual(cfg.address, "ty")
        self.assertIn("local", cfg.providers)
        self.assertTrue(cfg.providers["local"].local)
        self.assertEqual(cfg.providers["anthropic"].region, "us")
        self.assertIn("anthropic/claude-sonnet-5", cfg.pricing)
        self.assertEqual(cfg.warnings, [])

    def test_user_toml_overrides_and_warnings(self) -> None:
        self.paths.config_dir.mkdir(parents=True)
        self.paths.config_file.write_text(
            'language = "en"\npersona = "pirate"\nhumor = 7\nbogus = 1\n'
            '[route]\npolicy = "eu"\ndaily_budget_eur = 0.5\n'
            '[providers.local]\nbase_url = "http://127.0.0.1:9999/v1"\n'
            '[pricing]\n"anthropic/claude-sonnet-5" = [1.0, 2.0]\n'
            '[mcp.servers.files]\ncommand = ["mcp-files", "~/Documents"]\ntier = 1\n', encoding="utf-8")
        cfg = load_config(self.paths)
        self.assertEqual(cfg.language, "en")
        self.assertEqual(cfg.persona, "pirate")
        self.assertEqual(cfg.humor, 1)  # out of range → default
        self.assertEqual(cfg.route.policy, "eu")
        self.assertEqual(cfg.route.daily_budget_eur, 0.5)
        self.assertEqual(cfg.providers["local"].base_url, "http://127.0.0.1:9999/v1")
        self.assertEqual(cfg.pricing["anthropic/claude-sonnet-5"], (1.0, 2.0))
        self.assertEqual(cfg.mcp_servers["files"].tier, 1)
        self.assertTrue(any("bogus" in w for w in cfg.warnings))

    def test_set_toml_value_keeps_comments(self) -> None:
        f = self.paths.config_file
        f.parent.mkdir(parents=True)
        f.write_text('# my settings\npersona = "sysop"  # nice\n\n[route]\n# who may see data\npolicy = "any"\n\n'
                     '[memory]\njournal = true\n', encoding="utf-8")
        set_toml_value(f, "route", "policy", "local-only")
        set_toml_value(f, "route", "offline", True)
        set_toml_value(f, "", "humor", 2)
        set_toml_value(f, "tools", "web_fetch", False)
        text = f.read_text(encoding="utf-8")
        self.assertIn("# my settings", text)
        self.assertIn("# who may see data", text)
        data = tomllib.loads(text)
        self.assertEqual(data["route"], {"policy": "local-only", "offline": True})
        self.assertEqual(data["humor"], 2)
        self.assertEqual(data["persona"], "sysop")
        self.assertEqual(data["memory"], {"journal": True})
        self.assertFalse(data["tools"]["web_fetch"])


class KeysTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = short_tmpdir()
        self.paths = Paths.for_root(self.root)
        self.pc = ProviderConfig(name="anthropic", needs_key=True, api_key_env="ANTHROPIC_API_KEY")

    def tearDown(self) -> None:
        rmtree(self.root)

    def test_keyring_first(self) -> None:
        runner = FakeRunner(self.paths, available={"secret-tool"})
        expected = ["secret-tool", "lookup", "service", "svoya", "provider", "anthropic"]
        runner.run = lambda argv, **kw: RunResult(0, "sk-from-keyring\n") if list(argv) == expected \
            else RunResult(1)  # type: ignore[method-assign]
        found = KeyStore(self.paths, runner, env={}).lookup(self.pc)
        self.assertEqual((found.key, found.source), ("sk-from-keyring", "keyring"))

    def test_secrets_env_fallback_warns_on_loose_mode(self) -> None:
        f = self.paths.secrets_file
        f.parent.mkdir(parents=True)
        f.write_text("# keys\nexport ANTHROPIC_API_KEY='sk-file'\n", encoding="utf-8")
        os.chmod(f, 0o644)
        store = KeyStore(self.paths, FakeRunner(self.paths, available=set()), env={})
        found = store.lookup(self.pc)
        self.assertEqual((found.key, found.source), ("sk-file", "secrets.env"))
        self.assertIn("chmod 600", found.warning or "")
        os.chmod(f, 0o600)
        store.refresh()
        self.assertIsNone(store.lookup(self.pc).warning)

    def test_env_fallback_and_missing(self) -> None:
        store = KeyStore(self.paths, FakeRunner(self.paths, available=set()), env={"ANTHROPIC_API_KEY": "sk-env"})
        self.assertEqual(store.lookup(self.pc).source, "env")
        empty = KeyStore(self.paths, FakeRunner(self.paths, available=set()), env={})
        self.assertFalse(empty.lookup(self.pc).found)


class PersonaTest(unittest.TestCase):
    def test_rules_identical_for_every_persona(self) -> None:
        base = None
        for persona in ("kent", "sysop", "dispatcher", "pirate"):
            prompt = system_prompt(lang="ru", persona=persona)
            rules = prompt.split("## Правила", 1)[1]
            self.assertIn("Не говори «готово»", rules)
            self.assertNotIn("демон", prompt.lower())
            base = base or rules
            self.assertEqual(rules, base)

    def test_humor_levels_and_fast_style(self) -> None:
        self.assertIn("без шуток", persona_text("kent", "ru", 0))
        self.assertIn("кентафурик", persona_text("kent", "ru", 1))
        self.assertIn("чуваааак", persona_text("kent", "ru", 1))
        self.assertIn("в большинстве ответов", persona_text("kent", "ru", 1))
        self.assertEqual(style_fast("kent", "ru", "Громкость 50%.", ok=False, humor=2), "Громкость 50%.")
        self.assertEqual(style_fast("kent", "ru", "Громкость 50%.", ok=True, humor=0), "Громкость 50%.")
        flavored = [style_fast("kent", "ru", "ok", True, 2, seed=str(i)) for i in range(60)]
        self.assertTrue(any(f != "ok" for f in flavored))
        self.assertEqual(sum(f != "ok" for f in flavored), 60)   # humor 2: every reply gets a word
        some = [style_fast("kent", "ru", "ok", True, 1, seed=str(i)) for i in range(60)]
        self.assertTrue(15 < sum(f != "ok" for f in some) < 45)    # humor 1 (default): about half
        self.assertTrue(style_fast("dispatcher", "ru", "Готово", True).startswith("✓"))


class SandboxTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = short_tmpdir()
        self.paths = Paths.for_root(self.root)
        (self.paths.home / ".ssh").mkdir(parents=True)
        (self.paths.home / ".netrc").write_text("x")
        (self.paths.home / "proj").mkdir()

    def tearDown(self) -> None:
        rmtree(self.root)

    def test_bwrap_layout(self) -> None:
        sb = Sandbox(self.paths, FakeRunner(self.paths, available={"bwrap"}))
        argv = sb.wrap(["bash", "-c", "ls"], rw=[self.paths.home / "proj"], network=False,
                       cwd=self.paths.home / "proj")
        joined = " ".join(argv)
        self.assertIn("--unshare-all", argv)
        self.assertNotIn("--share-net", argv)
        self.assertIn("--ro-bind / /", joined)
        self.assertIn(f"--tmpfs {self.paths.home / '.ssh'}", joined)
        self.assertIn(f"--ro-bind /dev/null {self.paths.home / '.netrc'}", joined)
        self.assertIn(f"--bind {self.paths.home / 'proj'} {self.paths.home / 'proj'}", joined)
        self.assertEqual(argv[-4:], ["--", "bash", "-c", "ls"])
        self.assertIn("--share-net", sb.wrap(["true"], network=True))
        # a writable path inside a hidden secret dir is never bound
        self.assertNotIn("--bind", sb.wrap(["true"], rw=[self.paths.home / ".ssh"]))


if __name__ == "__main__":
    unittest.main()
