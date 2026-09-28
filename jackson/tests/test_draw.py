# SPDX-License-Identifier: Apache-2.0
"""«Джексон, нарисуй …»: the request, the ComfyUI graphs, the Studio's lifecycle, the turn."""

import asyncio
import base64
import hashlib
import json
import queue
import socket
import threading
import time
import tomllib
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from jackson import draw
from jackson.engine import Session, Turn
from jackson.providers.base import CancelToken
from jackson.runner import RunResult
from tests.fakes import FakeRunner, make_app, rmtree, short_tmpdir

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
DESCRIPTION = ("A fluffy ginger cat wearing a small black top hat sits on a wooden windowsill, soft morning "
               "light from the left, warm colors, shallow depth of field, a cozy storybook illustration.")


class ParseTest(unittest.TestCase):
    def p(self, text, *names):
        r = draw.parse(text, names)
        return None if r is None else (r.prompt, r.size, r.wallpaper, r.kit)

    def test_russian(self):
        self.assertEqual(self.p("Джексон, нарисуй кота в шляпе"), ("кота в шляпе", "square", False, None))
        self.assertEqual(self.p("нарисуй мне, пожалуйста, закат над морем в стиле акварели")[0],
                         "закат над морем в стиле акварели")
        self.assertEqual(self.p("ну нарисуй-ка мне ёжика в тумане")[0], "ёжика в тумане")
        self.assertEqual(self.p("можешь нарисовать собаку?")[0], "собаку")
        self.assertEqual(self.p("сделай картинку с котом")[0], "котом")
        self.assertEqual(self.p("Барсик, нарисуй дракона", "Барсик")[0], "дракона")

    def test_the_noun_stays_when_it_is_the_subject(self):
        self.assertEqual(self.p("сделай логотип для кофейни")[0], "логотип для кофейни")
        self.assertEqual(self.p("создай раскраску с драконом для детей")[0], "раскраску с драконом для детей")
        self.assertEqual(self.p("make a logo for my cafe")[0], "a logo for my cafe")

    def test_english(self):
        self.assertEqual(self.p("draw a cat in a hat"), ("a cat in a hat", "square", False, None))
        self.assertEqual(self.p("Please, draw me a picture of a dog")[0], "a dog")
        self.assertEqual(self.p("generate an image of a castle at night")[0], "a castle at night")
        self.assertEqual(self.p("draw an art deco poster")[0], "an art deco poster")    # "art" is kept

    def test_shape_words(self):
        self.assertEqual(self.p("нарисуй обои с горами"), ("горами", "wide", True, None))
        self.assertEqual(self.p("сделай обои с котом"), ("котом", "wide", True, None))
        self.assertEqual(self.p("нарисуй вертикальную картинку кота"), ("кота", "portrait", False, None))
        self.assertEqual(self.p("нарисуй кота для телефона"), ("кота", "tall", False, None))
        # content words set the shape but stay in the description
        self.assertEqual(self.p("нарисуй портрет бабушки"), ("портрет бабушки", "portrait", False, None))
        self.assertEqual(self.p("нарисуй пейзаж с горами"), ("пейзаж с горами", "landscape", False, None))
        self.assertEqual(self.p("can you draw a wide river")[:2], ("a wide river", "square"))
        self.assertEqual(self.p("please draw a sunset, wallpaper"), ("a sunset", "wide", True, None))
        self.assertEqual(self.p("draw a wallpaper with mountains"), ("mountains", "wide", True, None))
        self.assertEqual(self.p("draw a cat for my phone"), ("a cat", "tall", False, None))
        self.assertEqual(draw.parse("нарисуй обои").dims, (1344, 768))

    def test_kit_words(self):
        self.assertEqual(self.p("нарисуй кота через квен"), ("кота", "square", False, "qwen-image-2.1"))
        self.assertEqual(self.p("draw a cat with qwen image 2.1")[3], "qwen-image-2.1")
        self.assertEqual(self.p("нарисуй кота флюксом")[3], "flux2-klein-4b")

    def test_not_a_drawing(self):
        for text in ("сделай скриншот", "сделай громче", "как нарисовать кота", "ты умеешь рисовать?",
                     "создай папку проекты", "нарисуй кота и отправь в телеграм", "draw a cat and send it to Anna",
                     "установи рисование", "сделай\nкартинку"):
            self.assertIsNone(draw.parse(text), text)

    def test_nothing_to_draw_asks(self):
        self.assertEqual(self.p("нарисуй"), ("", "square", False, None))
        self.assertEqual(self.p("нарисуй картинку")[0], "")

    def test_slug(self):
        self.assertEqual(draw.slug("кота в шляпе!"), "кота в шляпе")
        self.assertEqual(draw.slug("a/b\\c"), "a b c")
        self.assertEqual(draw.slug("???"), "picture")
        self.assertLessEqual(len(draw.slug("очень " * 30)), 48)


class GraphTest(unittest.TestCase):
    def test_klein_mirrors_the_template(self):
        g = draw.graph_for(draw.KLEIN, "a cat", 832, 1216, 7)
        types = {v["class_type"] for v in g.values()}
        self.assertEqual(types, {"UNETLoader", "CLIPLoader", "VAELoader", "CLIPTextEncode", "ConditioningZeroOut",
                                 "CFGGuider", "KSamplerSelect", "Flux2Scheduler", "RandomNoise",
                                 "EmptyFlux2LatentImage", "SamplerCustomAdvanced", "VAEDecode", "PreviewImage"})
        self.assertEqual(g["62"]["inputs"], {"steps": 4, "width": 832, "height": 1216})
        self.assertEqual(g["71"]["inputs"]["type"], "flux2")
        self.assertEqual(g["63"]["inputs"]["cfg"], 1)
        self.assertEqual(g["73"]["inputs"]["noise_seed"], 7)
        for node in g.values():                  # every link points at a node of the graph
            for v in node["inputs"].values():
                if isinstance(v, list):
                    self.assertIn(v[0], g)

    def test_qwen_image(self):
        g = draw.graph_for(draw.QWEN_IMAGE, "a cat", 1024, 1024, 1)
        self.assertEqual(g["458"]["inputs"]["steps"], 25)
        self.assertEqual(g["453"]["inputs"], {"clip_name": "qwen3vl_8b_int8_convrot.safetensors", "type": "qwen_image",
                                              "device": "default"})
        self.assertEqual(g["458"]["inputs"]["negative"], ["452", 1])

    def test_enhance_links_the_system_prompt(self):
        g = draw.graph_enhance(draw.KLEIN, "кот в шляпе")
        self.assertEqual(g["80"]["inputs"]["system_prompt"], ["82", 0])
        inputs = g["80"]["inputs"]
        self.assertEqual((inputs["sampling_mode"], inputs["sampling_mode.temperature"], inputs["sampling_mode.top_k"]),
                         ("on", 0.7, 20))                    # sampled as Qwen3 advises; greedy loops
        self.assertEqual(g["81"]["class_type"], "PreviewAny")

    def test_kit_files_match_the_sos_catalog(self):
        catalog = Path(__file__).resolve().parents[2] / "cli" / "svoya_cli" / "data" / "model_catalog.toml"
        if not catalog.exists():
            self.skipTest("the sos CLI is not next to Jackson")
        kits = {k["id"]: k for k in tomllib.loads(catalog.read_text(encoding="utf-8"))["kit"]}
        for kit in draw.KITS.values():
            names = sorted(Path(f["file"]).name for f in kits[kit.id]["files"])
            self.assertEqual(names, sorted(n for _, n in kit.files()), kit.id)
        self.assertTrue(kits[draw.DEFAULT_KIT].get("default"))

    def test_clean_description(self):
        self.assertEqual(draw.clean_description(f"<think>\n\n</think>\n\n\"{DESCRIPTION}\""), DESCRIPTION)
        self.assertEqual(draw.clean_description("Prompt: " + DESCRIPTION), DESCRIPTION)
        self.assertIsNone(draw.clean_description("кот"))
        self.assertIsNone(draw.clean_description("<|im_start|>assistant " + DESCRIPTION))


class FakeComfy:
    """ComfyUI's HTTP API as the drawer uses it (no WebSocket: the drawer polls the history)."""

    def __init__(self) -> None:
        self.graphs: list[dict] = []
        self.calls: list[str] = []
        self.alive = True
        self.reject_enhance = False
        self.oom_once = False
        self.polls_before_done = 1
        self.description = DESCRIPTION
        self.ws_enabled = False
        self.ws_queues: dict[str, queue.Queue] = {}
        self.closed = False
        self.running: list[str] = []              # what /queue reports as running (prompt ids)
        self.forget = False                       # a restarted Studio: prompts are not in the queue
        self._polls: dict[str, int] = {}
        self._oom: dict[str, bool] = {}
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def send(self, code, body, ctype="application/json"):
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                fake.calls.append("GET " + self.path.split("?")[0])
                if self.path.startswith("/ws") and fake.ws_enabled and fake.alive:
                    self.websocket()
                    return
                if not fake.alive:
                    self.send(503, {})
                elif self.path == "/system_stats":
                    self.send(200, {"system": {}})
                elif self.path.startswith("/history/"):
                    self.send(200, fake.history(self.path.rsplit("/", 1)[1]))
                elif self.path.startswith("/view"):
                    self.send(200, PNG, "image/png")
                elif self.path == "/queue":
                    running = [[n, pid, {}, {}, []] for n, pid in enumerate(fake.running)]
                    self.send(200, {"queue_running": running, "queue_pending": []})
                else:
                    self.send(404, {})

            def websocket(self):
                key = self.headers.get("Sec-WebSocket-Key", "")
                accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode())
                                          .digest()).decode()
                self.send_response(101)
                self.send_header("Upgrade", "websocket")
                self.send_header("Connection", "Upgrade")
                self.send_header("Sec-WebSocket-Accept", accept)
                self.end_headers()
                cid = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)["clientId"][0]
                q = fake.ws_queues.setdefault(cid, queue.Queue())
                while True:
                    msg = q.get()
                    if msg is None:
                        return
                    data = json.dumps(msg).encode()
                    head = bytes([0x81]) + (bytes([len(data)]) if len(data) < 126
                                            else bytes([126]) + len(data).to_bytes(2, "big"))
                    try:
                        self.wfile.write(head + data)
                        self.wfile.flush()
                    except OSError:
                        return

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                fake.calls.append("POST " + self.path)
                if self.path == "/prompt":
                    graph = body["prompt"]
                    fake.graphs.append(graph)
                    if fake.reject_enhance and any(v["class_type"] == "TextGenerate" for v in graph.values()):
                        self.send(400, {"error": {"message": "Prompt outputs failed validation"},
                                        "node_errors": {"80": {"class_type": "TextGenerate",
                                                               "errors": [{"message": "Value not in list"}]}}})
                        return
                    pid = f"p{len(fake.graphs)}"
                    if not fake.forget:
                        fake.running.append(pid)
                    self.send(200, {"prompt_id": pid, "number": len(fake.graphs), "node_errors": {}})
                    q = fake.ws_queues.get(body.get("client_id", ""))
                    if q is not None:
                        sampler = next((k for k, v in graph.items() if v["class_type"] == "SamplerCustomAdvanced"), None)
                        loader = next((k for k, v in graph.items() if v["class_type"] == "UNETLoader"), None)
                        q.put({"type": "execution_start", "data": {"prompt_id": pid}})
                        if loader:
                            q.put({"type": "executing", "data": {"node": loader, "prompt_id": pid}})
                        if sampler:
                            q.put({"type": "executing", "data": {"node": sampler, "prompt_id": pid}})
                            for i in range(1, 5):
                                q.put({"type": "progress", "data": {"value": i, "max": 4, "node": sampler,
                                                                    "prompt_id": pid}})
                        q.put({"type": "progress", "data": {"value": 1, "max": 1, "node": "x", "prompt_id": "other"}})
                        q.put({"type": "execution_success", "data": {"prompt_id": pid}})
                        q.put({"type": "executing", "data": {"node": None, "prompt_id": pid}})
                else:
                    self.send(200, {})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def history(self, pid: str) -> dict:
        self._polls[pid] = self._polls.get(pid, 0) + 1
        if self._polls[pid] <= self.polls_before_done:
            return {}
        graph = self.graphs[int(pid[1:]) - 1]
        if pid in self.running:                   # done: out of the queue, into the history
            self.running.remove(pid)
        if any(v["class_type"] == "TextGenerate" for v in graph.values()):
            return {pid: {"outputs": {"81": {"text": [self.description]}},
                          "status": {"status_str": "success", "completed": True, "messages": []}}}
        if self.oom_once and not self._oom:
            self._oom[pid] = True
            return {pid: {"outputs": {}, "status": {"status_str": "error", "completed": False, "messages": [
                ["execution_error", {"node_type": "SamplerCustomAdvanced", "exception_type": "torch.OutOfMemoryError",
                                     "exception_message": "CUDA out of memory. Tried to allocate 2.00 GiB"}]]}}}
        return {pid: {"outputs": {"9": {"images": [{"filename": "ComfyUI_temp_0001_.png", "subfolder": "",
                                                    "type": "temp"}]}},
                      "status": {"status_str": "success", "completed": True, "messages": []}}}

    def close(self):
        if self.closed:
            return
        self.closed = True
        for q in self.ws_queues.values():
            q.put(None)
        self.httpd.shutdown()
        self.httpd.server_close()


class StudioRunner(FakeRunner):
    """sos-studio, podman and systemctl --user for the Studio; starting the unit brings the fake up."""

    def __init__(self, comfy: FakeComfy, built: bool = True, installed: bool = True, unit: bool = True):
        super().__init__(available={"systemctl", "podman"} | ({"sos-studio"} if installed else set()))
        self.comfy = comfy
        self.built = built
        self.unit = unit

    def run(self, argv, timeout=5.0, env=None, cwd=None, input=None):
        argv = list(argv)
        if argv[:3] == ["podman", "image", "exists"]:
            self.calls.append(argv)
            return RunResult(0 if self.built else 1)
        if argv[:2] == ["systemctl", "--user"]:
            self.calls.append(argv)
            if not self.unit:
                return RunResult(5, err="Failed to start sos-studio.service: Unit sos-studio.service not found.")
            if argv[2] == "start":
                self.comfy.alive = True
            elif argv[2] == "stop":
                self.comfy.alive = False
            return RunResult(0)
        return super().run(argv, timeout, env, cwd, input)


class DrawerTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        self.comfy = FakeComfy()
        self.addCleanup(self.comfy.close)
        self.addCleanup(rmtree, self.root)
        self.views = self.root / "views"
        self.pictures = self.root / "Pictures"

    def kit(self, kit=draw.KLEIN):
        for folder, name in kit.files():
            (self.views / folder).mkdir(parents=True, exist_ok=True)
            (self.views / folder / name).write_bytes(b"w")

    def drawer(self, runner=None, marker=None, **settings):
        runner = runner or StudioRunner(self.comfy)
        d = draw.Drawer(runner, lambda: self.pictures, settings, views=self.views, comfy=draw.Comfy(self.comfy.url, poll=0.02),
                        marker=marker, sleep=lambda s: None)
        self.addCleanup(d.close)
        return d

    def test_draws_and_keeps_the_description(self):
        self.kit()
        d = self.drawer()
        phases = []
        res = d.draw(draw.parse("нарисуй кота в шляпе"), CancelToken(), lambda **p: phases.append(p))
        self.assertTrue(res.ok, res)
        self.assertEqual(res.path.parent, self.pictures / "Jackson")
        self.assertTrue(res.path.name.endswith(" кота в шляпе.png"), res.path.name)
        self.assertEqual(res.path.read_bytes(), PNG)
        self.assertEqual(res.prompt, DESCRIPTION)
        enhance, image = self.comfy.graphs
        self.assertEqual(enhance["80"]["inputs"]["prompt"], "кота в шляпе")
        self.assertEqual(image["74"]["inputs"]["text"], DESCRIPTION)
        self.assertEqual(image["62"]["inputs"], {"steps": 4, "width": 1024, "height": 1024})
        self.assertIn({"phase": "start"}, phases)
        # «ещё вариант»: the same request draws again with a new seed, without describing it again
        res2 = d.draw(draw.parse("нарисуй кота в шляпе"), CancelToken())
        self.assertTrue(res2.ok)
        self.assertEqual(len(self.comfy.graphs), 3)
        self.assertEqual(self.comfy.graphs[2]["74"]["inputs"]["text"], DESCRIPTION)
        self.assertNotEqual(res2.path, res.path)

    def test_follows_progress_over_the_websocket(self):
        self.kit()
        self.comfy.ws_enabled = True                 # the history has it after the messages say so
        phases = []
        d = self.drawer(enhance=False)
        d.comfy.poll = 30                        # only the WebSocket can finish this in time
        res = d.draw(draw.parse("draw a cat"), CancelToken(), lambda **p: phases.append(p))
        self.assertTrue(res.ok, res)
        self.assertEqual(phases[:2], [{"phase": "start"}, {"phase": "load"}])
        self.assertIn({"phase": "draw", "done": 4, "total": 4}, phases)
        self.assertNotIn({"phase": "draw", "done": 1, "total": 1}, phases)      # another prompt's progress

    def test_a_long_english_prompt_goes_as_it_is(self):
        self.kit()
        res = self.drawer().draw(draw.DrawRequest(DESCRIPTION + " " + DESCRIPTION), CancelToken())
        self.assertTrue(res.ok)
        self.assertEqual([g.get("80") for g in self.comfy.graphs], [None])

    def test_the_description_step_failing_is_not_the_end(self):
        self.kit()
        self.comfy.reject_enhance = True
        res = self.drawer().draw(draw.parse("нарисуй кота"), CancelToken())
        self.assertTrue(res.ok, res)
        self.assertEqual(self.comfy.graphs[-1]["74"]["inputs"]["text"], "кота")

    def test_starts_the_studio_and_stops_it_when_idle(self):
        self.kit()
        self.comfy.alive = False
        runner = StudioRunner(self.comfy)
        d = self.drawer(runner, idle_minutes=0)
        res = d.draw(draw.parse("draw a cat"), CancelToken())
        self.assertTrue(res.ok, res)
        self.assertIn(["systemctl", "--user", "start", "--no-block", draw.UNIT], runner.calls)
        self.assertTrue(d.started_here)
        self.assertTrue(d.stop_if_idle())
        self.assertIn(["systemctl", "--user", "stop", draw.UNIT], runner.calls)
        self.assertFalse(self.comfy.alive)

    def test_a_busy_studio_is_looked_at_again_later(self):
        self.kit()
        self.comfy.alive = False
        runner = StudioRunner(self.comfy)
        d = self.drawer(runner, idle_minutes=30)
        self.assertTrue(d.draw(draw.parse("draw a cat"), CancelToken()).ok)
        with d._lock:                                    # drawing right now: not stopped, the timer runs again
            self.assertFalse(d.stop_if_idle())
        self.assertIsNotNone(d._idle)
        self.assertTrue(d._idle.is_alive())
        self.assertTrue(d.stop_if_idle())

    def test_a_restarted_jackson_still_stops_the_studio_he_started(self):
        self.kit()
        self.comfy.alive = False
        marker = self.root / "run" / "studio-by-jackson"
        runner = StudioRunner(self.comfy)
        first = self.drawer(runner, marker=marker)
        self.assertTrue(first.draw(draw.parse("draw a cat"), CancelToken()).ok)
        self.assertTrue(marker.exists())
        first._idle.cancel()                             # jacksond crashed: close() never ran
        second = self.drawer(runner, marker=marker)
        self.assertTrue(second.started_here)
        self.assertTrue(second._idle.is_alive())
        second.close()                                   # jacksond stops: the Studio he started goes too
        self.assertIn(["systemctl", "--user", "stop", "--no-block", draw.UNIT], runner.calls)
        self.assertFalse(marker.exists())

    def test_an_old_studio_without_the_unit(self):
        self.kit()
        self.comfy.alive = False
        res = self.drawer(StudioRunner(self.comfy, unit=False)).draw(draw.parse("draw a cat"), CancelToken())
        self.assertEqual((res.code, res.install), ("old-studio", "draw"))

    def test_a_studio_that_goes_away_is_noticed(self):
        self.kit()
        self.comfy.polls_before_done = 10 ** 6
        d = self.drawer(enhance=False)
        threading.Timer(0.3, self.comfy.close).start()   # the container stops mid-picture
        started = time.monotonic()
        res = d.draw(draw.parse("draw a cat"), CancelToken())
        self.assertEqual(res.code, "gone")
        self.assertLess(time.monotonic() - started, 5)

    def test_a_prompt_the_studio_forgot_is_noticed(self):
        self.kit()
        self.comfy.polls_before_done = 10 ** 6
        self.comfy.forget = True                          # restarted: the prompt is in no queue and no history
        started = time.monotonic()
        res = self.drawer(enhance=False).draw(draw.parse("draw a cat"), CancelToken())
        self.assertEqual(res.code, "gone")
        self.assertLess(time.monotonic() - started, 5)

    def test_the_models_own_description_is_used_as_it_is(self):
        self.kit()
        req = draw.DrawRequest("A red fox in the snow", describe=False)
        self.assertTrue(self.drawer().draw(req, CancelToken()).ok)
        self.assertEqual([g.get("80") for g in self.comfy.graphs], [None])

    def test_a_studio_started_by_hand_is_left_alone(self):
        self.kit()
        d = self.drawer()
        self.assertTrue(d.draw(draw.parse("draw a cat"), CancelToken()).ok)
        self.assertFalse(d.stop_if_idle())

    def test_what_is_missing(self):
        d = self.drawer(StudioRunner(self.comfy, installed=False))
        res = d.draw(draw.parse("нарисуй кота"), CancelToken())
        if Path("/usr/local/bin/sos-studio").exists():
            self.skipTest("a real Studio is installed here")
        self.assertEqual((res.ok, res.code, res.install), (False, "not-installed", "draw"))
        res = self.drawer().draw(draw.parse("нарисуй кота"), CancelToken())
        self.assertEqual(res.code, "no-kit")
        self.assertIn("text_encoders/qwen_3_4b.safetensors", res.detail)
        self.kit()
        self.comfy.alive = False
        res = self.drawer(StudioRunner(self.comfy, built=False)).draw(draw.parse("нарисуй кота"), CancelToken())
        self.assertEqual((res.code, res.install), ("not-built", "draw"))

    def test_qwen_asked_for_but_missing_draws_with_klein(self):
        self.kit()
        res = self.drawer().draw(draw.parse("нарисуй кота через квен"), CancelToken())
        self.assertTrue(res.ok)
        self.assertEqual((res.kit, res.notes), ("flux2-klein-4b", ["instead-of:qwen-image-2.1"]))
        self.kit(draw.QWEN_IMAGE)
        res = self.drawer().draw(draw.parse("нарисуй кота через квен"), CancelToken())
        self.assertEqual(res.kit, "qwen-image-2.1")
        self.assertEqual(self.comfy.graphs[-1]["452"]["inputs"]["prompt"], "кота")   # Qwen reads Russian itself

    def test_out_of_memory_frees_the_card_and_tries_again(self):
        self.kit()
        self.comfy.oom_once = True
        res = self.drawer(enhance=False).draw(draw.parse("draw a cat"), CancelToken())
        self.assertTrue(res.ok, res)
        self.assertIn("POST /free", self.comfy.calls)

    def test_cancel(self):
        self.kit()
        self.comfy.polls_before_done = 10 ** 6
        d = self.drawer(enhance=False)
        cancel = CancelToken()
        threading.Timer(0.3, cancel.cancel).start()
        res = d.draw(draw.parse("draw a cat"), cancel)
        self.assertEqual(res.code, "cancelled")
        self.assertIn("POST /interrupt", self.comfy.calls)


class WebSocketTest(unittest.TestCase):
    def test_reads_frames_answers_pings_and_joins_fragments(self):
        a, b = socket.socketpair()
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        text = json.dumps({"type": "progress", "data": {"value": 2, "max": 4}}).encode()
        big = b"x" * 300
        b.sendall(bytes([0x89, 2]) + b"hi"                                   # ping
                  + bytes([0x81, len(text)]) + text                          # text
                  + bytes([0x02, 126]) + (len(big)).to_bytes(2, "big") + big  # binary, first fragment
                  + bytes([0x80, 3]) + b"end")                               # continuation, last
        ws = draw.WebSocket(a)
        ws.settimeout(2)
        self.assertEqual(ws.recv(), (1, text))
        self.assertEqual(ws.recv(), (2, big + b"end"))
        pong = b.recv(64)
        self.assertEqual(pong[0], 0x8A)            # a masked pong with the same payload
        mask = pong[2:6]
        self.assertEqual(bytes(c ^ mask[i % 4] for i, c in enumerate(pong[6:8])), b"hi")


class DrawTurnTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        self.addCleanup(rmtree, self.root)
        self.comfy = FakeComfy()
        self.addCleanup(self.comfy.close)

    def run_turn(self, app, text, session=None):
        events = []

        async def emit(ev):
            events.append(ev)

        async def go():
            await app.engine.run_turn(Turn(id="t-1", session=session or Session("test", "ru"), text=text, emit=emit))
        asyncio.run(go())
        return events

    def kit(self, app, session=None):
        views = self.root / "views"
        app.draw = draw.Drawer(app.runner, lambda: app.paths.home / "Pictures", {"enhance": False}, views=views,
                               comfy=draw.Comfy(self.comfy.url, poll=0.02), sleep=lambda s: None)
        for folder, name in draw.KLEIN.files():
            (views / folder).mkdir(parents=True, exist_ok=True)
            (views / folder / name).write_bytes(b"w")

    def test_turn_events(self):
        runner = StudioRunner(self.comfy)
        app = make_app(self.root, runner=runner)
        views = self.root / "views"
        app.draw = draw.Drawer(runner, lambda: app.paths.home / "Pictures", {}, views=views,
                               comfy=draw.Comfy(self.comfy.url, poll=0.02), sleep=lambda s: None)
        for folder, name in draw.KLEIN.files():
            (views / folder).mkdir(parents=True, exist_ok=True)
            (views / folder / name).write_bytes(b"w")
        events = self.run_turn(app, "Джексон, нарисуй кота в шляпе")
        route = next(e for e in events if e["type"] == "route")
        self.assertEqual((route["provider"], route["model"], route["local"]), ("studio", "flux2-klein-4b", True))
        tools = [e for e in events if e["type"] == "tool"]
        self.assertEqual([t["state"] for t in tools], ["running", "done"])
        self.assertTrue(tools[1]["image"].endswith("кота в шляпе.png"))
        self.assertIn("FLUX.2 [klein] 4B · 1024×1024 · A fluffy ginger cat", tools[1]["summary"])
        self.assertTrue(any(e["type"] == "progress" and e["stage"] == "draw" for e in events))
        token = "".join(e["text"] for e in events if e["type"] == "token")
        self.assertTrue(token.startswith("Готово: `~/Pictures/Jackson/"), token)
        # the voice says this instead of the file name
        self.assertEqual(next(e for e in events if e["type"] == "token")["speak"], "Готово, нарисовал.")
        done = next(e for e in events if e["type"] == "done")
        self.assertEqual(done["suggestions"], [{"label": "Ещё вариант", "prompt": "Джексон, нарисуй кота в шляпе",
                                                "primary": True}])
        self.assertFalse(done["leftMachine"])

    def test_not_installed_says_how(self):
        runner = StudioRunner(self.comfy, installed=False)
        app = make_app(self.root, runner=runner)
        if Path("/usr/local/bin/sos-studio").exists():
            self.skipTest("a real Studio is installed here")
        events = self.run_turn(app, "нарисуй кота")
        token = "".join(e["text"] for e in events if e["type"] == "token")
        self.assertIn("sos install draw", token)
        self.assertEqual(next(e for e in events if e["type"] == "tool" and e["state"] == "failed")["summary"],
                         "not-installed")

    def test_nothing_to_draw_asks_what(self):
        app = make_app(self.root, runner=StudioRunner(self.comfy))
        session = Session("test", "ru")
        events = self.run_turn(app, "нарисуй обои", session)
        self.assertIn("Что нарисовать?", "".join(e["text"] for e in events if e["type"] == "token"))
        self.assertEqual(session.history[-1][1]["content"][:15], "Что нарисовать?")
        # the reply is the picture, in the shape asked for first
        self.kit(app, session)
        events = self.run_turn(app, "горы на закате", session)
        tool = next(e for e in events if e["type"] == "tool" and e["state"] == "done")
        self.assertEqual((tool["args"]["prompt"], tool["args"]["size"]), ("горы на закате", "1344x768"))
        # a question after «нарисуй» is not a picture
        self.run_turn(app, "нарисуй", session)
        events = self.run_turn(app, "а что ты умеешь?", session)
        self.assertFalse(any(e["type"] == "tool" and e["name"] == "draw" for e in events))
        self.assertIsNone(session.pending_draw)

    def test_ai_off_stops_drawing(self):
        app = make_app(self.root, runner=StudioRunner(self.comfy))
        marker = app.paths.ai_off_markers[1]
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("off\n")
        events = self.run_turn(app, "нарисуй кота")
        self.assertTrue(any(e["type"] == "error" and e.get("aiOff") for e in events))
        self.assertEqual(self.comfy.graphs, [])


if __name__ == "__main__":
    unittest.main()
