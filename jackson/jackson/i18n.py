# SPDX-License-Identifier: Apache-2.0
"""Russian/English strings and locale-aware formatting (design/DESIGN.md §8).

Russian numbers use a decimal comma and a narrow no-break space between
thousand groups (``12 345``); four-digit numbers are not grouped.
"""

from __future__ import annotations

from typing import Iterable

NNBSP = " "  # narrow no-break space (thin space that never wraps)

LANGS = ("ru", "en")


def norm_lang(lang: str | None) -> str:
    lang = (lang or "ru").lower()[:2]
    return lang if lang in LANGS else "en"


# ---------------------------------------------------------------------------
# numbers

def fmt_number(value: float, lang: str, decimals: int = 0) -> str:
    lang = norm_lang(lang)
    text = f"{value:,.{decimals}f}"
    if lang == "ru":
        integer = text.split(".")[0].replace(",", "").lstrip("-")
        if len(integer) <= 4:  # Russian typography: 4-digit numbers stay ungrouped
            text = text.replace(",", "")
        text = text.replace(",", NNBSP).replace(".", ",")
    return text


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def fmt_tokens(n: int, lang: str) -> str:
    lang = norm_lang(lang)
    num = fmt_number(n, lang)
    if lang == "ru":
        return f"{num} {plural_ru(n, 'токен', 'токена', 'токенов')}"
    return f"{num} {'token' if n == 1 else 'tokens'}"


def fmt_latency(ms: float, lang: str) -> str:
    lang = norm_lang(lang)
    sec = max(0.0, ms / 1000.0)
    unit_s = "с" if lang == "ru" else "s"
    if sec < 10:
        return f"{fmt_number(sec, lang, 1)} {unit_s}"
    if sec < 60:
        return f"{int(round(sec))} {unit_s}"
    minutes, rest = divmod(int(round(sec)), 60)
    unit_m = "мин" if lang == "ru" else "min"
    return f"{minutes} {unit_m} {rest} {unit_s}" if rest else f"{minutes} {unit_m}"


def fmt_cost(eur: float | None, lang: str, estimated: bool = False) -> str:
    lang = norm_lang(lang)
    if eur is None:
        return "? €" if lang == "ru" else "€?"
    prefix = "≈" if estimated and eur > 0 else ""
    if eur <= 0:
        body = "0"
    elif eur < 0.01:
        body = f"{eur:.4f}".rstrip("0").rstrip(".")
        if lang == "ru":
            body = body.replace(".", ",")
    else:
        body = fmt_number(eur, lang, 2)
    return f"{prefix}{body} €" if lang == "ru" else f"{prefix}€{body}"


def fmt_bytes(n: float, lang: str) -> str:
    lang = norm_lang(lang)
    units = ("Б", "КБ", "МБ", "ГБ", "ТБ") if lang == "ru" else ("B", "KB", "MB", "GB", "TB")
    value = float(n)
    for i, unit in enumerate(units):
        if value < 1024 or i == len(units) - 1:
            decimals = 0 if i == 0 or value >= 100 else 1
            return f"{fmt_number(value, lang, decimals)} {unit}"
        value /= 1024
    return f"{n} B"  # pragma: no cover


def fmt_percent(p: float, lang: str) -> str:
    return f"{fmt_number(p, lang, 0)}%"


def join_list(items: Iterable[str], lang: str) -> str:
    return ", ".join(items)


def left_machine_statement(left: bool, destinations: Iterable[str], lang: str) -> str:
    lang = norm_lang(lang)
    dest = [d for d in destinations if d]
    if not left:
        return "данные не покидали компьютер" if lang == "ru" else "data stayed on this computer"
    if lang == "ru":
        return "данные отправлены: " + ", ".join(dest) if dest else "данные покидали компьютер"
    return "data sent to: " + ", ".join(dest) if dest else "data left this computer"


def meta_line(latency_ms: float, tokens: int, cost_eur: float | None, left: bool,
              destinations: Iterable[str], lang: str, estimated: bool = False) -> str:
    """Footer meta line: ``0,8 с · 312 токенов · 0 € · данные не покидали компьютер``."""
    return " · ".join([
        fmt_latency(latency_ms, lang),
        fmt_tokens(tokens, lang),
        fmt_cost(cost_eur, lang, estimated),
        left_machine_statement(left, destinations, lang),
    ])


# ---------------------------------------------------------------------------
# message catalogue

MESSAGES: dict[str, dict[str, str]] = {
    # routing
    "route.local.fast": {
        "ru": "локально: быстрый ответ, данные не покидают компьютер",
        "en": "local: fast answer, data stays on this computer",
    },
    "route.local.policy": {
        "ru": "локально: политика «только локально», данные не покидают компьютер",
        "en": "local: “local only” policy, data stays on this computer",
    },
    "route.local.explicit": {
        "ru": "локально по твоему выбору, данные не покидают компьютер",
        "en": "local, as you asked; data stays on this computer",
    },
    "route.local.code": {
        "ru": "локально · код: данные не покидают компьютер",
        "en": "local · code: data stays on this computer",
    },
    "route.local.vision": {
        "ru": "локально · модель со зрением, данные не покидают компьютер",
        "en": "local · vision model, data stays on this computer",
    },
    "route.local.budget": {
        "ru": "локально: дневной бюджет на облако исчерпан ({budget})",
        "en": "local: today's cloud budget is spent ({budget})",
    },
    "route.cloud.explicit": {
        "ru": "облако по твоему выбору: {provider} · {model}, запрос уйдёт с компьютера",
        "en": "cloud, as you asked: {provider} · {model}; the request leaves this computer",
    },
    "route.cloud.unavailable": {
        "ru": "облако: локальная модель недоступна ({why}), политика разрешает {provider}",
        "en": "cloud: no local model available ({why}); policy allows {provider}",
    },
    "route.cloud.vision": {
        "ru": "облако: нужна модель со зрением, локальной такой нет — {provider}",
        "en": "cloud: this needs a vision model and none runs locally — {provider}",
    },
    "route.cloud.long": {
        "ru": "облако: длинный контекст (~{tokens}) не влезет в локальную модель — {provider}",
        "en": "cloud: long context (~{tokens}) does not fit a local model — {provider}",
    },
    "route.cloud.preferred": {
        "ru": "облако: {provider} · {model} — первый в настройках для задачи «{task}»",
        "en": "cloud: {provider} · {model} is first in your settings for “{task}”",
    },
    "route.fastpath": {
        "ru": "быстрая команда без модели",
        "en": "quick command, no model needed",
    },
    "route.none": {
        "ru": "Нет доступной модели: {why}",
        "en": "No model available: {why}",
    },
    "route.why.offline": {
        "ru": "включён офлайн-режим, а локальная модель не отвечает. Запусти её: `svoya models serve`",
        "en": "offline mode is on and the local model is not answering. Start it: `svoya models serve`",
    },
    "route.why.local_only": {
        "ru": "политика «только локально», а локальная модель не отвечает ({detail}). "
              "Запусти её (`svoya models serve`) или разреши облако: `jackson route set policy any`",
        "en": "the policy is “local only” and the local model is not answering ({detail}). "
              "Start it (`svoya models serve`) or allow the cloud: `jackson route set policy any`",
    },
    "route.why.no_cloud": {
        "ru": "облачных провайдеров с ключом нет. Добавь ключ: "
              "`secret-tool store --label='Svoya: anthropic' service svoya provider anthropic`",
        "en": "no cloud provider has a key. Add one: "
              "`secret-tool store --label='Svoya: anthropic' service svoya provider anthropic`",
    },
    "route.why.budget": {
        "ru": "дневной бюджет на облако исчерпан ({budget}), а локальная модель не отвечает",
        "en": "today's cloud budget is spent ({budget}) and the local model is not answering",
    },
    "route.why.capability": {
        "ru": "нет модели, которая умеет это ({task}) при текущей политике",
        "en": "no model can do this ({task}) under the current policy",
    },
    "route.why.generic": {
        "ru": "ни один провайдер не отвечает ({detail})",
        "en": "no provider is answering ({detail})",
    },
    # turn / daemon
    "err.busy": {
        "ru": "Уже отвечаю на предыдущий запрос. Дождись ответа или отмени его.",
        "en": "Still answering the previous request. Wait for it or cancel it.",
    },
    "err.cancelled": {"ru": "Остановлено.", "en": "Stopped."},
    "err.shutdown": {"ru": "Джексон перезапускается — повтори запрос.", "en": "Jackson is restarting — please retry."},
    "err.bad_message": {"ru": "Не понял сообщение клиента: {why}", "en": "Malformed client message: {why}"},
    "err.provider": {"ru": "Модель не ответила: {why}", "en": "The model failed: {why}"},
    "err.internal": {"ru": "Внутренняя ошибка Джексона: {why}", "en": "Jackson internal error: {why}"},
    "err.max_steps": {
        "ru": "Остановился: слишком много шагов с инструментами ({n}). Уточни задачу.",
        "en": "Stopped: too many tool steps ({n}). Please narrow the task.",
    },
    "err.no_undo": {"ru": "Нечего отменять.", "en": "Nothing to undo."},
    # tools / approvals
    "tool.denied": {
        "ru": "Пользователь отклонил действие. Не повторяй его и не ищи обходных путей.",
        "en": "The user denied this action. Do not retry it or look for a workaround.",
    },
    "tool.denied.summary": {"ru": "отклонено", "en": "denied"},
    "tool.approval_timeout": {"ru": "нет ответа на запрос разрешения — отклонено", "en": "no answer to the approval request — denied"},
    "tool.blocked": {"ru": "заблокировано: {why}", "en": "blocked: {why}"},
    "approval.reason.t2": {"ru": "внешнее действие (T2)", "en": "external side effect (T2)"},
    "approval.reason.t3": {"ru": "системное изменение (T3): polkit и снимок", "en": "system change (T3): polkit and snapshot"},
    "approval.reason.t4": {
        "ru": "секреты (T4): разрешение только на эту задачу",
        "en": "secrets (T4): permission for this task only",
    },
    "approval.reason.taint": {
        "ru": "в разговоре есть недоверенный контент ({sources}) — отправка наружу только с подтверждением",
        "en": "the conversation contains untrusted content ({sources}) — sending out needs confirmation",
    },
    "approval.reason.nosandbox": {
        "ru": "песочница недоступна (нет bwrap) — команда выполнится без изоляции",
        "en": "sandbox unavailable (no bwrap) — the command would run without isolation",
    },
    "memory.written": {"ru": "запомнил: {text}", "en": "remembered: {text}"},
    "memory.forgot": {"ru": "забыл {n} {entries}", "en": "forgot {n} {entries}"},
    "memory.journal": {"ru": "записал в журнал", "en": "added to the journal"},
    "undo.done": {"ru": "Отменил: {summary}", "en": "Undone: {summary}"},
    "undo.failed": {"ru": "Не получилось отменить: {why}", "en": "Could not undo: {why}"},
    "undo.not_found": {"ru": "Нет действия с номером {id}.", "en": "No action with id {id}."},
    "undo.already": {"ru": "Действие {id} уже отменено.", "en": "Action {id} is already undone."},
    "undo.irreversible": {"ru": "Действие {id} нельзя отменить.", "en": "Action {id} cannot be undone."},
    "undo.no_handler": {"ru": "Не умею отменять «{kind}».", "en": "I cannot undo “{kind}”."},
    "undo.changed": {
        "ru": "{path} изменился после меня — не трогаю (прежняя версия лежит в корзине)",
        "en": "{path} changed after I wrote it — leaving it alone (the previous version is in the trash)",
    },
    "undo.prev_gone": {"ru": "прежней версии {name} уже нет в корзине", "en": "the previous version of {name} is no longer in the trash"},
    "undo.exists": {"ru": "{path} снова существует — не перезаписываю", "en": "{path} exists again — not overwriting it"},
    "undo.missing": {"ru": "{path} уже нет", "en": "{path} is gone"},
    "undo.hash": {"ru": "восстановил {path}, но содержимое не совпало с ожидаемым", "en": "restored {path}, but its content does not match"},
    "undo.no_system": {"ru": "системный откат недоступен (нет svoya/snapper)", "en": "system undo is unavailable (no svoya/snapper)"},
    "undo.system_failed": {"ru": "откат снимка не удался: {why}", "en": "snapshot rollback failed: {why}"},
}


def t(key: str, lang: str, **kwargs: object) -> str:
    lang = norm_lang(lang)
    entry = MESSAGES.get(key)
    if entry is None:
        return key
    template = entry.get(lang) or entry.get("en") or key
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return template
    return template


def entries_word(n: int, lang: str) -> str:
    if norm_lang(lang) == "ru":
        return plural_ru(n, "запись", "записи", "записей")
    return "entry" if n == 1 else "entries"
