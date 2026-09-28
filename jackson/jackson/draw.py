# SPDX-License-Identifier: Apache-2.0
"""«Джексон, нарисуй …»: pictures made on this computer, in the Studio (ComfyUI in a container).

- :func:`parse` reads the request, anchored like the fast path: «нарисуй кота в шляпе», «сделай
  картинку …», "draw a cat in a hat". Words for the shape pick the size («вертикальную», «обои»,
  "for my phone"), «квеном» / "with qwen" the kit.
- The Studio (module studio, ``sos-studio.service``) starts when asked and stops after Jackson has
  not drawn for ``[draw] idle_minutes`` (10), so the graphics card is free for games and the local
  model. A Studio someone started by hand is left alone.
- The graphs mirror ComfyUI's own templates (Comfy-Org/workflow_templates): FLUX.2 [klein] 4B
  distilled (Apache-2.0: 4 steps, cfg 1) and Qwen-Image 2.1 (non-commercial: 25 steps). klein draws
  best from an English paragraph of 40–120 words, so its own text encoder (Qwen3 4B) first turns a
  short request in any language into one (ComfyUI's TextGenerate); the paragraph is kept, so «ещё
  вариант» only draws again. If that step fails, the request goes as it is.
- The picture is saved in ~/Pictures/Jackson (the XDG pictures folder). Nothing leaves the machine.

The kit files carry the names ``sos models pull <kit>`` links into /srv/ai/views/comfyui
(cli/svoya_cli/data/model_catalog.toml ``[[kit]]``); a test keeps the two in step.
"""

from __future__ import annotations

import base64
import datetime as dt
import http.client
import json
import logging
import os
import random
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .providers.base import CancelToken

log = logging.getLogger("jackson.draw")

STUDIO_URL = "http://127.0.0.1:8188"
UNIT = "sos-studio.service"
IMAGE = "localhost/sos-studio:latest"

Progress = Callable[..., None]           # progress(phase=…, done=…, total=…)


# ---------------------------------------------------------------------------------------------------
# kits

@dataclass(frozen=True)
class Kit:
    id: str
    name: str
    unet: str                 # diffusion_models/
    clip: str                 # text_encoders/
    vae: str                  # vae/
    steps: int
    vram_gb: float
    commercial: bool
    install: str              # `sos install …` that brings it
    enhance: bool = False     # rewrite a short request with the kit's own text encoder first

    def files(self) -> list[tuple[str, str]]:
        return [("diffusion_models", self.unet), ("text_encoders", self.clip), ("vae", self.vae)]


KLEIN = Kit("flux2-klein-4b", "FLUX.2 [klein] 4B", "flux-2-klein-4b-fp8.safetensors", "qwen_3_4b.safetensors",
            "flux2-vae.safetensors", steps=4, vram_gb=8.4, commercial=True, install="draw", enhance=True)
QWEN_IMAGE = Kit("qwen-image-2.1", "Qwen-Image 2.1", "qwen_image_2.1_int8_convrot.safetensors",
                 "qwen3vl_8b_int8_convrot.safetensors", "qwen_image_2.1_vae_bf16.safetensors", steps=25,
                 vram_gb=16, commercial=False, install="qwen-image-2.1 --accept-license")
KITS = {k.id: k for k in (KLEIN, QWEN_IMAGE)}
DEFAULT_KIT = KLEIN.id

# ≈ 1 megapixel, sides in multiples of 32 (both models' latent grids)
SIZES = {"square": (1024, 1024), "portrait": (832, 1216), "landscape": (1216, 832),
         "wide": (1344, 768), "tall": (768, 1344)}


# ---------------------------------------------------------------------------------------------------
# the request

@dataclass
class DrawRequest:
    prompt: str                       # what to draw, in the user's words (may be empty: ask what)
    size: str = "square"
    wallpaper: bool = False           # «обои», "wallpaper": the panel offers «На рабочий стол»
    kit: str | None = None            # asked for by name («квеном»)
    text: str = ""                    # the whole utterance
    describe: bool = True             # False: the prompt is already a description (the model wrote it)

    @property
    def dims(self) -> tuple[int, int]:
        return SIZES.get(self.size, SIZES["square"])


_WAKE = r"^(?:эй |ну |слушай |hey |ok |okay )?(?:{names})\b[ ,:!]*"
_LEAD = re.compile(r"^(?:(?:а|ну|так|давай|слушай|можешь|сможешь|ты можешь|could you|can you|would you|will you|"
                   r"please|pls|just|пожалуйста)\b[ ,]*)+")
_POLITE = re.compile(r"(?:,\s*)?\b(?:пожалуйста|плиз|please|pls)\b[,!.]?", re.IGNORECASE)
# «набросай», "sketch" and "illustrate" name a picture only with a picture noun («набросай эскиз
# логотипа»): «набросай письмо», "sketch out a plan", "illustrate how TCP works" are text
_DRAW = r"(?:нарисуй(?:те)?(?:-ка)?|нарисуешь|нарисовать|изобрази(?:те)?|изобразить|draw|paint)"
_MAKE = (r"(?:сделай(?:те)?|сделать|создай(?:те)?|создать|сгенерируй(?:те)?|сгенерировать|генерируй|набросай|"
         r"generate|make|create|render|sketch|illustrate)")
# "draw up a contract", "draw lots", "draw a card", "draw conclusions": English idioms, not pictures
_IDIOM = re.compile(r"^(?:draw|paint)(?: me)? (?:up|out|on|in|back|near|down|off|from|over|aside|away|together|"
                    r"lots?|straws?|(?:a |the |some |\w+ )?cards?|(?:a |the |my |your |some )?conclusions?|"
                    r"(?:a |the )?comparisons?|(?:a |the )?parallels?|(?:a |the )?distinction|attention|"
                    r"inspiration|(?:the )?curtains?|(?:a )?bath|blood|water|money|(?:a |my |the )?salary|"
                    r"(?:a )?breath|(?:a |the )?blank|(?:a |the )?crowd|fire|(?:the )?line between|"
                    r"(?:a |the |your )?own conclusions?|(?:a |the |my )?pension|(?:a |the )?sword|(?:a |the )?gun|"
                    r"a picture of (?:how|what|why|where|the situation|the problem))\b")
_WHO = r"(?: (?:мне|нам|для меня|me|us|for me),?)?"
_GENERIC = (r"(?:картинк\w*|изображени\w*|рисун\w*|рисуночек|арт|артик|иллюстраци\w*|пикч\w*|эскиз\w*|скетч\w*|"
            r"набросок|(?:an? )?(?:image|picture|pic|drawing|illustration|artwork|sketch))")
# nouns that are the subject themselves («логотип для кофейни»). Not «иконку» («создай иконку на
# рабочем столе» is a shortcut) nor a bare "cover" ("a cover letter")
_SPECIFIC = (r"(?:обо(?:и|ев|ями)|постер\w*|плакат\w*|аватар\w*|аватарк\w*|логотип\w*|лого|раскраск\w*|"
             r"обложк\w* (?:для|к) (?:книг|альбом|трек|песн|плейлист|видео|ролик)\w*|стикер\w*|открытк\w*|"
             r"(?:an? )?(?:wallpaper|poster|avatar|logo|coloring page|(?:book|album) cover|cover art|sticker|postcard))")
_LINK = r"(?: (?:of|about|with|showing|где|на котор\w+|с|со|про))?"
_RE_DRAW = re.compile(rf"^{_DRAW}{_WHO}(?: {_GENERIC}{_LINK})?(?: (?P<what>.+))?$")
_RE_MAKE = re.compile(rf"^{_MAKE}{_WHO} (?P<noun>{_GENERIC}|{_SPECIFIC})(?P<link>{_LINK})(?: (?P<what>.+))?$")
_RE_LEAD_NOUN = re.compile(rf"^{_GENERIC}{_LINK}(?: |$)")
_RE_GENERIC_NOUN = re.compile(rf"^{_GENERIC}$")
# "…and send it to Telegram": more than a picture, the model plans that (it has the image.draw tool)
_MORE = re.compile(r"\b(?:и|а потом|потом|затем|and|then|and then) (?:отправь|пришли|скинь|сохрани|вставь|перешли|"
                   r"опубликуй|выложи|send|save|post|upload|share|email)\b")

# «через квен», «квеном», "with qwen": the kit (not «Квентин Тарантино»)
_KIT_WORDS = (
    (QWEN_IMAGE.id, r"(?:(?:через|с помощью|с|со|на|в|with|using|in|on) )?(?:квен(?:ом|а|е|у)?|"
                    r"qwen(?:[- ]?image)?(?:[- ]?2(?:\.1)?)?)"),
    (KLEIN.id, r"(?:(?:через|с помощью|с|со|на|в|with|using|in|on) )?(?:флюкс(?:ом|а|е|у)?|flux(?:\.?2)?|klein|"
               r"кляйн(?:ом|а|е|у)?)"),
)
# (size, words, the words only name the format: leave them out of the description)
_SIZE_WORDS = (
    ("tall", r"(?:для телефона|на телефон|для сторис|в сторис|сторис|stories|for (?:my |a |the )?phone|"
             r"phone wallpaper|9:16|9 на 16)", True),
    ("wide", r"(?:(?:на |для )?рабоч(?:ий|его|ем) стол\w*|обо(?:и|ев|ями)|(?:desktop )?wallpaper|desktop background|"
             r"широкоформатн\w*|widescreen|16:9|16 на 9)", True),
    ("wide", r"(?:панорам\w*|panoram\w*)", False),
    ("portrait", r"(?:вертикальн\w*|книжн\w*|vertical|portrait orientation|2:3)", True),
    ("portrait", r"(?:портрет\w*|portrait)", False),
    ("landscape", r"(?:горизонтальн\w*|альбомн\w*|horizontal|landscape orientation|3:2)", True),
    ("landscape", r"(?:пейзаж\w*|landscape)", False),
    ("square", r"(?:квадратн\w*|square format|1:1)", True),
)
_WALLPAPER = re.compile(r"(?:рабоч(?:ий|его|ем) стол|обо(?:и|ев|ями)|wallpaper|desktop background)")


def _clean(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip(" ,;:-—–")
    return s.rstrip(".!?…").strip()


def _cut(text: str, start: int, end: int) -> str:
    return re.sub(r"\s+", " ", text[:start] + " " + text[end:]).strip()


def parse(text: str, names: tuple[str, ...] = ()) -> DrawRequest | None:
    """A request to draw → what, which size, which kit; anything else → None."""
    raw = re.sub(r"\s+", " ", text.strip())
    if not raw or "\n" in text.strip():
        return None
    low = raw.lower().replace("ё", "е")
    if len(low) != len(raw):          # a letter whose lower case is longer: keep indexes honest
        raw = low
    alts = "|".join(["джексон", "jackson", *(re.escape(n.lower().replace("ё", "е")) for n in names if n)])
    wake = re.compile(_WAKE.format(names=alts))
    for _ in range(3):
        before = low
        for pat in (wake, _LEAD):
            m = pat.match(low)
            if m and m.end():
                raw, low = raw[m.end():], low[m.end():]
        if low == before:
            break
    for a, b in reversed([x.span() for x in _POLITE.finditer(low)]):     # «нарисуй мне, пожалуйста, …»
        raw, low = raw[:a] + " " + raw[b:], low[:a] + " " + low[b:]
    raw, low = re.sub(r"\s+", " ", raw).strip(), re.sub(r"\s+", " ", low).strip()
    n = len(low.rstrip(" .!?…"))
    raw, low = raw[:n], low[:n]
    if _IDIOM.match(low):
        return None
    m = _RE_DRAW.match(low)
    if m is not None:
        what = raw[m.start("what"):] if m.group("what") else ""
    else:
        m = _RE_MAKE.match(low)
        if m is None:
            return None
        if _RE_GENERIC_NOUN.match(m.group("noun")):
            what = raw[m.start("what"):] if m.group("what") else ""
        else:                          # «логотип для кофейни», "a coloring page with a dragon": the noun is the subject
            what = raw[m.start("noun"):]
    if _MORE.search(what.lower()):
        return None
    req = DrawRequest("", text=text.strip())
    for kit, pat in _KIT_WORDS:
        km = re.search(rf"(?:^|\s){pat}(?=$|[\s,.!?])", what.lower().replace("ё", "е"))
        if km:
            req.kit = kit
            what = _cut(what, km.start(), km.end())
            break
    for size, pat, format_only in _SIZE_WORDS:
        sm = re.search(rf"(?:^|\s)(?:(?:an?|the|my) )?{pat}(?=$|[\s,.!?])", what.lower().replace("ё", "е"))
        if sm:
            req.size = size
            req.wallpaper = size in ("wide", "tall") and bool(_WALLPAPER.search(sm.group(0)))
            if format_only:
                what = _cut(what, sm.start(), sm.end())
            break
    what = _clean(_POLITE.sub(" ", what))
    # «нарисуй вертикальную картинку кота»: once the shape word is out, a generic noun may lead
    lead = _RE_LEAD_NOUN.match(what.lower().replace("ё", "е"))
    if lead:
        what = _clean(what[lead.end():])
    what = _clean(re.sub(r"^(?:с|со|with|of|про|about)\s+", "", what, flags=re.IGNORECASE)) if req.wallpaper else what
    req.prompt = what
    return req


_NOT_AN_ANSWER = re.compile(r"^(?:не надо|ничего|отмена|отмени|забудь|неважно|передумал\w*|стоп|"
                            r"cancel|never ?mind|nothing|forget it|stop)\b|\?$", re.IGNORECASE)
_QUESTION_WORD = re.compile(r"^(?:почему|зачем|как|какой|какая|какие|где|когда|сколько|кто|что такое|"
                            r"why|how|what is|what's|where|when|who)\b", re.IGNORECASE)


def answer_to_what(text: str, pending: DrawRequest) -> DrawRequest | None:
    """The reply to «Что нарисовать?»: «кота в шляпе» is the picture; a question, a command or
    «не надо» is not."""
    t = _clean(_POLITE.sub(" ", re.sub(r"\s+", " ", text.strip())))
    if not t or "\n" in text.strip() or len(t.split()) > 25 or _NOT_AN_ANSWER.search(t) or _QUESTION_WORD.match(t):
        return None
    req = parse(t) or DrawRequest(t, text=text.strip())
    if not req.prompt:
        return None
    if req.size == "square" and pending.size != "square":
        req.size, req.wallpaper = pending.size, pending.wallpaper
    req.kit = req.kit or pending.kit
    return req


# ---------------------------------------------------------------------------------------------------
# graphs (ComfyUI API format)

ENHANCE_SYSTEM = (
    "You write prompts for an image generator. Rewrite the user's request as one English paragraph of "
    "40 to 90 words that describes the finished picture: the subject first, then the setting, composition, "
    "lighting, colors and style. Keep every detail the user gave and the style they name (a photo, "
    "watercolor, pixel art, a black-and-white coloring page with clean outlines, a logo). Add only what makes "
    "the picture concrete. Do not add text or letters to the picture unless the user asks for them. "
    "Answer with the paragraph only.")


def graph_enhance(kit: Kit, request: str, seed: int = 0) -> dict[str, Any]:
    """The kit's text encoder (Qwen3 4B for klein) writes the description: TextGenerate → PreviewAny.
    Sampling as Qwen3 advises for answers without thinking (greedy decoding can loop)."""
    return {
        "71": {"class_type": "CLIPLoader", "inputs": {"clip_name": kit.clip, "type": "flux2", "device": "default"}},
        "82": {"class_type": "PrimitiveStringMultiline", "inputs": {"value": ENHANCE_SYSTEM}},
        "80": {"class_type": "TextGenerate", "inputs": {
            "clip": ["71", 0], "prompt": request, "max_length": 220,
            "sampling_mode": "on", "sampling_mode.temperature": 0.7, "sampling_mode.top_k": 20,
            "sampling_mode.top_p": 0.8, "sampling_mode.min_p": 0.0, "sampling_mode.repetition_penalty": 1.05,
            "sampling_mode.seed": seed, "thinking": False, "use_default_template": True, "system_prompt": ["82", 0]}},
        "81": {"class_type": "PreviewAny", "inputs": {"source": ["80", 0]}},
    }


def graph_klein(kit: Kit, prompt: str, width: int, height: int, seed: int) -> dict[str, Any]:
    """image_flux2_klein_text_to_image (distilled): 4 steps, cfg 1, an empty negative."""
    return {
        "70": {"class_type": "UNETLoader", "inputs": {"unet_name": kit.unet, "weight_dtype": "default"}},
        "71": {"class_type": "CLIPLoader", "inputs": {"clip_name": kit.clip, "type": "flux2", "device": "default"}},
        "72": {"class_type": "VAELoader", "inputs": {"vae_name": kit.vae}},
        "74": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["71", 0], "text": prompt}},
        "76": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["74", 0]}},
        "63": {"class_type": "CFGGuider", "inputs": {"model": ["70", 0], "positive": ["74", 0],
                                                     "negative": ["76", 0], "cfg": 1}},
        "61": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "62": {"class_type": "Flux2Scheduler", "inputs": {"steps": kit.steps, "width": width, "height": height}},
        "73": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "66": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "64": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["73", 0], "guider": ["63", 0],
                                                                 "sampler": ["61", 0], "sigmas": ["62", 0],
                                                                 "latent_image": ["66", 0]}},
        "65": {"class_type": "VAEDecode", "inputs": {"samples": ["64", 0], "vae": ["72", 0]}},
        "9": {"class_type": "PreviewImage", "inputs": {"images": ["65", 0]}},
    }


def graph_qwen_image(kit: Kit, prompt: str, width: int, height: int, seed: int) -> dict[str, Any]:
    """image_qwen_image_2_1_t2i without its optional prompt rewriter: 25 steps, euler/simple, cfg 1."""
    return {
        "451": {"class_type": "UNETLoader", "inputs": {"unet_name": kit.unet, "weight_dtype": "default"}},
        "480": {"class_type": "QwenImage21Cache", "inputs": {"model": ["451", 0], "device": "auto", "dtype": "default"}},
        "453": {"class_type": "CLIPLoader", "inputs": {"clip_name": kit.clip, "type": "qwen_image", "device": "default"}},
        "454": {"class_type": "VAELoader", "inputs": {"vae_name": kit.vae}},
        "452": {"class_type": "TextEncodeQwenImage21", "inputs": {"clip": ["453", 0], "prompt": prompt,
                                                                  "negative_prompt": "", "resolution": 1024}},
        "456": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "458": {"class_type": "KSampler", "inputs": {"model": ["480", 0], "positive": ["452", 0], "negative": ["452", 1],
                                                     "latent_image": ["456", 0], "seed": seed, "steps": kit.steps,
                                                     "cfg": 1, "sampler_name": "euler", "scheduler": "simple",
                                                     "denoise": 1}},
        "457": {"class_type": "VAEDecode", "inputs": {"samples": ["458", 0], "vae": ["454", 0]}},
        "9": {"class_type": "PreviewImage", "inputs": {"images": ["457", 0]}},
    }


def graph_for(kit: Kit, prompt: str, width: int, height: int, seed: int) -> dict[str, Any]:
    return (graph_qwen_image if kit.id == QWEN_IMAGE.id else graph_klein)(kit, prompt, width, height, seed)


# what a node doing its work means for people
PHASES = {"UNETLoader": "load", "CLIPLoader": "load", "VAELoader": "load", "TextGenerate": "think",
          "CLIPTextEncode": "read", "TextEncodeQwenImage21": "read", "SamplerCustomAdvanced": "draw",
          "KSampler": "draw", "VAEDecode": "finish", "PreviewImage": "finish"}


# ---------------------------------------------------------------------------------------------------
# ComfyUI over HTTP (+ a minimal WebSocket reader for progress; stdlib only)

class StudioError(Exception):
    """code: not-installed | no-kit | not-built | old-studio | no-start | gone | rejected | failed | oom |
    timeout | cancelled"""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class WebSocket:
    """Enough of RFC 6455 to read ComfyUI's status messages on localhost."""

    def __init__(self, sock: socket.socket, pending: bytes = b"") -> None:
        self.sock = sock
        self.buf = pending
        self._parts: list[bytes] = []
        self._opcode = 0

    @classmethod
    def connect(cls, url: str, path: str, timeout: float = 3.0) -> "WebSocket":
        u = urllib.parse.urlsplit(url)
        host, port = u.hostname or "127.0.0.1", u.port or 80
        sock = socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        sock.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
                      f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
                     .encode("ascii"))
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                sock.close()
                raise OSError("no WebSocket handshake")
            buf += chunk
            if len(buf) > 65536:
                sock.close()
                raise OSError("WebSocket handshake too long")
        head, rest = buf.split(b"\r\n\r\n", 1)
        status = head.split(b"\r\n", 1)[0]
        if b" 101" not in status:
            sock.close()
            raise OSError(f"no WebSocket: {status.decode('latin-1', 'replace')}")
        return cls(sock, rest)

    def _need(self, n: int) -> None:
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise EOFError("WebSocket closed")
            self.buf += chunk

    def _frame(self) -> tuple[bool, int, bytes]:
        self._need(2)
        b0, b1 = self.buf[0], self.buf[1]
        n, off = b1 & 0x7F, 2
        if n == 126:
            self._need(4)
            n, off = int.from_bytes(self.buf[2:4], "big"), 4
        elif n == 127:
            self._need(10)
            n, off = int.from_bytes(self.buf[2:10], "big"), 10
        mask = b""
        if b1 & 0x80:
            self._need(off + 4)
            mask, off = self.buf[off:off + 4], off + 4
        self._need(off + n)
        payload, self.buf = self.buf[off:off + n], self.buf[off + n:]
        if mask:
            payload = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
        return bool(b0 & 0x80), b0 & 0x0F, payload

    def _send(self, opcode: int, payload: bytes = b"") -> None:
        mask = os.urandom(4)
        n = len(payload)
        head = bytes([0x80 | opcode])
        head += bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + n.to_bytes(2, "big")
        self.sock.sendall(head + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(payload)))

    def recv(self) -> tuple[int, bytes]:
        """The next message (opcode 1 text, 2 binary); raises socket.timeout / EOFError."""
        while True:
            fin, op, payload = self._frame()
            if op == 0x9:                                   # ping
                self._send(0xA, payload)
                continue
            if op == 0xA:
                continue
            if op == 0x8:
                raise EOFError("WebSocket closed")
            if op in (0x1, 0x2):
                self._opcode, self._parts = op, [payload]
            elif op == 0x0:
                self._parts.append(payload)
            if fin:
                return self._opcode, b"".join(self._parts)

    def settimeout(self, t: float) -> None:
        self.sock.settimeout(t)

    def close(self) -> None:
        try:
            self._send(0x8)
        except OSError:
            pass
        self.sock.close()


class Comfy:
    def __init__(self, url: str = STUDIO_URL, timeout: float = 10.0, poll: float = 1.0) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.poll = poll                          # seconds between history reads without a WebSocket
        self._op = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # localhost: never a proxy

    def _call(self, method: str, path: str, body: Any = None, timeout: float | None = None) -> bytes:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"} if data is not None else {})
        try:
            with self._op.open(req, timeout=timeout or self.timeout) as r:
                return r.read()
        except http.client.HTTPException as e:       # a Studio going away mid-answer
            raise OSError(f"{e.__class__.__name__}: {e}") from None

    def alive(self) -> bool:
        try:
            self._call("GET", "/system_stats", timeout=2.0)
            return True
        except (OSError, urllib.error.URLError, ValueError):
            return False

    def submit(self, graph: dict[str, Any], client_id: str) -> str:
        try:
            out = json.loads(self._call("POST", "/prompt", {"prompt": graph, "client_id": client_id}))
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read().decode("utf-8", "replace"))
            except (OSError, ValueError):
                err = {}
            raise StudioError("rejected", _node_errors(err) or f"HTTP {e.code}") from None
        except (OSError, urllib.error.URLError, ValueError) as e:
            raise StudioError("failed", str(e)) from None
        pid = out.get("prompt_id")
        if not pid:
            raise StudioError("rejected", _node_errors(out) or "no prompt id")
        return str(pid)

    def history(self, pid: str) -> dict[str, Any] | None:
        """The prompt's history entry; {} while it runs; None when the Studio does not answer."""
        try:
            data = json.loads(self._call("GET", f"/history/{urllib.parse.quote(pid)}"))
        except (OSError, urllib.error.URLError, ValueError):
            return None
        entry = data.get(pid) if isinstance(data, dict) else None
        return entry if isinstance(entry, dict) else {}

    def view(self, ref: dict[str, Any]) -> bytes:
        q = urllib.parse.urlencode({"filename": ref.get("filename", ""), "subfolder": ref.get("subfolder", ""),
                                    "type": ref.get("type", "output")})
        return self._call("GET", f"/view?{q}", timeout=60)

    def cancel(self, pid: str) -> None:
        for path, body in (("/queue", {"delete": [pid]}), ("/interrupt", {"prompt_id": pid})):
            try:
                self._call("POST", path, body, timeout=3)
            except (OSError, urllib.error.URLError):
                pass

    def free(self) -> None:
        try:
            self._call("POST", "/free", {"unload_models": True, "free_memory": True}, timeout=5)
        except (OSError, urllib.error.URLError):
            pass

    def _queue(self) -> dict[str, Any] | None:
        try:
            q = json.loads(self._call("GET", "/queue", timeout=3))
        except (OSError, urllib.error.URLError, ValueError):
            return None
        return q if isinstance(q, dict) else None

    def queue_size(self) -> int:
        q = self._queue() or {}
        return len(q.get("queue_running") or []) + len(q.get("queue_pending") or [])

    def queued(self, pid: str) -> bool | None:
        """Is the prompt waiting or running? (None: the Studio does not say.) Items are
        [number, prompt_id, …]."""
        q = self._queue()
        if q is None:
            return None
        items = list(q.get("queue_running") or []) + list(q.get("queue_pending") or [])
        return any(isinstance(it, list) and len(it) > 1 and it[1] == pid for it in items)

    def watch(self, client_id: str) -> WebSocket | None:
        try:
            return WebSocket.connect(self.url, f"/ws?clientId={urllib.parse.quote(client_id)}")
        except (OSError, ValueError):
            return None

    def run(self, graph: dict[str, Any], cancel: CancelToken, progress: Progress | None = None,
            timeout: float = 900.0) -> dict[str, Any]:
        """Queue *graph*, follow it, → its outputs ({node: {"images": […], "text": […]}})."""
        cid = base64.urlsafe_b64encode(os.urandom(9)).decode("ascii")
        ws = self.watch(cid)                     # before the prompt, so no message is missed
        started = time.monotonic()
        nodes = {k: v.get("class_type", "") for k, v in graph.items()}
        try:
            pid = self.submit(graph, cid)
            return self._follow(pid, nodes, ws, cancel, progress, started, timeout)
        finally:
            if ws is not None:
                ws.close()

    def _follow(self, pid: str, nodes: dict[str, str], ws: WebSocket | None, cancel: CancelToken,
                progress: Progress | None, started: float, timeout: float) -> dict[str, Any]:
        last_poll = 0.0
        phase = ""
        finished = False                          # ComfyUI said it is done; the history follows a moment later
        unanswered = 0                            # history reads in a row the Studio did not answer
        lost = 0                                  # looks in a row that found the prompt nowhere (a restarted Studio)
        empty = 0

        def tell(p: str, **kw: Any) -> None:
            nonlocal phase
            if p == phase and not kw:
                return
            phase = p
            if progress is not None:
                try:
                    progress(phase=p, **kw)
                except Exception:  # a vanished client must not stop the picture
                    log.debug("progress callback failed", exc_info=True)

        if ws is not None:
            ws.settimeout(1.0)
        while True:
            if cancel.is_set():                   # the stop button: out of the queue, or interrupted
                self.cancel(pid)
                raise StudioError("cancelled")
            if time.monotonic() - started > timeout:
                self.cancel(pid)
                raise StudioError("timeout", f"{int(timeout)} s")
            msg = None
            if ws is not None:
                try:
                    op, payload = ws.recv()
                    if op == 1:
                        msg = json.loads(payload.decode("utf-8", "replace"))
                except socket.timeout:
                    pass
                except (OSError, EOFError, ValueError):
                    ws = None                     # fall back to polling the history
            else:
                cancel.wait(min(0.5, self.poll))
            if isinstance(msg, dict):
                data = msg.get("data") if isinstance(msg.get("data"), dict) else {}
                if data.get("prompt_id") not in (None, pid):
                    continue
                kind = msg.get("type")
                if kind == "execution_start":
                    tell("start")
                elif kind == "executing" and data.get("node") is not None:
                    tell(PHASES.get(nodes.get(str(data.get("node")), ""), phase or "start"))
                elif kind == "progress" and PHASES.get(nodes.get(str(data.get("node")), "")) == "draw":
                    tell("draw", done=int(data.get("value") or 0), total=int(data.get("max") or 0))
                elif kind == "execution_error":
                    raise _failure(data)
                elif kind == "execution_interrupted":
                    raise StudioError("cancelled")
                elif kind == "execution_success":
                    finished = True               # the history is written right after this message
                    if ws is not None:
                        ws.settimeout(0.1)
                elif kind == "executing" and data.get("node") is None and data.get("prompt_id") == pid:
                    finished, last_poll = True, 0.0     # sent after the history is written: read it now
            now = time.monotonic()
            if now - last_poll >= (0.1 if finished else self.poll if ws is None else 3.0):
                last_poll = now
                h = self.history(pid)
                if h is None:
                    unanswered += 1
                    if unanswered >= 3 and not self.alive():
                        raise StudioError("gone")
                    continue
                unanswered = 0
                if not h and not finished:
                    empty += 1
                    if empty % 3 == 0:            # neither in the history nor in the queue: forgotten
                        lost = lost + 1 if self.queued(pid) is False else 0
                        if lost >= 2:
                            raise StudioError("gone", "the prompt is no longer in the Studio's queue")
                if h:
                    st = h.get("status") or {}
                    if st.get("status_str") == "error":
                        err = next((m[1] for m in st.get("messages", []) if m and m[0] == "execution_error"), {})
                        raise _failure(err if isinstance(err, dict) else {})
                    if st.get("completed") or st.get("status_str") == "success" or h.get("outputs"):
                        return h.get("outputs") or {}
                elif ws is None and not phase:
                    tell("queue" if self.queue_size() > 1 else "start")


def _node_errors(err: dict[str, Any]) -> str:
    parts = []
    e = err.get("error")
    if isinstance(e, dict) and e.get("message"):
        parts.append(str(e["message"]))
    for node, ne in (err.get("node_errors") or {}).items():
        for x in (ne.get("errors") or [])[:2]:
            parts.append(f"{ne.get('class_type', node)}: {x.get('message', '')} {x.get('details', '')}".strip())
    return "; ".join(parts)[:400]


def _failure(data: dict[str, Any]) -> StudioError:
    text = f"{data.get('exception_type', '')}: {data.get('exception_message', '')}".strip(": ")
    if re.search(r"out of memory|OutOfMemory|CUDA error: out of memory|HIP out of memory", text, re.IGNORECASE):
        return StudioError("oom", text[:300])
    return StudioError("failed", (f"{data.get('node_type')}: " if data.get("node_type") else "") + text[:300])


def clean_description(text: str) -> str | None:
    """The text encoder's paragraph, or None when it does not look like one."""
    t = re.sub(r"<think>.*?</think>", " ", text or "", flags=re.S)
    if "<|" in t:                                  # the chat template leaked: the generation went astray
        return None
    t = re.sub(r"^\s*(?:prompt|description|here is[^:]*):\s*", "", t.strip(), flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip().strip('"“”«»\'').strip()
    words = t.split()
    if len(words) < 6 or len(words) > 220 or "<" in t:
        return None
    if len(words) >= 30 and len({w.lower().strip(".,;:") for w in words}) < len(words) * 0.35:
        return None                                # the same few words over and over: a loop
    return t


# ---------------------------------------------------------------------------------------------------
# the service

@dataclass
class Result:
    ok: bool
    code: str = ""                    # the StudioError code when not ok
    path: Path | None = None
    prompt: str = ""                  # the description the picture was drawn from
    kit: str = ""
    seconds: float = 0.0
    size: tuple[int, int] = (0, 0)
    detail: str = ""
    install: str = ""                 # `sos install …` that fixes it
    notes: list[str] = field(default_factory=list)


def ai_root(env: dict[str, str] | None = None) -> Path:
    e = os.environ if env is None else env
    return Path(e.get("SVOYA_AI_ROOT") or e.get("HF_HOME") or "/srv/ai")


class Drawer:
    """One drawing at a time; starts the Studio on demand and stops it when idle.

    *marker* (a file in the runtime folder) remembers that this Jackson started the Studio, so a
    Jackson started again after a crash still stops it when idle; a Studio started by hand is left
    alone."""

    def __init__(self, runner: Any, pictures: Callable[[], Path], settings: dict[str, Any] | None = None,
                 views: Path | None = None, comfy: Comfy | None = None, marker: Path | None = None,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> None:
        self.runner = runner
        self.pictures = pictures
        self.settings = dict(settings or {})
        self.views = views or ai_root() / "views" / "comfyui"
        self.comfy = comfy or Comfy(str(self.settings.get("url") or STUDIO_URL))
        self.marker = marker
        self.clock = clock
        self.sleep = sleep
        self._lock = threading.Lock()
        self._described: dict[str, str] = {}          # request → the text encoder's paragraph
        self._idle: threading.Timer | None = None
        self.last_used = 0.0
        self._started_here = bool(marker is not None and marker.exists())
        if self._started_here:
            self._arm_idle()                           # left running by a Jackson that crashed

    @property
    def started_here(self) -> bool:
        return self._started_here

    @started_here.setter
    def started_here(self, value: bool) -> None:
        self._started_here = value
        if self.marker is None:
            return
        try:
            if value:
                self.marker.parent.mkdir(parents=True, exist_ok=True)
                self.marker.write_text("sos-studio.service\n", encoding="utf-8")
            else:
                self.marker.unlink(missing_ok=True)
        except OSError:
            pass

    # --- what is there ------------------------------------------------------------------------
    def installed(self) -> bool:
        return self.runner.which("sos-studio") is not None or Path("/usr/local/bin/sos-studio").exists()

    def missing(self, kit: Kit) -> list[str]:
        out = []
        for folder, name in kit.files():
            p = self.views / folder / name
            if not p.exists():                # a dangling link is missing too
                out.append(f"{folder}/{name}")
        return out

    def kit_for(self, req: DrawRequest) -> tuple[Kit, str]:
        """(the kit to draw with, the id of the kit asked for when it is not installed and klein draws)."""
        wanted = req.kit or str(self.settings.get("kit") or "") or DEFAULT_KIT
        kit = KITS.get(wanted, KLEIN)
        if kit is not KLEIN and self.missing(kit) and not self.missing(KLEIN):
            return KLEIN, kit.id
        return kit, ""

    def status(self) -> dict[str, Any]:
        return {"installed": self.installed(), "running": self.comfy.alive(),
                "kits": {k.id: not self.missing(k) for k in KITS.values()}, "startedHere": self.started_here}

    # --- the Studio ---------------------------------------------------------------------------
    def _built(self) -> bool:
        if self.runner.which("podman") is None:
            return True                        # cannot tell: let the start say
        return self.runner.run(["podman", "image", "exists", IMAGE], timeout=20).ok

    def ensure_running(self, cancel: CancelToken, progress: Progress | None, wait: float = 240.0) -> None:
        if self.comfy.alive():
            return
        if not self._built():
            raise StudioError("not-built")
        if progress is not None:
            progress(phase="studio")
        res = self.runner.run(["systemctl", "--user", "start", "--no-block", UNIT], timeout=10)
        if not res.ok:
            text = f"{res.out}\n{res.err}".lower()
            if "not found" in text or "not-found" in text or "no such" in text:
                raise StudioError("old-studio")        # a Studio from before the user unit
            raise StudioError("no-start", res.why())
        self.started_here = True
        deadline = self.clock() + wait
        while self.clock() < deadline:
            if cancel.is_set():
                raise StudioError("cancelled")
            if self.comfy.alive():
                return
            self.sleep(1.0)
        raise StudioError("no-start")

    def _stop(self, block: bool = True) -> None:
        self.runner.run(["systemctl", "--user", "stop", *([] if block else ["--no-block"]), UNIT], timeout=30)
        self.started_here = False

    def stop_if_idle(self) -> bool:
        """Stop the Studio this Jackson started, when nothing is drawing (the idle timer). Busy with
        a job of its own (the web page): look again later."""
        if not self.started_here:
            return False
        if not self._lock.acquire(blocking=False):
            self._arm_idle()
            return False
        try:
            if self.comfy.queue_size() > 0:
                self._arm_idle()
                return False
            self._stop()
            log.info("Studio stopped after %s idle minutes", self._idle_minutes())
            return True
        finally:
            self._lock.release()

    def _idle_minutes(self) -> float:
        try:
            return max(0.0, float(self.settings.get("idle_minutes", 10) or 0))
        except (TypeError, ValueError):
            return 10.0

    def _arm_idle(self) -> None:
        minutes = self._idle_minutes()
        if self._idle is not None:
            self._idle.cancel()
        if minutes <= 0 or not self.started_here:
            return
        self._idle = threading.Timer(minutes * 60, self.stop_if_idle)
        self._idle.daemon = True
        self._idle.start()

    def close(self) -> None:
        """Jackson stops: the Studio he started goes too (the graphics card is not left taken)."""
        if self._idle is not None:
            self._idle.cancel()
        if self.started_here and self._idle_minutes() > 0:
            self._stop(block=False)

    # --- drawing --------------------------------------------------------------------------------
    def describe(self, kit: Kit, request: str, cancel: CancelToken, progress: Progress | None) -> str:
        """klein reads an English paragraph best: its own text encoder writes one (kept per request)."""
        words = request.split()
        if not kit.enhance or self.settings.get("enhance") is False or \
                (len(words) >= 30 and not re.search(r"[А-Яа-яЁё]", request)):
            return request
        key = f"{kit.id}\n{request.strip().lower()}"
        if key in self._described:
            return self._described[key]
        try:
            out = self.comfy.run(graph_enhance(kit, request, random.getrandbits(32)), cancel, progress, timeout=300)
        except StudioError as e:
            if e.code == "cancelled":
                raise
            log.info("the description step failed (%s); drawing from the request itself", e)
            return request
        texts = [t for node in out.values() for t in (node.get("text") or []) if isinstance(t, str)]
        text = clean_description(texts[0]) if texts else None
        if text is None:
            return request
        if len(self._described) > 64:
            self._described.pop(next(iter(self._described)))
        self._described[key] = text
        return text

    def draw(self, req: DrawRequest, cancel: CancelToken, progress: Progress | None = None) -> Result:
        with self._lock:
            return self._draw(req, cancel, progress)

    def _draw(self, req: DrawRequest, cancel: CancelToken, progress: Progress | None) -> Result:
        start = self.clock()
        kit, instead_of = self.kit_for(req)
        notes = [f"instead-of:{instead_of}"] if instead_of else []
        if not self.installed():
            return Result(False, "not-installed", kit=kit.id, install=kit.install)
        gone = self.missing(kit)
        if gone:
            return Result(False, "no-kit", kit=kit.id, install=kit.install, detail=", ".join(gone))
        width, height = req.dims
        try:
            self.ensure_running(cancel, progress)
            prompt = self.describe(kit, req.prompt, cancel, progress) if req.describe else req.prompt
            seed = random.getrandbits(32)
            try:
                out = self.comfy.run(graph_for(kit, prompt, width, height, seed), cancel, progress)
            except StudioError as e:
                if e.code != "oom":
                    raise
                # the card is busy with something else (a game, the local model): once more, freed
                self.comfy.free()
                out = self.comfy.run(graph_for(kit, prompt, width, height, seed), cancel, progress)
            images = [ref for node in out.values() for ref in (node.get("images") or [])]
            if not images:
                raise StudioError("failed", "no picture in the output")
            data = self.comfy.view(images[0])
            path = self._save(req, data)
        except StudioError as e:
            return Result(False, e.code, kit=kit.id, detail=e.detail,
                          install=kit.install if e.code in ("not-built", "old-studio") else "",
                          seconds=self.clock() - start, notes=notes)
        except OSError as e:
            return Result(False, "failed", kit=kit.id, detail=str(e), seconds=self.clock() - start, notes=notes)
        except Exception as e:  # a bug here must not end the turn as an internal error
            log.exception("drawing failed")
            return Result(False, "failed", kit=kit.id, detail=f"{e.__class__.__name__}: {e}",
                          seconds=self.clock() - start, notes=notes)
        finally:
            self.last_used = self.clock()
            self._arm_idle()
        return Result(True, path=path, prompt=prompt, kit=kit.id, seconds=self.clock() - start,
                      size=(width, height), notes=notes)

    def _save(self, req: DrawRequest, data: bytes) -> Path:
        folder = Path(str(self.settings.get("folder") or "")).expanduser() if self.settings.get("folder") \
            else self.pictures() / "Jackson"
        folder.mkdir(parents=True, exist_ok=True)
        ext = ".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else ".webp" if data[8:12] == b"WEBP" else ".jpg"
        stem = f"{dt.datetime.now():%Y-%m-%d %H-%M-%S} {slug(req.prompt)}".strip()
        path = folder / f"{stem}{ext}"
        n = 2
        while path.exists():
            path = folder / f"{stem} {n}{ext}"
            n += 1
        tmp = path.with_name(path.name + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, path)
        return path


def slug(text: str, limit: int = 48) -> str:
    """A file name from the request: letters, digits, spaces; «кот в шляпе»."""
    s = re.sub(r"[^\w\s-]", " ", text, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0] or s[:limit]
    return s or "picture"
