# SPDX-License-Identifier: Apache-2.0
import unittest

from jackson.config import DEFAULTS, build_config, deep_merge
from jackson.providers.base import Health, Provider
from jackson.router import HealthCache, RouteError, Router, order_local_models
from jackson.spend import SpendLedger
from tests.fakes import rmtree, short_tmpdir


class Stub(Provider):
    def __init__(self, cfg, healthy=True, models=None, key=None):
        super().__init__(cfg, key)
        self.healthy = healthy
        self.models = models or []
        self.checks = 0

    def stream(self, req, cancel):  # pragma: no cover - not used here
        raise NotImplementedError

    def health(self, timeout=1.0):
        self.checks += 1
        return Health(self.healthy, "ok" if self.healthy else "connection refused", list(self.models))


def make_router(root, route=None, local_ok=True, local_models=("qwen3.5-4b", "qwen3.5-14b"), keys=("anthropic",),
                spent=0.0):
    data = deep_merge(DEFAULTS, {"route": route or {}})
    cfg = build_config(data)
    providers = {}
    for name, pc in cfg.providers.items():
        if pc.local:
            providers[name] = Stub(pc, healthy=local_ok and name == "local", models=list(local_models))
        else:
            providers[name] = Stub(pc, key="sk" if name in keys else None)
    spend = SpendLedger(root / "spend.json")
    if spent:
        spend.add(spent, True)
    return Router(cfg, providers, HealthCache(providers), spend), providers


class RouterTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()

    def tearDown(self):
        rmtree(self.root)

    def test_local_first_with_human_reason(self):
        r, _ = make_router(self.root)
        d = r.decide("привет, как дела?", lang="ru")
        self.assertEqual((d.chosen.provider, d.chosen.model, d.chosen.local), ("local", "qwen3.5-4b", True))
        self.assertIn("данные не покидают компьютер", d.reason)
        ev = d.event()
        self.assertEqual(set(ev) >= {"model", "provider", "local", "reason"}, True)

    def test_code_prefers_bigger_local_model(self):
        r, _ = make_router(self.root)
        d = r.decide("почему падает этот python скрипт? Traceback ...", lang="ru")
        self.assertEqual(d.task, "code")
        self.assertEqual(d.chosen.model, "qwen3.5-14b")
        self.assertIn("код", d.reason)

    def test_local_only_policy_never_uses_cloud(self):
        r, _ = make_router(self.root, local_ok=False)
        with self.assertRaises(RouteError) as ctx:
            r.decide("привет", lang="ru")
        self.assertIn("только локально", ctx.exception.message)
        self.assertIn("sos models serve", ctx.exception.message)

    def test_asking_starts_the_local_server_when_a_model_is_installed(self):
        r, providers = make_router(self.root, local_ok=False)
        calls = []

        def start():
            calls.append(1)
            providers["local"].healthy = True          # the server came up
            return True

        r.local_starter, r.start_wait = start, 2.0
        d = r.decide("привет", lang="ru")
        self.assertEqual((d.chosen.provider, d.chosen.local), ("local", True))
        self.assertEqual(len(calls), 1)

    def test_no_installed_model_says_how_to_get_one(self):
        r, _ = make_router(self.root, local_ok=False)
        r.local_starter = lambda: False                # nothing to start: no model in /srv/ai
        r.local_installed = lambda: False
        with self.assertRaises(RouteError) as ctx:
            r.decide("привет", lang="ru")
        self.assertIn("пока нет своей модели", ctx.exception.message)
        self.assertIn("sos модели подобрать", ctx.exception.message)

    def test_policy_any_falls_back_to_cloud_when_local_down(self):
        r, _ = make_router(self.root, route={"policy": "any"}, local_ok=False)
        d = r.decide("привет", lang="ru")
        self.assertEqual(d.chosen.provider, "anthropic")
        self.assertFalse(d.chosen.local)
        self.assertIn("локальная модель недоступна", d.reason)

    def test_explicit_cloud_overrides_policy_but_not_offline(self):
        r, _ = make_router(self.root)
        d = r.decide("привет", route="cloud", lang="ru")
        self.assertEqual(d.chosen.provider, "anthropic")
        self.assertIn("по твоему выбору", d.reason)
        r2, _ = make_router(self.root, route={"offline": True})
        with self.assertRaises(RouteError) as ctx:
            r2.decide("привет", route="cloud", lang="ru")
        self.assertIn("офлайн", ctx.exception.message)

    def test_explicit_model_and_local(self):
        r, _ = make_router(self.root, route={"policy": "any"})
        d = r.decide("hi", route="anthropic/claude-opus-5-5", lang="en")
        self.assertEqual((d.chosen.provider, d.chosen.model), ("anthropic", "claude-opus-5-5"))
        d2 = r.decide("hi", route="local", lang="en")
        self.assertTrue(d2.chosen.local)
        self.assertIn("as you asked", d2.reason)

    def test_eu_policy_uses_only_eu_cloud(self):
        r, _ = make_router(self.root, route={"policy": "eu"}, local_ok=False, keys=("anthropic", "mistral"))
        d = r.decide("hello", lang="en")
        self.assertEqual(d.chosen.provider, "mistral")
        r2, _ = make_router(self.root, route={"policy": "eu"}, local_ok=False, keys=("anthropic",))
        with self.assertRaises(RouteError):
            r2.decide("hello", lang="en")

    def test_vision_needs_a_vision_model(self):
        r, _ = make_router(self.root, route={"policy": "any"})
        d = r.decide("что на скриншоте?", {"screenshot": "/tmp/x.png"}, lang="ru")
        self.assertEqual(d.task, "vision")
        self.assertFalse(d.chosen.local)
        self.assertIn("зрени", d.reason)
        r2, _ = make_router(self.root, route={"policy": "any"}, local_models=("qwen3.5-vl-7b",))
        self.assertTrue(r2.decide("что тут?", {"screenshot": "/tmp/x.png"}).chosen.local)

    def test_long_context_goes_to_a_big_window(self):
        r, _ = make_router(self.root, route={"policy": "any"})
        d = r.decide("summarize", {"selection": "слово " * 60_000}, lang="ru")
        self.assertEqual(d.task, "long")
        self.assertFalse(d.chosen.local)

    def test_budget_exhausted_keeps_local(self):
        r, _ = make_router(self.root, route={"policy": "any", "daily_budget_eur": 0.10}, local_ok=False, spent=0.10)
        with self.assertRaises(RouteError) as ctx:
            r.decide("hi", lang="ru")
        self.assertIn("бюджет", ctx.exception.message)
        r2, _ = make_router(self.root, route={"policy": "any", "daily_budget_eur": 0.10}, spent=0.10)
        d = r2.decide("hi", lang="ru")
        self.assertTrue(d.chosen.local)

    def test_cloud_without_key_is_unavailable(self):
        r, _ = make_router(self.root, route={"policy": "any"}, local_ok=False, keys=())
        with self.assertRaises(RouteError) as ctx:
            r.decide("hi", route="cloud", lang="ru")
        self.assertIn("secret-tool store", ctx.exception.message)

    def test_health_is_cached(self):
        r, providers = make_router(self.root)
        r.decide("a")
        r.decide("b")
        self.assertEqual(providers["local"].checks, 1)

    def test_circuit_breaker(self):
        r, _ = make_router(self.root, route={"policy": "any"}, local_ok=False, keys=("anthropic", "gemini"))
        r.health.mark_failed("anthropic", "HTTP 529")
        self.assertEqual(r.decide("hi").chosen.provider, "gemini")

    def test_local_model_ordering(self):
        from jackson.config import ProviderConfig
        pc = ProviderConfig("local", local=True)
        models = ["bge-m3-embed", "qwen3.5-1.5b", "qwen3.5-4b", "qwen3.5-14b", "qwen3.5-72b"]
        self.assertEqual(order_local_models(models, "chat", pc)[0], "qwen3.5-4b")
        self.assertEqual(order_local_models(models, "code", pc)[0], "qwen3.5-14b")
        self.assertNotIn("bge-m3-embed", order_local_models(models, "chat", pc))


if __name__ == "__main__":
    unittest.main()
