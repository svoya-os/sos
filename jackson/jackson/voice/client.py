# SPDX-License-Identifier: Apache-2.0
"""jacksond's side of voice: the link to the voice service and the conversation on top of it.

:class:`VoiceLink` keeps a connection to ``svoya-voice`` (it comes and goes with the voice module).
:class:`VoiceDesk` turns a client's ``listen`` into a recording, the transcript into a turn, the
turn's answer into sentences for the voice, and — in conversation mode — listens again after the
answer has been said. Standard library only.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from ..i18n import t
from .speech import SpeechStream

log = logging.getLogger("jackson.voice")

Event = dict[str, Any]


class VoiceLink:
    """A connection to the voice service that comes back by itself."""

    def __init__(self, path: Path, on_event: Callable[[Event], Awaitable[None]],
                 on_change: Callable[[], None] | None = None, retry_s: float = 3.0) -> None:
        self.path = Path(path)
        self.on_event = on_event
        self.on_change = on_change or (lambda: None)
        self.retry_s = retry_s
        self.writer: asyncio.StreamWriter | None = None
        self.status: Event = {}

    @property
    def ready(self) -> bool:
        return self.writer is not None and bool(self.status.get("ready"))

    @property
    def reads_numbers(self) -> bool:
        return bool(self.status.get("readsNumbers"))

    async def send(self, msg: Event) -> bool:
        if self.writer is None:
            return False
        try:
            self.writer.write(json.dumps(msg, ensure_ascii=False).encode() + b"\n")
            await self.writer.drain()
            return True
        except (ConnectionError, RuntimeError, OSError):
            return False

    def _set_status(self, status: Event) -> None:
        before = self.ready
        self.status = status
        if self.ready != before:
            self.on_change()

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            if self.path.exists():
                try:
                    reader, writer = await asyncio.open_unix_connection(str(self.path))
                except OSError:
                    reader = None
                if reader is not None:
                    self.writer = writer
                    await self.send({"type": "status"})
                    poll = asyncio.get_running_loop().create_task(self._poll(stop))
                    try:
                        await self._read(reader)
                    finally:
                        poll.cancel()
                        self.writer = None
                        self._set_status({})
                        try:
                            writer.close()
                        except Exception:  # noqa: BLE001
                            pass
                        await self.on_event({"type": "gone"})
            try:
                await asyncio.wait_for(stop.wait(), timeout=self.retry_s)
            except asyncio.TimeoutError:
                pass

    async def _poll(self, stop: asyncio.Event) -> None:
        """The service loads its models after it starts: ask until it is ready, then now and then."""
        while not stop.is_set():
            await asyncio.sleep(2.0 if not self.status.get("ready") else 30.0)
            await self.send({"type": "status"})

    async def _read(self, reader: asyncio.StreamReader) -> None:
        while True:
            try:
                raw = await reader.readline()
            except (ConnectionError, OSError, ValueError):
                return
            if not raw:
                return
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(msg, dict):
                continue
            if msg.get("type") == "status":
                self._set_status(msg)
                continue
            try:
                await self.on_event(msg)
            except Exception:  # noqa: BLE001 - a bad event must not end the link
                log.exception("voice event %r failed", msg.get("type"))


# «всё», «спасибо», "that's all" said after an answer: the conversation is over
BYE = re.compile(r"^\W*(?:джексон\W*)?(?:всё|все|хватит|стоп|спасибо|пока|отбой|достаточно|на этом всё|"
                 r"всё,? спасибо|спасибо,? всё|that'?s all|that'?s it|thanks|thank you|stop|bye|goodbye|"
                 r"never mind)\W*(?:джексон)?\W*$", re.IGNORECASE)


def guess_lang(text: str, default: str = "ru") -> str:
    letters = re.findall(r"[^\W\d_]", text)
    if not letters:
        return default
    cyr = sum(1 for c in letters if "а" <= c.lower() <= "я" or c.lower() == "ё")
    return "ru" if cyr / len(letters) >= 0.3 else "en"


@dataclass
class Talk:
    """One answer being said."""
    id: str
    client: Any
    lang: str
    voice: str
    stream: SpeechStream
    follow: bool
    finished: bool = False       # the turn is over (done/error)
    spoken: bool = False         # the voice has said everything
    hushed: bool = False         # silenced: nothing more of it is said
    ok: bool = True
    said: int = 0
    started: float = field(default_factory=time.monotonic)


@dataclass
class Listening:
    id: str
    client: Any
    mode: str


class VoiceDesk:
    """Listening and speaking for jacksond's clients (see :mod:`jackson.voice`)."""

    def __init__(self, link_path: Path, *, config: Callable[[], dict[str, Any]],
                 ask: Callable[[Any, Event], Awaitable[None]], send: Callable[[Any, Event], None],
                 broadcast: Callable[[Event], None], state: Callable[[str, str, str], Event],
                 voice_for: Callable[[Any], str], cancel: Callable[[Any], None] | None = None,
                 on_ready_change: Callable[[], None] | None = None, installed: Callable[[], bool] | None = None,
                 start_service: Callable[[], Awaitable[None]] | None = None,
                 unit_failed: Callable[[], Awaitable[bool]] | None = None, start_timeout: float = 120.0) -> None:
        self.link = VoiceLink(link_path, self._on_voice, on_ready_change)
        self.config = config
        self.ask = ask
        self.send = send
        self.broadcast = broadcast
        self.state = state                  # (turn id, state, mood) → a `state` event
        self.voice_for = voice_for          # client → voice id (the persona's)
        self.cancel = cancel or (lambda client: None)   # ends the client's running turn
        self.installed = installed or (lambda: False)   # the voice module is there (its venv)
        self.start_service = start_service
        self.unit_failed = unit_failed
        self.start_timeout = start_timeout
        self.listening: dict[str, Listening] = {}
        self.talks: dict[str, Talk] = {}
        self._ids = 0

    @property
    def available(self) -> bool:
        """Clients may offer the microphone: the service runs, or it can be started."""
        return self.link.ready or self.installed()

    async def _ensure_running(self, client: Any, tid: str) -> bool:
        """The voice service starts on the first press (its models take a few seconds to load)."""
        if self.link.ready:
            return True
        if not self.installed():
            return False
        self.send(client, {"type": "listen", "id": tid, "state": "loading"})
        if self.link.writer is None and self.start_service is not None:
            await self.start_service()
        deadline = time.monotonic() + self.start_timeout
        checked = time.monotonic()
        while time.monotonic() < deadline:
            if self.link.ready:
                return True
            if self.link.status.get("error"):
                return False
            if self.unit_failed is not None and time.monotonic() - checked > 2:
                checked = time.monotonic()
                if await self.unit_failed():          # it could not start at all: no point waiting
                    self.link.status = {"error": "svoya-voice did not start (journalctl --user -u svoya-voice)"}
                    return False
            await asyncio.sleep(0.2)
        return False

    def new_id(self) -> str:
        self._ids += 1
        return f"v{int(time.time() * 1000):x}{self._ids}"

    # ---- a client asks to listen ------------------------------------------------------------
    async def listen(self, client: Any, msg: Event) -> None:
        action = str(msg.get("action") or "start")
        tid = str(msg.get("id") or "") or self.new_id()
        if action == "hush":
            await self.hush(client)
            return
        if action in ("stop", "cancel"):
            mine = [li for li in self.listening.values() if li.client is client and (li.id == tid or not msg.get("id"))]
            for li in mine:
                await self.link.send({"type": action, "id": li.id})
                if action == "cancel":
                    self.listening.pop(li.id, None)
                    self.broadcast(self.state(li.id, "idle", "calm"))
            if action == "stop" and not mine:
                await self.hush(client)
            return
        if not await self._ensure_running(client, tid):
            self.send(client, {"type": "listen", "id": tid, "state": "unavailable",
                               "message": self.link.status.get("error") or ""})
            return
        await self.start_listening(client, tid, str(msg.get("mode") or "tap"))

    async def start_listening(self, client: Any, tid: str, mode: str, follow_of: str = "") -> None:
        for li in [li for li in self.listening.values() if li.client is client]:
            self.listening.pop(li.id, None)
        if not follow_of:
            self.cancel(client)                        # pressing the button again starts over
        for talk in [t for t in self.talks.values() if t.client is client and t.id != follow_of]:
            talk.follow = False                        # a new question replaces the answer
            if not talk.hushed:
                talk.hushed = True
                await self.link.send({"type": "hush", "id": talk.id})
        self.listening[tid] = Listening(tid, client, mode)
        event: Event = {"type": "listen", "id": tid, "state": "listening", "mode": mode}
        if follow_of:
            event["follow"] = follow_of
        self.send(client, event)
        self.broadcast(self.state(tid, "listening", "listening"))
        await self.link.send({"type": "listen", "id": tid, "mode": mode})

    async def hush(self, client: Any) -> None:
        for talk in [t for t in self.talks.values() if t.client is client]:
            talk.follow = False
            if not talk.hushed:
                talk.hushed = True
                await self.link.send({"type": "hush", "id": talk.id})

    def forget(self, client: Any) -> None:
        """The client went away: nothing more is heard or said for it."""
        for li in [li for li in self.listening.values() if li.client is client]:
            self.listening.pop(li.id, None)
            asyncio.get_running_loop().create_task(self.link.send({"type": "cancel", "id": li.id}))
        if any(t.client is client for t in self.talks.values()):
            asyncio.get_running_loop().create_task(self.link.send({"type": "hush"}))

    # ---- what the voice service says ---------------------------------------------------------
    async def _on_voice(self, msg: Event) -> None:
        kind = msg.get("type")
        tid = str(msg.get("id") or "")
        if kind == "gone":                      # the service went away: end what was going on
            for li in list(self.listening.values()):
                self.send(li.client, {"type": "listen", "id": li.id, "state": "error", "message": "voice service stopped"})
                self.broadcast(self.state(li.id, "idle", "sorry"))
            self.listening.clear()
            for talk in list(self.talks.values()):
                await self._spoken(talk, hushed=True)
            return
        li = self.listening.get(tid)
        talk = self.talks.get(tid)
        client = li.client if li else talk.client if talk else None
        if client is None:
            return
        if kind == "level":
            self.broadcast({"type": "level", "id": tid, "source": msg.get("source"), "level": msg.get("level", 0)})
        elif kind == "speech" and li:
            self.send(client, {"type": "listen", "id": tid, "state": "hearing" if msg.get("state") == "start" else "heard"})
        elif kind == "loading" and li:
            self.send(client, {"type": "listen", "id": tid, "state": "loading"})
        elif kind == "nothing" and li:
            self.listening.pop(tid, None)
            self.send(client, {"type": "listen", "id": tid, "state": "nothing", "mode": li.mode})
            self.broadcast(self.state(tid, "idle", "calm"))
        elif kind == "error":
            if li:
                self.listening.pop(tid, None)
                self.send(client, {"type": "listen", "id": tid, "state": "error", "message": msg.get("message", "")})
                self.broadcast(self.state(tid, "idle", "sorry"))
            elif talk:
                await self._spoken(talk, hushed=True)
        elif kind == "transcript" and li:
            self.listening.pop(tid, None)
            await self._heard(li, str(msg.get("text") or ""), msg.get("ms"))
        elif kind == "spoken" and talk:
            await self._spoken(talk, hushed=bool(msg.get("hushed")))

    async def _heard(self, li: Listening, text: str, ms: Any) -> None:
        client = li.client
        lang = guess_lang(text, getattr(getattr(client, "session", None), "lang", "ru"))
        self.send(client, {"type": "transcript", "id": li.id, "text": text, "lang": lang, "ms": ms})
        cfg = self.config()
        speak = cfg.get("speak", True) is not False
        if li.mode == "follow" and BYE.match(text):      # the end of a conversation needs no model
            bye = t("voice.bye", lang)
            self.send(client, {"type": "token", "id": li.id, "text": bye})
            self.send(client, {"type": "done", "id": li.id, "usage": {"inTokens": 0, "outTokens": 0}, "costEur": 0,
                               "latencyMs": 0, "leftMachine": False, "actions": []})
            if not speak:
                self.broadcast(self.state(li.id, "idle", "calm"))
                return
            talk = Talk(li.id, client, lang, self.voice_for(client), SpeechStream(lang), follow=False, finished=True)
            self.talks[li.id] = talk
            self.broadcast(self.state(li.id, "speaking", "talking"))
            await self._say(talk, bye)
            await self._say(talk, "", final=True)
            return
        if speak:
            self.talks[li.id] = Talk(li.id, client, lang, self.voice_for(client),
                                     SpeechStream(lang, numbers=not self.link.reads_numbers),
                                     follow=cfg.get("follow", True) is not False and li.mode != "hold")
        await self.ask(client, {"type": "ask", "id": li.id, "text": text, "context": {"voice": True}})

    # ---- the answer, as it streams ------------------------------------------------------------
    def wrap(self, turn_id: str, emit: Callable[[Event], Awaitable[None]]) -> Callable[[Event], Awaitable[None]]:
        """The turn's emitter, with the answer handed to the voice sentence by sentence."""
        async def voiced(event: Event) -> None:
            talk = self.talks.get(turn_id)
            kind = event.get("type")
            if talk is not None and not talk.finished and not talk.hushed:
                if kind == "token":
                    for sentence in talk.stream.feed(str(event.get("text") or "")):
                        await self._say(talk, sentence)
                elif kind == "done":
                    for sentence in talk.stream.flush():
                        await self._say(talk, sentence)
                    talk.finished, talk.ok = True, not event.get("cancelled")
                    await self._say(talk, "", final=True)
                elif kind == "error":
                    message = str(event.get("message") or "")
                    first = SpeechStream(talk.lang, numbers=talk.stream.numbers).feed(message + "\n")[:1]
                    for sentence in first:
                        await self._say(talk, sentence)
                    talk.finished, talk.ok = True, False
                    await self._say(talk, "", final=True)
            if talk is not None and kind == "state" and event.get("state") == "idle" and not talk.spoken:
                event = dict(event, state="speaking", mood="talking")   # the answer is still being said
            await emit(event)
        return voiced

    async def _say(self, talk: Talk, text: str, final: bool = False) -> None:
        if text:
            talk.said += 1
        lang = guess_lang(text, talk.lang) if text else talk.lang
        await self.link.send({"type": "say", "id": talk.id, "text": text, "lang": lang, "voice": talk.voice,
                              "final": final})

    async def _spoken(self, talk: Talk, hushed: bool) -> None:
        if talk.spoken:
            return
        talk.spoken = True
        self.talks.pop(talk.id, None)
        self.send(talk.client, {"type": "spoken", "id": talk.id, "hushed": hushed})
        if talk.follow and talk.ok and not hushed and self.available and not getattr(talk.client, "closed", False):
            await self.start_listening(talk.client, self.new_id(), "follow", follow_of=talk.id)
        else:
            self.broadcast(self.state(talk.id, "idle", "calm"))
