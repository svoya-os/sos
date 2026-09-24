# SPDX-License-Identifier: Apache-2.0
"""Pick a provider/model for each turn.

Precedence: explicit route > privacy policy > task class > budget > availability.
Local models come first by default. Every decision carries a human reason that the
shell shows in the route chip (``локально: быстрый ответ, данные не покидают компьютер``).
"""

from __future__ import annotations

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import Any, Iterable

from .config import Config, ProviderConfig
from .i18n import fmt_cost, fmt_number, t
from .providers import Health, Provider, price_for
from .spend import SpendLedger

CODE_RE = re.compile(
    r"```|\b(def|class|import|function|const|return|SELECT|INSERT|#include|fn|impl|async|await)\b"
    r"|Traceback|Exception|stack ?trace|segfault|\.(py|js|ts|tsx|rs|go|c|cpp|h|java|kt|sh|toml|ya?ml|json|qml)\b"
    r"|\b(код\w*|функци\w*|скрипт\w*|баг\w*|компил\w*|рефактор\w*|python|javascript|typescript|rust|golang"
    r"|bash|regex|регулярк\w*|git|commit|pull request|unit ?test\w*|тест\w* для)\b",
    re.IGNORECASE)
NON_CHAT_RE = re.compile(r"embed|rerank|whisper|tts|bge-|e5-|clip|mmproj|parakeet|gigaam|silero|piper",
                         re.IGNORECASE)
SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*b(?![a-z])", re.IGNORECASE)
LONG_TOKENS = 24_000
EXPECTED_OUTPUT_TOKENS = 1_000


@dataclass
class Candidate:
    provider: str
    model: str
    local: bool
    region: str
    label: str

    @property
    def id(self) -> str:
        return f"{self.provider}/{self.model}"


@dataclass
class RouteDecision:
    chosen: Candidate
    fallbacks: list[Candidate]
    reason: str
    task: str
    explicit: str | None = None
    est_tokens: int = 0

    def event(self) -> dict[str, Any]:
        return {"model": self.chosen.model, "provider": self.chosen.provider, "local": self.chosen.local,
                "reason": self.reason, "task": self.task, "label": self.chosen.label}


class RouteError(Exception):
    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable


class HealthCache:
    """Cached health checks: local providers are probed, cloud providers are circuit-broken."""

    def __init__(self, providers: dict[str, Provider], ttl_ok: float = 15.0, ttl_fail: float = 3.0,
                 breaker: float = 60.0) -> None:
        self.providers = providers
        self.ttl_ok, self.ttl_fail, self.breaker = ttl_ok, ttl_fail, breaker
        self._cache: dict[str, tuple[float, Health]] = {}
        self._broken: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def get(self, name: str, timeout: float = 0.8, max_age: float | None = None) -> Health:
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(name)
        if hit is not None:
            age = now - hit[0]
            limit = max_age if max_age is not None else (self.ttl_ok if hit[1].ok else self.ttl_fail)
            if age <= limit:
                return hit[1]
        prov = self.providers.get(name)
        if prov is None:
            return Health(False, "unknown provider")
        try:
            health = prov.health(timeout=timeout)
        except Exception as exc:  # a health check must never break routing
            health = Health(False, str(exc))
        with self._lock:
            self._cache[name] = (time.monotonic(), health)
        return health

    def cached(self, name: str) -> Health | None:
        with self._lock:
            hit = self._cache.get(name)
        return hit[1] if hit else None

    def refresh(self, names: Iterable[str], timeout: float = 0.8) -> dict[str, Health]:
        names = list(names)
        if not names:
            return {}
        with ThreadPoolExecutor(max_workers=min(8, len(names))) as pool:
            results = pool.map(lambda n: (n, self.get(n, timeout=timeout, max_age=0)), names)
            return dict(results)

    def mark_failed(self, name: str, detail: str) -> None:
        with self._lock:
            self._broken[name] = (time.monotonic(), detail)
            self._cache.pop(name, None)

    def mark_ok(self, name: str) -> None:
        with self._lock:
            self._broken.pop(name, None)

    def broken(self, name: str) -> str | None:
        with self._lock:
            hit = self._broken.get(name)
            if hit is None:
                return None
            if time.monotonic() - hit[0] > self.breaker:
                del self._broken[name]
                return None
            return hit[1]


def _model_size(name: str) -> float | None:
    sizes = [float(m) for m in SIZE_RE.findall(name)]
    return max(sizes) if sizes else None


def order_local_models(models: list[str], task: str, pcfg: ProviderConfig) -> list[str]:
    usable = [m for m in models if not NON_CHAT_RE.search(m)]
    if task == "vision":
        usable = [m for m in usable if pcfg.has_vision(m)]

    def key(m: str) -> tuple[int, float]:
        size = _model_size(m)
        if size is None:
            return (1, 0.0)
        if task in ("code", "long"):
            return (0, -size if size <= 40 else size)  # biggest that is still practical
        return (0, size if size >= 3 else 100 + size)  # smallest that is still good

    return sorted(usable, key=key)


class Router:
    def __init__(self, config: Config, providers: dict[str, Provider], health: HealthCache,
                 spend: SpendLedger, has_key: dict[str, bool] | None = None) -> None:
        self.config = config
        self.providers = providers
        self.health = health
        self.spend = spend
        self.has_key = has_key or {}

    # ------------------------------------------------------------------
    def classify(self, text: str, context: dict[str, Any] | None = None, has_images: bool = False,
                 est_tokens: int = 0) -> str:
        context = context or {}
        if has_images or context.get("screenshot"):
            return "vision"
        if est_tokens > LONG_TOKENS:
            return "long"
        probe = text + "\n" + str(context.get("selection") or "")[:4000]
        if CODE_RE.search(probe):
            return "code"
        return "chat"

    def provider_ready(self, name: str) -> tuple[bool, str]:
        prov = self.providers.get(name)
        if prov is None or not prov.cfg.enabled:
            return False, "disabled"
        if prov.cfg.needs_key and not self.has_key.get(name):
            return False, "no key"
        if prov.cfg.local:
            h = self.health.get(name)
            return (h.ok, "loading" if h.loading else h.detail)
        broken = self.health.broken(name)
        if broken:
            return False, broken
        return True, "ok"

    def models_of(self, name: str, task: str) -> list[str]:
        prov = self.providers[name]
        models = list(prov.cfg.models)
        if prov.cfg.local:
            h = self.health.cached(name)
            discovered = h.models if h and h.ok else []
            models = models + [m for m in discovered if m not in models]
            return order_local_models(models, task, prov.cfg)
        return models

    def _ordered_pairs(self, task: str) -> list[Candidate]:
        prefs = self.config.route.task.get(task) or []
        pairs: list[Candidate] = []
        seen: set[str] = set()

        def add(p: ProviderConfig, model: str) -> None:
            cid = f"{p.name}/{model}"
            if cid not in seen:
                seen.add(cid)
                pairs.append(Candidate(p.name, model, p.local, p.region, p.display))

        for pattern in prefs:
            pname, _, mpat = pattern.partition("/")
            prov = self.providers.get(pname)
            if prov is None:
                continue
            for model in self.models_of(pname, task):
                if fnmatchcase(model, mpat or "*"):
                    add(prov.cfg, model)
        for name, prov in self.providers.items():  # anything not mentioned comes after, local first
            for model in self.models_of(name, task):
                add(prov.cfg, model)
        if self.config.route.prefer_local:
            pairs.sort(key=lambda c: 0 if c.local else 1)  # stable: keeps preference order in each group
        return pairs

    # ------------------------------------------------------------------
    def decide(self, text: str, context: dict[str, Any] | None = None, route: str | None = None,
               lang: str = "ru", history_chars: int = 0, has_images: bool = False) -> RouteDecision:
        context = context or {}
        rc = self.config.route
        route = (route or rc.default or "auto").strip()
        chars = len(text) + len(str(context.get("selection") or "")) + len(str(context.get("clipboard") or "")) \
            + history_chars
        est = int(chars / 3.5) + 3000  # + system prompt and tool schemas
        task = self.classify(text, context, has_images, est)

        # Health of local providers first (cached; the daemon keeps it warm).
        local_names = [n for n, p in self.providers.items() if p.cfg.local and p.cfg.enabled]
        local_status = {n: self.provider_ready(n) for n in local_names}
        pairs = self._ordered_pairs(task)

        explicit_model = route if "/" in route else None
        explicit = route if route in ("local", "cloud") or explicit_model else None
        if explicit_model:
            pname, _, model = explicit_model.partition("/")
            prov = self.providers.get(pname)
            if prov is None:
                raise RouteError(t("route.none", lang, why=f"unknown provider {pname!r}"), retryable=False)
            pairs = [Candidate(pname, model, prov.cfg.local, prov.cfg.region, prov.cfg.display)]
        elif route == "local":
            pairs = [c for c in pairs if c.local]
        elif route == "cloud":
            pairs = [c for c in pairs if not c.local]
        explicit_cloud = (route == "cloud") or bool(explicit_model and not pairs[0].local)

        # Privacy policy (an explicit per-turn choice overrides it, the offline switch does not).
        if rc.offline:
            if explicit_cloud:
                raise RouteError(t("route.none", lang, why=t("route.why.offline", lang)), retryable=False)
            pairs = [c for c in pairs if c.local]
        elif not explicit_cloud:
            if rc.policy == "local-only":
                pairs = [c for c in pairs if c.local]
            elif rc.policy == "eu":
                pairs = [c for c in pairs if c.local or c.region == "eu"]

        # Task class: capabilities.
        capable: list[Candidate] = []
        for c in pairs:
            pcfg = self.providers[c.provider].cfg
            if task == "vision" and not pcfg.has_vision(c.model):
                continue
            if task == "long" and pcfg.context_for(c.model) < est * 1.2:
                continue
            capable.append(c)
        dropped_capability = bool(pairs) and not capable
        local_capable = any(c.local for c in capable)

        # Budget.
        budget = rc.daily_budget_eur
        spent = self.spend.today()["eur"]
        over_budget = False
        affordable: list[Candidate] = []
        for c in capable:
            if not c.local and budget is not None:
                (p_in, p_out), _ = price_for(self.config, c.provider, c.model, c.local)
                estimate = (est * p_in + EXPECTED_OUTPUT_TOKENS * p_out) / 1_000_000
                if spent + estimate > budget:
                    over_budget = True
                    continue
            affordable.append(c)

        # Availability.
        available: list[Candidate] = []
        ready_cache: dict[str, tuple[bool, str]] = dict(local_status)
        for c in affordable:
            if c.provider not in ready_cache:
                ready_cache[c.provider] = self.provider_ready(c.provider)
            if ready_cache[c.provider][0]:
                available.append(c)

        local_detail = "; ".join(f"{self.providers[n].cfg.display}: {why}" for n, (ok, why) in local_status.items()
                                 if not ok) or "—"
        if not available:
            raise RouteError(self._why_none(lang, task, explicit_cloud, over_budget, dropped_capability,
                                            local_detail, pairs, ready_cache))

        chosen = available[0]
        reason = self._reason(lang, chosen, task, explicit, explicit_cloud, over_budget, local_capable,
                              local_status, est)
        return RouteDecision(chosen, available[1:], reason, task, explicit, est)

    # ------------------------------------------------------------------
    def _reason(self, lang: str, c: Candidate, task: str, explicit: str | None, explicit_cloud: bool,
                over_budget: bool, local_capable: bool, local_status: dict[str, tuple[bool, str]],
                est: int) -> str:
        if c.local:
            if explicit == "local":
                return t("route.local.explicit", lang)
            if over_budget:
                return t("route.local.budget", lang, budget=fmt_cost(self.config.route.daily_budget_eur, lang))
            if task == "code":
                return t("route.local.code", lang)
            if task == "vision":
                return t("route.local.vision", lang)
            if self.config.route.policy == "local-only" or self.config.route.offline:
                return t("route.local.policy", lang)
            return t("route.local.fast", lang)
        if explicit_cloud:
            return t("route.cloud.explicit", lang, provider=c.label, model=c.model)
        if task == "vision" and not local_capable:
            return t("route.cloud.vision", lang, provider=c.label)
        if task == "long" and not local_capable:
            tokens = fmt_number(round(est, -3), lang)
            return t("route.cloud.long", lang, provider=c.label, tokens=tokens)
        down = [why for ok, why in local_status.values() if not ok]
        if down or not local_status:
            return t("route.cloud.unavailable", lang, provider=c.label,
                     why=", ".join(down) if down else ("нет локальных моделей" if lang == "ru" else "no local models"))
        return t("route.cloud.preferred", lang, provider=c.label, model=c.model, task=task)

    def _why_none(self, lang: str, task: str, explicit_cloud: bool, over_budget: bool,
                  dropped_capability: bool, local_detail: str, pairs: list[Candidate],
                  ready: dict[str, tuple[bool, str]]) -> str:
        rc = self.config.route
        if rc.offline:
            why = t("route.why.offline", lang)
        elif over_budget:
            why = t("route.why.budget", lang, budget=fmt_cost(rc.daily_budget_eur, lang))
        elif dropped_capability:
            why = t("route.why.capability", lang, task=task)
        elif explicit_cloud and not any(ok for n, (ok, _) in ready.items() if not self.providers[n].cfg.local):
            why = t("route.why.no_cloud", lang)
        elif rc.policy == "local-only" and not explicit_cloud:
            why = t("route.why.local_only", lang, detail=local_detail)
        else:
            details = [f"{self.providers[n].cfg.display}: {w}" for n, (ok, w) in ready.items() if not ok]
            if not details and not pairs:
                return t("route.none", lang, why=t("route.why.no_cloud", lang))
            why = t("route.why.generic", lang, detail="; ".join(details) or local_detail)
        return t("route.none", lang, why=why)

    # ------------------------------------------------------------------
    def model_table(self) -> list[dict[str, Any]]:
        """Configured and discovered models with availability (for `welcome` and `jackson models`)."""
        rows = []
        for name, prov in self.providers.items():
            ready, why = self.provider_ready(name) if prov.cfg.enabled else (False, "disabled")
            models = self.models_of(name, "chat") if prov.cfg.local else list(prov.cfg.models)
            if prov.cfg.local and not models:
                rows.append({"id": f"{name}/*", "provider": name, "model": "", "local": True,
                             "available": False, "detail": why, "label": prov.cfg.display})
            for m in models:
                rows.append({"id": f"{name}/{m}", "provider": name, "model": m, "local": prov.cfg.local,
                             "available": ready, "detail": why, "label": prov.cfg.display,
                             "region": prov.cfg.region})
        return rows
