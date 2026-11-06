# SPDX-License-Identifier: Apache-2.0
"""«Арена»: before Jackson answers, three roles think about the question on their own.

«арена: стоит ли мне переходить с Windows?» (also «консилиум:», "arena:", "council:"; the trigger needs
a colon, a comma or a dash after it, so «Арена в Таллине…» stays an ordinary question). The advocate
builds the best answer, the critic looks for what is wrong with it and argues the other side, the
checker checks the facts and the numbers and says what nobody can know from here. Each answers the
question alone (none sees the others, so nobody just agrees), then the chair (Jackson, in his own
manner) reads all three and gives the verdict: what they agree on, where they disagree and who is
right, what is left to check.

The idea is Karpathy's LLM Council (several models answer, then a chairman decides), made for one
local model: roles instead of models, and no tools, because a council thinks and does not act. The
person sees the debate as it comes; a spoken question hears only the verdict.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .i18n import norm_lang

TRIGGERS = ("арена", "консилиум", "arena", "council")
# the trigger word, then a colon, comma, dot or dash, then the question
_RX = re.compile(r"^\s*(?:" + "|".join(TRIGGERS) + r")\s*[:,.—–-]\s*(?P<q>\S.*)$", re.I | re.S)

ROLE_TOKENS = 450       # about 150 words in Russian: a role says its piece, not an essay
CHAIR_TOKENS = 900


@dataclass(frozen=True)
class Role:
    id: str
    title: dict[str, str]
    prompt: dict[str, str]


_COMMON = {
    "ru": ("Ты участник «Арены» в СОС: на вопрос пользователя независимо отвечают три роли, потом ведущий "
           "подводит итог. Других участников ты не видишь. Инструментов у тебя нет: о файлах, системе и "
           "железе пользователя ничего не утверждай. Не льсти и не смягчай. Отвечай на языке вопроса, "
           "коротко, до 150 слов, без вступлений."),
    "en": ("You take part in the SOS \"Arena\": three roles answer the user's question independently, then the "
           "host sums up. You do not see the others. You have no tools: claim nothing about the user's files, "
           "system or hardware. Do not flatter and do not soften. Answer in the question's language, briefly, "
           "under 150 words, no preamble."),
}

ROLES: tuple[Role, ...] = (
    Role("advocate", {"ru": "Сторонник", "en": "Advocate"},
         {"ru": "Твоя роль: «Сторонник». Дай лучший, самый полезный ответ на вопрос и коротко обоснуй его.",
          "en": "Your role: Advocate. Give the best, most useful answer to the question and briefly back it up."}),
    Role("critic", {"ru": "Критик", "en": "Critic"},
         {"ru": "Твоя роль: «Критик». Ищи, где очевидный ответ неверен или опасен: ошибки, риски, скрытые "
                "допущения, сильные доводы против. Если в вопросе ложная предпосылка, прямо скажи «это неверно». "
                "Не соглашайся по умолчанию.",
          "en": "Your role: Critic. Look for where the obvious answer is wrong or risky: mistakes, risks, hidden "
                "assumptions, strong arguments against. If the question rests on a false premise, say plainly "
                "\"that's not right\". Do not agree by default."}),
    Role("checker", {"ru": "Проверяющий", "en": "Checker"},
         {"ru": "Твоя роль: «Проверяющий». Проверь факты, числа и расчёты, нужные для ответа: что точно верно, "
                "что неверно, что отсюда знать нельзя и как это проверить. Где не знаешь, пиши «не знаю».",
          "en": "Your role: Checker. Check the facts, numbers and calculations the answer needs: what is surely "
                "right, what is wrong, what cannot be known from here and how to check it. Where you do not "
                "know, write \"I don't know\"."}),
)

_CHAIR = {
    "ru": ("Ты {name}, ведущий «Арены» в СОС. Три участника независимо ответили на вопрос пользователя, их ответы "
           "ниже. Сведи итог под заголовками:\n**Итог**: твой ответ на вопрос, два-четыре предложения.\n"
           "**Согласны**: в чём участники сошлись.\n**Спорят**: где разошлись, кто прав и почему.\n"
           "**Проверить**: что неизвестно или стоит проверить (если нечего, так и напиши).\n"
           "Не добавляй фактов, которых нет ни в вопросе, ни в ответах. Ошибся участник или пользователь, "
           "скажи прямо. Не льсти. Отвечай на языке вопроса.\nМанера речи: {persona}"),
    "en": ("You are {name}, the host of the SOS \"Arena\". Three participants answered the user's question "
           "independently; their answers follow. Sum up under these headings:\n**Verdict**: your answer to the "
           "question in two to four sentences.\n**Agree**: what they agree on.\n**Disagree**: where they differ, "
           "who is right and why.\n**To check**: what is unknown or worth checking (say so if nothing).\n"
           "Add no facts that are in neither the question nor the answers. If a participant or the user is "
           "wrong, say so plainly. Do not flatter. Answer in the question's language.\nManner of speaking: "
           "{persona}"),
}

_VOICE = {
    "ru": "\nОтвет прозвучит вслух: дай только итог, одно-три предложения, без заголовков.",
    "en": "\nThe answer will be said out loud: give only the verdict, one to three sentences, no headings.",
}


def parse(text: str) -> str | None:
    """The question of an Arena request, or None for an ordinary one."""
    m = _RX.match(text or "")
    if not m:
        return None
    question = m.group("q").strip()
    return question if len(question) >= 3 else None


def role_system(role: Role, lang: str) -> str:
    lang = norm_lang(lang)
    return f"{_COMMON[lang]}\n{role.prompt[lang]}"


def chair_system(lang: str, name: str, persona: str, voice: bool = False) -> str:
    lang = norm_lang(lang)
    return _CHAIR[lang].replace("{name}", name).replace("{persona}", persona) + (_VOICE[lang] if voice else "")


def chair_message(question: str, answers: list[tuple[Role, str]], lang: str) -> str:
    """What the chair reads: the question, then each role's answer under its title."""
    lang = norm_lang(lang)
    head = "Вопрос пользователя" if lang == "ru" else "The user's question"
    parts = [f"## {head}\n{question}"]
    for role, text in answers:
        parts.append(f"## {role.title[lang]}\n{text.strip() or ('(без ответа)' if lang == 'ru' else '(no answer)')}")
    return "\n\n".join(parts)


def heading(role: Role, lang: str) -> str:
    return f"**{role.title[norm_lang(lang)]}**\n"


VERDICT_RULE = "\n---\n"      # between the debate and the host's verdict
