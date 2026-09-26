# SPDX-License-Identifier: Apache-2.0
"""Jackson's answer as speech: Markdown streamed by the model → sentences to say.

:class:`SpeechStream` hands out each sentence as soon as it is complete, so the voice starts with
the first one while the model is still writing the rest. Code blocks and tables are not read out
(«Код — на экране.» once), links become their text, emphasis and emoji disappear, and numbers are
spelled out (:func:`numbers_to_words`) for engines that read digits badly: «70%» → «семьдесят
процентов», «15:30» → «пятнадцать тридцать», «12 ГБ» → «двенадцать гигабайт».

Standard library only: jacksond imports this.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------------------------
# numbers

_RU_UNITS_M = ["ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_RU_UNITS_F = ["ноль", "одна", "две"] + _RU_UNITS_M[3:]
_RU_TEENS = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать",
             "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
_RU_TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят",
            "восемьдесят", "девяносто"]
_RU_HUNDREDS = ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот",
                "восемьсот", "девятьсот"]
# scale: (forms one/few/many, feminine)
_RU_SCALES = [(("тысяча", "тысячи", "тысяч"), True), (("миллион", "миллиона", "миллионов"), False),
              (("миллиард", "миллиарда", "миллиардов"), False)]

_EN_UNITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
             "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
             "nineteen"]
_EN_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_EN_SCALES = ["thousand", "million", "billion"]


def ru_plural(n: int, one: str, few: str, many: str) -> str:
    """The noun form after *n*: 1 процент, 2 процента, 5 процентов, 11 процентов, 21 процент."""
    n = abs(n)
    if 11 <= n % 100 <= 14:
        return many
    if n % 10 == 1:
        return one
    if 2 <= n % 10 <= 4:
        return few
    return many


def _ru_triple(n: int, feminine: bool) -> list[str]:
    words = []
    h, rest = divmod(n, 100)
    if h:
        words.append(_RU_HUNDREDS[h])
    if 10 <= rest < 20:
        words.append(_RU_TEENS[rest - 10])
    else:
        t, u = divmod(rest, 10)
        if t:
            words.append(_RU_TENS[t])
        if u:
            words.append((_RU_UNITS_F if feminine else _RU_UNITS_M)[u])
    return words


def ru_number(n: int, feminine: bool = False) -> str:
    if n < 0:
        return "минус " + ru_number(-n, feminine)
    if n == 0:
        return "ноль"
    words: list[str] = []
    groups = []
    while n:
        n, g = divmod(n, 1000)
        groups.append(g)
    for i in range(len(groups) - 1, -1, -1):
        g = groups[i]
        if not g:
            continue
        if i == 0:
            words += _ru_triple(g, feminine)
        elif i <= len(_RU_SCALES):
            forms, fem = _RU_SCALES[i - 1]
            words += _ru_triple(g, fem)
            words.append(ru_plural(g, *forms))
        else:  # beyond billions: say the digits
            return " ".join(_RU_UNITS_M[int(d)] for d in str(n))
    return " ".join(words)


def _en_triple(n: int) -> list[str]:
    words = []
    h, rest = divmod(n, 100)
    if h:
        words += [_EN_UNITS[h], "hundred"]
    if rest:
        if rest < 20:
            words.append(_EN_UNITS[rest])
        else:
            t, u = divmod(rest, 10)
            words.append(_EN_TENS[t] + (f"-{_EN_UNITS[u]}" if u else ""))
    return words


def en_number(n: int) -> str:
    if n < 0:
        return "minus " + en_number(-n)
    if n == 0:
        return "zero"
    groups = []
    while n:
        n, g = divmod(n, 1000)
        groups.append(g)
    if len(groups) > len(_EN_SCALES) + 1:
        return " ".join(_EN_UNITS[int(d)] for d in "".join(str(g) for g in groups))
    words: list[str] = []
    for i in range(len(groups) - 1, -1, -1):
        if groups[i]:
            words += _en_triple(groups[i])
            if i:
                words.append(_EN_SCALES[i - 1])
    return " ".join(words)


# units after a number: pattern → (Russian forms one/few/many, feminine, English singular, plural)
_UNITS: list[tuple[str, tuple[str, str, str], bool, str, str]] = [
    (r"%", ("процент", "процента", "процентов"), False, "percent", "percent"),
    (r"°\s?[CС]|°", ("градус", "градуса", "градусов"), False, "degree", "degrees"),
    (r"(?:ТБ|Тб|TB)\b", ("терабайт", "терабайта", "терабайт"), False, "terabyte", "terabytes"),
    (r"(?:ГБ|Гб|GB|GiB)\b", ("гигабайт", "гигабайта", "гигабайт"), False, "gigabyte", "gigabytes"),
    (r"(?:МБ|Мб|MB|MiB)\b", ("мегабайт", "мегабайта", "мегабайт"), False, "megabyte", "megabytes"),
    (r"(?:КБ|Кб|KB|kB)\b", ("килобайт", "килобайта", "килобайт"), False, "kilobyte", "kilobytes"),
    (r"(?:ГГц|GHz)\b", ("гигагерц", "гигагерца", "гигагерц"), False, "gigahertz", "gigahertz"),
    (r"(?:₽|руб\.?(?=\s|$))", ("рубль", "рубля", "рублей"), False, "ruble", "rubles"),
    (r"€", ("евро", "евро", "евро"), False, "euro", "euros"),
    (r"\$", ("доллар", "доллара", "долларов"), False, "dollar", "dollars"),
    (r"(?:мин\.?(?=\s|$|[,;])|min\b)", ("минута", "минуты", "минут"), True, "minute", "minutes"),
    (r"(?:сек\.?(?=\s|$|[,;])|sec\b)", ("секунда", "секунды", "секунд"), True, "second", "seconds"),
]
_UNIT_RE = "|".join(f"(?:{u[0]})" for u in _UNITS)
# feminine nouns that follow a number in Jackson's answers: «одна минута», «две вкладки»
_RU_FEMININE = re.compile(r"\s+(?:минут|секунд|недел|строк|ошибк|папк|вкладк|задач|программ|заметк|штук|"
                          r"копи|верси|страниц|картин|фотографи|песн|книг|тысяч|игр|ссылк|клавиш|кнопк)",
                          re.IGNORECASE)


def _unit_for(text: str) -> tuple[tuple[str, str, str], bool, str, str] | None:
    for pattern, forms, fem, one, many in _UNITS:
        if re.fullmatch(pattern, text):
            return forms, fem, one, many
    return None


def _say_number(n: int, lang: str, feminine: bool = False) -> str:
    return ru_number(n, feminine) if lang == "ru" else en_number(n)


def _say_decimal(whole: int, frac: str, lang: str) -> str:
    frac = frac.rstrip("0") or "0"
    if lang == "ru":   # «три и пять», «три и ноль пять»
        tail = " ".join(_RU_UNITS_M[int(d)] for d in frac) if frac.startswith("0") else ru_number(int(frac))
        return f"{ru_number(whole)} и {tail}"
    return f"{en_number(whole)} point {' '.join(_EN_UNITS[int(d)] for d in frac)}"


def _time(h: int, m: int, lang: str) -> str:
    if lang == "ru":
        minutes = "ноль-ноль" if m == 0 else (f"ноль {ru_number(m)}" if m < 10 else ru_number(m))
        return f"{ru_number(h)} {minutes}"
    if m == 0:
        return f"{en_number(h)} o'clock" if h <= 12 else f"{en_number(h)} hundred"
    return f"{en_number(h)} {'oh ' + en_number(m) if m < 10 else en_number(m)}"


def numbers_to_words(text: str, lang: str) -> str:
    """Spell out the numbers of *text* (Russian or English) the way they are said."""
    lang = "ru" if lang == "ru" else "en"

    def money_before(m: re.Match[str]) -> str:          # $5, €12
        unit = _unit_for(m.group(1))
        n = int(m.group(2))
        if not unit:
            return m.group(0)
        forms, fem, one, many = unit
        if lang == "ru":
            return f"{ru_number(n, fem)} {ru_plural(n, *forms)}"
        return f"{en_number(n)} {one if n == 1 else many}"

    def with_unit(m: re.Match[str]) -> str:
        sign = "-" if m.group(1) else ""
        whole = int(m.group(2).replace("\u00a0", "").replace(" ", ""))
        frac, unit_text = m.group(3), m.group(4)
        unit = _unit_for(unit_text)
        if not unit:
            return m.group(0)
        forms, fem, one, many = unit
        if frac:
            said = _say_decimal(whole, frac, lang)
            noun = forms[1] if lang == "ru" else many       # 3,5 процента · 3.5 percent
        else:
            said = _say_number(whole, lang, fem)
            noun = ru_plural(whole, *forms) if lang == "ru" else (one if whole == 1 else many)
        return f"{'минус ' if sign and lang == 'ru' else 'minus ' if sign else ''}{said} {noun}"

    def clock(m: re.Match[str]) -> str:
        h, mi = int(m.group(1)), int(m.group(2))
        if h > 23 or mi > 59:
            return m.group(0)
        return _time(h, mi, lang) + (f" {m.group(3).upper().replace('.', '')}" if m.group(3) else "")

    def decimal(m: re.Match[str]) -> str:
        return _say_decimal(int(m.group(1)), m.group(2), lang)

    def plain(m: re.Match[str]) -> str:
        digits = m.group(1).replace("\u00a0", "").replace(" ", "")
        n = int(digits)
        feminine = lang == "ru" and bool(_RU_FEMININE.match(m.group(2) or ""))
        return _say_number(n, lang, feminine) + (m.group(2) or "")

    text = re.sub(r"([$€])\s?(\d+)(?![\w.,]\d)", money_before, text)
    text = re.sub(rf"(?<![\w.,])(-|−)?(\d{{1,3}}(?:[\u00a0 ]\d{{3}})+|\d+)(?:[.,](\d+))?\s?({_UNIT_RE})",
                  with_unit, text)
    text = re.sub(r"(?<![\w.:])(\d{1,2}):(\d{2})(?![\w:])(?:\s?([AaPp]\.?[Mm]\.?))?", clock, text)
    text = re.sub(r"(?<![\w.,])(\d+)[.,](\d+)(?![\w]|[.,]\d)", decimal, text)
    text = re.sub(r"(?<![\w.,])(\d{1,3}(?:[\u00a0 ]\d{3})+|\d+)(?![\w]|[.,]\d)(\s+\w+)?", plain, text)
    return text


# ---------------------------------------------------------------------------------------------
# Markdown → speakable text

_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍⬀-⯿]+")
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_URL = re.compile(r"\b(?:https?://|www\.|file://)\S+?(?=[.,;:!?)\]»\"']*(?:\s|$))")
# a path in the text: say its last part («~/Документы/план.md» → «план.md»)
_PATH = re.compile(r"(?<!\w)(?:~|\.{1,2})?(?:/[^\s/]+)+/([^\s/]+?)(?=[.,;:!?)\]»\"']*(?:\s|$))")
_CODE_SPAN = re.compile(r"`([^`]*)`")
_EMPHASIS = re.compile(r"(\*\*|__|\*|~~)(?=\S)(.+?)(?<=\S)\1")
_LINE_MARK = re.compile(r"^\s{0,3}(?:#{1,6}\s+|>\s?|[-*+•]\s+|\d{1,3}[.)]\s+)")

_SAID = {
    "code": {"ru": "Код — на экране.", "en": "The code is on the screen."},
    "table": {"ru": "Таблица — на экране.", "en": "The table is on the screen."},
    "link": {"ru": "ссылка", "en": "a link"},
}


def clean_inline(text: str, lang: str) -> str:
    """One line of Markdown as it should sound: no markup, links as their text, no emoji."""
    text = _LINK.sub(lambda m: m.group(1), text)
    text = _URL.sub(_SAID["link"]["ru" if lang == "ru" else "en"], text)
    text = _PATH.sub(lambda m: m.group(1), text)
    text = _CODE_SPAN.sub(lambda m: m.group(1) if len(m.group(1)) <= 40 else "", text)
    text = _EMPHASIS.sub(lambda m: m.group(2), text)
    text = _EMOJI.sub("", text)
    text = text.replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


_END = re.compile(r"[.!?…]+[\"»”')\]]*\s+")


def _balanced_cut(text: str, limit: int) -> int:
    """The longest prefix of *text* up to *limit* that ends at a space and leaves no link or code
    span half open, so that the cleanup sees every piece whole."""
    while limit > 0:
        head = text[:limit]
        if head.count("[") == head.count("]") and head.count("(") == head.count(")") and head.count("`") % 2 == 0:
            return limit
        limit = text.rfind(" ", 0, limit - 1) + 1
    return 0
_CLAUSE = re.compile(r"[,;:—–]\s+")


class SpeechStream:
    """Feed the answer as it streams; get back the sentences that are ready to be said."""

    def __init__(self, lang: str, *, numbers: bool = True, first_min: int = 40, max_len: int = 220) -> None:
        self.lang = "ru" if lang == "ru" else "en"
        self.numbers = numbers
        self.first_min = first_min
        self.max_len = max_len
        self.raw = ""            # Markdown not looked at yet
        self.prose = ""          # speakable text not handed out yet
        self.in_code = False
        self.line_open = False   # the start of the current line is already in `prose`
        self.said_once: set[str] = set()
        self.first = True

    # ---- structure (whole lines) ----
    def _once(self, what: str) -> None:
        if what not in self.said_once:
            self.said_once.add(what)
            self._end_sentence()
            self.prose += _SAID[what][self.lang] + " "

    def _end_sentence(self) -> None:
        tail = self.prose.rstrip()
        if tail and tail[-1] not in ".!?…:;,":
            self.prose = tail + ". "
        elif tail:
            self.prose = tail + " "

    def _take_lines(self, final: bool) -> None:
        while True:
            nl = self.raw.find("\n")
            if nl < 0:
                if final and self.raw:
                    nl = len(self.raw)
                    self.raw += "\n"
                else:
                    break
            line, self.raw = self.raw[:nl], self.raw[nl + 1:]
            stripped = line.strip()
            if self.in_code:
                if stripped.startswith("```") and not self.line_open:
                    self.in_code = False
                continue
            if not self.line_open and stripped.startswith("```"):
                self.in_code = True
                self._once("code")
                continue
            if not self.line_open and stripped.startswith("|"):
                self._once("table")
                continue
            if not self.line_open:
                line = _LINE_MARK.sub("", line)
                if not line.strip():
                    self._end_sentence()   # an empty line ends a paragraph
                    continue
            self.prose += clean_inline(line, self.lang)
            self.line_open = False
            self._end_sentence()           # a list item or a line of its own is a sentence
        # an unfinished line: its finished sentences, or the start of a long one, can be spoken now
        if self.in_code or not self.raw:
            return
        head = self.raw.lstrip()
        if not self.line_open and (not head or head[0] in "`|"):
            return                         # maybe a code fence or a table: wait for the line
        ends = [m.end() for m in _END.finditer(self.raw)]
        cut = _balanced_cut(self.raw, ends[-1]) if ends else 0
        if not cut and len(self.raw) >= 30:
            cut = _balanced_cut(self.raw, self.raw.rfind(" ") + 1)
        if cut > 0:
            part, self.raw = self.raw[:cut], self.raw[cut:]
            if not self.line_open:
                part = _LINE_MARK.sub("", part)
            self.prose += clean_inline(part, self.lang) + " "
            self.line_open = True

    # ---- sentences ----
    def _sentences(self, final: bool) -> list[str]:
        out = []
        while True:
            m = _END.search(self.prose)
            cut = m.end() if m else -1
            if cut < 0 and self.first and len(self.prose) >= self.first_min:
                clause = None
                for c in _CLAUSE.finditer(self.prose):
                    if c.end() >= self.first_min:
                        clause = c
                        break
                cut = clause.end() if clause else -1
            if cut < 0 and len(self.prose) > self.max_len:
                cut = self.prose.rfind(" ", 0, self.max_len) + 1 or self.max_len
            if cut <= 0:
                break
            piece, self.prose = self.prose[:cut], self.prose[cut:]
            self._emit(piece, out)
        if final:
            self._emit(self.prose, out)
            self.prose = ""
        return out

    def _emit(self, piece: str, out: list[str]) -> None:
        piece = re.sub(r"\s+", " ", piece).strip()
        if not re.search(r"\w", piece):
            return
        if self.numbers:
            piece = numbers_to_words(piece, self.lang)
        out.append(piece)
        self.first = False

    def feed(self, text: str) -> list[str]:
        self.raw += text
        self._take_lines(final=False)
        return self._sentences(final=False)

    def flush(self) -> list[str]:
        self._take_lines(final=True)
        return self._sentences(final=True)


def speakable(markdown: str, lang: str, numbers: bool = True) -> list[str]:
    """A whole answer as the sentences to say."""
    stream = SpeechStream(lang, numbers=numbers)
    return stream.feed(markdown) + stream.flush()
