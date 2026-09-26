# SPDX-License-Identifier: Apache-2.0
"""Games, jokes, memes and greetings for the fast path: instant, offline, no model.

Every function returns ``(ru, en)`` text and takes a ``random.Random`` seeded by the turn, so a
reply is random for the person and repeatable in tests. The kent persona («кентафурик») gets its
own voice; the other personas get plain lines. Jokes are original or anonymous folklore.
"""

from __future__ import annotations

import datetime as dt
import random
import re

from .variety import fresh

T = tuple[str, str]

# ---------------------------------------------------------------------------
# games

def coin(rng: random.Random, kent: bool) -> T:
    heads = rng.random() < 0.5
    ru = "орёл" if heads else "решка"
    en = "Heads" if heads else "Tails"
    if kent:
        return (f"Подкинул, лови: {ru}!", f"Flipped it, catch: {en.lower()}!")
    return (f"{ru.capitalize()}.", f"{en}.")


def dice(rng: random.Random, sides: int, kent: bool) -> T:
    n = rng.randint(1, sides)
    ru, en = f"Выпало {n} из {sides}.", f"Rolled {n} of {sides}."
    if sides == 20 and n == 20:
        return (ru + (" Критический успех, чуваааак!" if kent else " Критический успех."),
                en + " Natural twenty!")
    if sides == 20 and n == 1:
        return (ru + (" Критический провал. Бывает, кентафурик." if kent else " Критический провал."),
                en + " Critical failure.")
    return ru, en


BALL_KENT: list[T] = [
    ("Базару нет — да.", "No doubt: yes."), ("Сто пудов.", "A hundred percent."),
    ("Это база: да.", "That's basic: yes."), ("Скорее да, чем нет.", "More yes than no."),
    ("Звёзды шепчут «да».", "The stars whisper yes."),
    ("Спроси позже, кентафурик: шар перегрелся.", "Ask later, buddy, the ball overheated."),
    ("Туманно. Встряхни ещё раз.", "Hazy. Shake again."),
    ("Даже не думай, чувак.", "Don't even think about it."), ("Не, не то.", "Nah."),
    ("Сомнительно, братишка.", "Doubtful, bro."),
]
BALL_PLAIN: list[T] = [
    ("Да.", "Yes."), ("Скорее да.", "Most likely."), ("Похоже на то.", "Signs point to yes."),
    ("Трудно сказать. Спросите ещё раз.", "Hard to say. Ask again."),
    ("Скорее нет.", "Probably not."), ("Нет.", "No."),
]


def ball(rng: random.Random, kent: bool) -> T:
    return fresh(rng, "ball:" + ("kent" if kent else "plain"), BALL_KENT if kent else BALL_PLAIN)


RPS_RU = {"камень": 0, "ножницы": 1, "бумага": 2, "бумагу": 2}
RPS_EN = {"rock": 0, "scissors": 1, "paper": 2}
RPS_NAMES: list[T] = [("камень", "rock"), ("ножницы", "scissors"), ("бумага", "paper")]


def rps(rng: random.Random, move: str | None, kent: bool) -> T:
    if not move:
        return ("Давай! Говори: камень, ножницы или бумага.", "Let's go! Say rock, paper or scissors.")
    mine = rng.randrange(3)
    theirs = RPS_RU.get(move, RPS_EN.get(move, 0))
    m_ru, m_en = RPS_NAMES[mine]
    if mine == theirs:
        return (f"У меня тоже {m_ru}. Ничья, ещё разок?", f"I also picked {m_en}. A draw, again?")
    you_win = (theirs - mine) % 3 == 2      # rock beats scissors, scissors beat paper, paper beats rock
    if you_win:
        return (f"У меня {m_ru}. Ты выиграл" + (", красава!" if kent else "."),
                f"I picked {m_en}. You win" + (", well played!" if kent else "."))
    return (f"У меня {m_ru}. Я выиграл" + (" — не расстраивайся, кентафурик." if kent else "."),
            f"I picked {m_en}. I win" + (", no hard feelings." if kent else "."))


def pick(rng: random.Random, a: str, b: str, kent: bool) -> T:
    choice = rng.choice([a.strip(), b.strip()])
    if kent:
        return (f"Я за «{choice}». Замётано.", f"I'd go with “{choice}”. Done deal.")
    return (f"Выбираю «{choice}».", f"I pick “{choice}”.")


def number(rng: random.Random, low: int, high: int) -> T:
    if low > high:
        low, high = high, low
    n = rng.randint(low, high)
    return (f"{n} (от {low} до {high}).", f"{n} (from {low} to {high}).")


# ---------------------------------------------------------------------------
# jokes: original or anonymous folklore, short

JOKES_RU = [
    "Сколько линуксоидов нужно, чтобы вкрутить лампочку? Ни одного: сначала надо собрать ядро с поддержкой лампочек.",
    "Почему система называется СОС? Потому что раньше, ставя драйвер видеокарты, все кричали «помогите».",
    "Снимок системы — это «сохраниться перед боссом». Только босс — это обновление.",
    "Мой код работает, и я не знаю почему. Мой код не работает, и я тоже не знаю почему.",
    "Есть два типа людей: те, кто делает бэкапы, и те, кто скоро начнёт.",
    "Оптимист: стакан наполовину полон. Пессимист: наполовину пуст. Программист: стакан в два раза больше, чем нужно.",
    "Программист ставит на тумбочку два стакана: с водой — если захочет пить, и пустой — если не захочет.",
    "Что делает линукс-геймер в пятницу вечером? Пишет в чат игры: «А под Proton идёт?»",
    "UpsiL научил нейросеть отвечать «да» или «нет». Раньше она отвечала тремя абзацами с оговорками.",
    "Раньше говорили «иди поспи». Теперь — «перезагрузись».",
    "Помощник хотел сказать «ошибка 404», но так и не нашёл нужных слов.",
    "Жена просит программиста: «Купи батон, а если будут яйца — возьми десяток». Он приносит десять батонов: «Яйца были».",
    "Шутить я умею, но на процессоре это занимает пару секунд. Так что смейся заранее, кентафурик.",
    "Обновил систему — всё работает. Подозрительно. Сделал ещё один снимок.",
    "Работает — не трогай. Не работает — «sos undo».",
]
JOKES_EN = [
    "How many Linux users does it take to change a light bulb? None: first you compile a kernel with bulb support.",
    "My code works and I don't know why. My code doesn't work and I don't know why either.",
    "There are two kinds of people: those who make backups and those who are about to start.",
    "An optimist sees the glass half full. A programmer sees a glass twice as big as it needs to be.",
    "A snapshot is a save point before the boss fight. The boss is the update.",
    "It works — don't touch it. It doesn't — `sos undo`.",
]


def joke(rng: random.Random) -> T:
    return fresh(rng, "joke:ru", JOKES_RU), fresh(rng, "joke:en", JOKES_EN)


# ---------------------------------------------------------------------------
# memes (Russian internet): answered in kind

PEPE_WORDS = ("пепе", "шнейне", "фа", "втфа", "ватафа")
PEPE_KENT: list[T] = [
    ("Фа! Пепе, шнейне — у нас всё на богатом, кентафурик.", "Fa! Pepe, shneyne: all on the rich side."),
    ("Пепе, шнейне, фа… Чуваааак, я в теме. Чем помочь по делу?", "Pepe, shneyne, fa… I'm in on it. What's the task?"),
    ("Втфа? Не, всё ровно: пепе и шнейне на месте.", "Wtfa? Nah, all smooth: pepe and shneyne in place."),
]


def pepe(rng: random.Random, kent: bool) -> T:
    if kent:
        return fresh(rng, "pepe", PEPE_KENT)
    return ("Мем знаю: «пепе, шнейне, фа». Чем помочь?", "I know the meme. How can I help?")


MEMES: dict[str, tuple[T | list[T], T]] = {
    # key: (kent reply or replies — a different one each time, plain reply)
    "preved": (("Превед, кросавчег! Чем помочь?", "Preved! What's up?"),
               ("Привет! Чем помочь?", "Hi! How can I help?")),
    "fiasco": (("Не фиаско, а опыт, братан. Рассказывай — разберёмся.", "Not a fiasco, bro, just experience. Tell me."),
               ("Не фиаско, а опыт. Расскажите, что случилось.", "Not a fiasco, just experience. What happened?")),
    "houston": (("Хьюстон на связи, кентафурик. Что сломалось? Могу начать с «sos doctor».",
                 "Houston here. What broke? `sos doctor` is a good start."),
                ("На связи. Что сломалось? Начните с «sos doctor».", "Here. What broke? Start with `sos doctor`.")),
    "good_job": (("Ты молодец, кентафурик! Это база.", "You did great, buddy! That's basic."),
                 ("Вы молодец!", "Well done!")),
    "dont_touch": (("Золотое правило. Но снимок перед обновлением я всё равно сделаю — так спокойнее.",
                    "Golden rule. I still take a snapshot before updates, though."),
                   ("Золотое правило. Снимок перед обновлением всё равно будет.",
                    "Golden rule. A snapshot comes before every update anyway.")),
    "oy_vse": (("Всё-всё, молчу. Если что — я на связи.", "Okay, okay, quiet. I'm here if you need me."),
               ("Хорошо. Я на связи.", "Okay. I'm here.")),
    "thanks": ([("Обращайся, кентафурик!", "Anytime, buddy!"),
                ("Да не за что, чувак. Я на связи.", "No problem, dude. I'm around."),
                ("Базару нет, обращайся!", "You bet, anytime!"),
                ("Изи, братишка. Если что — зови.", "Easy, bro. Call me anytime."),
                ("Йоу, всегда пожалуйста!", "Yo, you're welcome!")],
               ("Пожалуйста!", "You're welcome!")),
    "how_are_you": ([("Ровно, кентафурик: процессор тёплый, память свободна. У тебя как?",
                      "Smooth, buddy: warm CPU, free memory. How about you?"),
                     ("Йоу, всё чётко: логи чистые, диск не забит. Сам как?",
                      "Yo, all good: clean logs, plenty of disk. You?"),
                     ("Как по нотам, чувак. А у тебя что нового?", "Running like clockwork, dude. What's new with you?"),
                     ("Норм, кент: кулеры крутятся, настроение — имба. Ты как?",
                      "Solid, bro: fans spinning, mood on point. How are you?")],
                    ("Всё работает. Чем помочь?", "All systems go. How can I help?")),
    "answer42": (("42. Осталось понять вопрос, кентафурик.", "42. Now we just need the question."),
                 ("42. Осталось понять вопрос.", "42. Now we just need the question.")),
}


def meme(key: str, kent: bool, rng: random.Random | None = None) -> T:
    k, plain = MEMES[key]
    if not kent:
        return plain
    if isinstance(k, list):
        return fresh(rng or random.Random(), "meme:" + key, k)
    return k


# ---------------------------------------------------------------------------
# greetings that know the time

# «Кентафурик» greets differently every time — «йоу», «здарова», «салют», «хэй» — and never twice in a
# row (variety.fresh). {you} is «, кентафурик» / «, чувак» / «, кент» / «, братишка», or the user's name.
BUDDIES_RU = ("кентафурик", "кентафурик", "чувак", "кент", "братишка")
HELLO_KENT: dict[str, list[T]] = {
    "night": [
        ("Не спится{you}? Я тоже тут.", "Up late? I'm here too."),
        ("Йоу, полуночник! Чем помочь?", "Yo, night owl! What's up?"),
        ("Ночной движ{you}? Я на связи.", "Night shift, buddy? I'm here."),
    ],
    "monday": [
        ("Понедельник, утро… держись{you}. Чем помочь?", "Monday morning. Hang in there. What's up?"),
        ("Понедельник{you}? Изи, прорвёмся. С чего начнём?", "Monday, huh? Easy, we'll get through it. Where do we start?"),
        ("Понедельник, йоу! Кофе — и погнали{you}. Что делаем?", "Monday, yo! Coffee, then let's roll. What's first?"),
    ],
    "friday": [
        ("Пятница, чуваааак! Какие планы{you}?", "Friday evening! What's the plan?"),
        ("Пятница, вечер{you}! Йоу, игры или ещё поработаем?", "Friday night, yo! Games, or one more task?"),
        ("Пятница{you}! Это база: неделя закрыта. Чем помочь?", "Friday! The week is done, for real. What's up?"),
    ],
    "morning": [
        ("Йоу, доброе утро{you}! С чего начнём?", "Yo, good morning! Where do we start?"),
        ("Доброе утро{you}! Кофе уже был? Чем помочь?", "Morning, buddy! Coffee first? Then what's up?"),
        ("Утречко{you}! Я на связи — что делаем?", "Mornin'! I'm here — what are we doing?"),
        ("Здарооова{you}! Утро — лучшее время что-нибудь замутить. Чем помочь?",
         "Heyyy! Mornings are for building stuff. What's up?"),
    ],
    "day": [
        ("Йоу{you}! Чё как? Чем помочь?", "Yo! What's up?"),
        ("Здарова{you}! Чем помочь?", "Hey, buddy! What do you need?"),
        ("Йо-йо! Я на связи. Что мутим?", "Yo yo! What's the plan?"),
        ("Салют{you}! Погнали — что нужно?", "Sup, dude? Let's roll — what do you need?"),
        ("Хэй{you}! Я тут. Что делаем?", "Hey hey! I'm here. What are we doing?"),
        ("Здарооова{you}! Какие задачи?", "Heyyy! What's on the list?"),
    ],
    "evening": [
        ("Добрый вечер{you}! Чем помочь?", "Evening, buddy! What's up?"),
        ("Йоу{you}! Вечерний движ — что делаем?", "Yo! Evening shift — what are we doing?"),
        ("Здарова{you}! Вечер — самое время для чего-нибудь годного. Чем помочь?",
         "Hey! Evenings are for good stuff. What do you need?"),
        ("Хэй{you}! Я на связи. Что нужно?", "Hey, dude! I'm here. What do you need?"),
    ],
}


def greeting(now: dt.datetime, kent: bool, name: str = "", rng: random.Random | None = None) -> T:
    """«Йоу, кентафурик!», «Здарова!», «Салют!»… with a twist for the night, Monday morning, Friday evening
    and holidays; the plain voice says «Добрый день»."""
    rng = rng or random.Random()
    md = (now.month, now.day)
    h, wd = now.hour, now.weekday()
    you_ru = name or (fresh(rng, "buddy", BUDDIES_RU) if kent else "")
    you = f", {you_ru}" if you_ru else ""
    if md == (12, 31):
        return (f"С наступающим{you}! Снимок системы на Новый год уже сделан?", "Happy New Year's Eve!")
    if md == (1, 1):
        return (f"С Новым годом{you}!" + (" Чуваааак, новый год — новые драйверы." if kent else ""), "Happy New Year!")
    if md == (4, 1):
        return (f"С первым апреля{you}! Обещаю не шутить над твоими файлами.", "Happy April Fools'! Your files are safe.")
    if now.timetuple().tm_yday == 256:                    # programmers' day in Russia: 13 Sep (12 Sep in leap years)
        return (f"С Днём программиста{you}! Сегодня 256-й день года — самое круглое число.",
                "Happy Programmers' Day: day 256 of the year.")
    if 0 <= h < 5:
        slot = "night"
    elif wd == 0 and 5 <= h < 12:
        slot = "monday"
    elif wd == 4 and h >= 17:
        slot = "friday"
    else:
        slot = "morning" if 5 <= h < 12 else ("day" if h < 18 else "evening")
    if kent:
        ru, en = fresh(rng, "hello:" + slot, HELLO_KENT[slot])
        return ru.format(you=you), en
    plain = {"night": ("Доброй ночи. Чем помочь?", "Up late? I'm here too."),
             "monday": ("Доброе утро! Чем помочь?", "Monday morning. Hang in there. What's up?"),
             "friday": ("Добрый вечер пятницы! Чем помочь?", "Friday evening! What's the plan?"),
             "morning": ("Доброе утро! Чем помочь?", "Hi! How can I help?"),
             "day": ("Добрый день! Чем помочь?", "Hi! How can I help?"),
             "evening": ("Добрый вечер! Чем помочь?", "Hi! How can I help?")}
    return plain[slot]


# ---------------------------------------------------------------------------
# Morse code (the SOS mark is «··· ——— ···»)

MORSE = {
    "a": ".-", "b": "-...", "c": "-.-.", "d": "-..", "e": ".", "f": "..-.", "g": "--.", "h": "....", "i": "..",
    "j": ".---", "k": "-.-", "l": ".-..", "m": "--", "n": "-.", "o": "---", "p": ".--.", "q": "--.-", "r": ".-.",
    "s": "...", "t": "-", "u": "..-", "v": "...-", "w": ".--", "x": "-..-", "y": "-.--", "z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....", "6": "-....",
    "7": "--...", "8": "---..", "9": "----.", ".": ".-.-.-", ",": "--..--", "?": "..--..",
    "!": "-.-.--", "-": "-....-", "/": "-..-.", "@": ".--.-.", "(": "-.--.", ")": "-.--.-", ":": "---...",
    # Russian (the Cyrillic Morse code)
    "а": ".-", "б": "-...", "в": ".--", "г": "--.", "д": "-..", "е": ".", "ё": ".", "ж": "...-", "з": "--..",
    "и": "..", "й": ".---", "к": "-.-", "л": ".-..", "м": "--", "н": "-.", "о": "---", "п": ".--.", "р": ".-.",
    "с": "...", "т": "-", "у": "..-", "ф": "..-.", "х": "....", "ц": "-.-.", "ч": "---.", "ш": "----",
    "щ": "--.-", "ъ": "--.--", "ы": "-.--", "ь": "-..-", "э": "..-..", "ю": "..--", "я": ".-.-",
}


def morse(text: str) -> str:
    """«sos» → «··· ——— ···»: letters apart by a space, words by « / »; unknown characters are skipped."""
    words = []
    for word in re.split(r"\s+", text.strip().lower()):
        codes = [MORSE[ch] for ch in word if ch in MORSE]
        if codes:
            words.append(" ".join(c.replace(".", "·").replace("-", "—") for c in codes))
    return " / ".join(words)
