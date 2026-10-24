"""Cloud voices against local fake servers that mimic each service's documented API.
No network leaves the machine, and every key is a made-up test value."""
import base64
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.setdefault("SWEATCAST_BACKEND", "mlx")

import cli  # noqa: E402
import cloud  # noqa: E402
import msgpack_min  # noqa: E402
import personas  # noqa: E402
from fakes import FakeService, tone_pcm, tone_wav  # noqa: E402
from test_personas import FIXTURE, persona_home  # noqa: E402

SECRET = "sk-test-NEVERPRINT-123"
DRAFT = os.path.join(ROOT, "tests", "fixtures", "example.draft.txt")


def wav_answer(req):
    return 200, {"Content-Type": "audio/wav"}, tone_wav(0.4, rate=44100, bogus_size=True)


class Core(unittest.TestCase):
    def test_wav_with_a_bogus_size_reads_to_the_end(self):
        pcm, rate = cloud.wav_pcm(tone_wav(0.5, rate=24000, bogus_size=True))
        self.assertEqual(rate, 24000)
        self.assertEqual(len(pcm), 2 * 12000)
        stereo, _ = cloud.wav_pcm(tone_wav(0.5, channels=2))
        self.assertEqual(len(stereo), 2 * 12000)   # mixed down to mono

    def test_resample_44100_to_24000_keeps_length(self):
        pcm = tone_pcm(1.0, rate=44100)
        out = cloud.resample(pcm, 44100, 24000)
        self.assertAlmostEqual(len(out) / 2, 24000, delta=2)
        self.assertEqual(cloud.resample(pcm, 24000, 24000), pcm)

    def test_trim_matches_the_local_rule(self):
        pcm = b"\x00\x00" * 2400 + tone_pcm(0.2) + b"\x00\x00" * 4800
        out = cloud.trim(pcm)
        self.assertLess(len(out), len(pcm))
        self.assertGreater(len(out), len(tone_pcm(0.2)))

    def test_msgpack_round_trip(self):
        value = {"text": "Set your feet. Ünïcode", "references": [{"audio": b"\x00\x01" * 40000, "text": "hi"}],
                 "sample_rate": 24000, "normalize": True, "seed": None, "neg": -5, "big": 2 ** 40, "f": 1.5,
                 "long": "x" * 70000}
        self.assertEqual(msgpack_min.unpack(msgpack_min.pack(value)), value)

    def test_429_then_success_is_retried(self):
        calls = []

        def answer(req):
            calls.append(1)
            return (429, {}, b"{}") if len(calls) < 3 else (200, {}, b"ok")
        with FakeService(answer) as fake:
            status, _, data = cloud.request("POST", fake.url + "/x", {}, b"", sleep=lambda s: None)
        self.assertEqual((status, data, len(calls)), (200, b"ok", 3))

    def test_errors_by_kind(self):
        for status, body, kind in ((401, b'{"message": "Invalid api key"}', "auth"),
                                   (402, b'{"status": 402, "message": "No payment"}', "billing"),
                                   (400, b'{"detail": {"message": "text too long"}}', "bad_request"),
                                   (400, b'{"error_code": "quota_exceeded", "message": "out"}', "quota"),
                                   (503, b"{}", "unavailable")):
            with FakeService(lambda req, s=status, b=body: (s, {}, b)) as fake:
                with self.assertRaises(cloud.ServiceError) as e:
                    cloud.request("POST", fake.url + "/x", {"Authorization": f"Bearer {SECRET}"}, b"",
                                  service="fish", sleep=lambda s: None)
            self.assertEqual(e.exception.kind, kind, status)
            self.assertNotIn(SECRET, str(e.exception))

    def test_estimate_counts_bytes_for_fish_and_characters_elsewhere(self):
        chars, usd = cloud.estimate("fish", "s2.1-pro", ["Zoë"] * 1000)
        self.assertEqual(chars, 3000)
        self.assertAlmostEqual(usd, 4000 * 15 / 1e6)
        _, usd = cloud.estimate("deepgram", "aura-2", ["abc"] * 1000)
        self.assertAlmostEqual(usd, 3000 * 30 / 1e6)

    def test_services_settings(self):
        s = cloud.services()
        self.assertEqual(set(s), {"fish", "elevenlabs", "cartesia", "deepgram"})
        self.assertFalse(s["deepgram"]["tried_live"])
        for name in ("fish", "elevenlabs", "cartesia"):
            self.assertTrue(s[name]["tried_live"], name)
        self.assertEqual(s["fish"]["default_model"], "s2.1-pro")
        self.assertEqual(s["deepgram"]["max_chars"], 2000)


class Fish(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        patches = [mock.patch.object(personas.paths, "PERSONAS", persona_home(self.d)),
                   mock.patch.dict(os.environ, {"FISH_AUDIO_API_KEY": SECRET})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.voice = personas.voice_for(personas.lookup("Coach Test"), "fish")

    def test_voice_for_a_service(self):
        v = self.voice
        self.assertEqual((v["backend"], v["engine"], v["service"], v["model"]), ("cloud", "fish", "fish", "s2.1-pro"))
        self.assertEqual(v["key"], personas.voice_for(personas.lookup("Coach Test"), "local")["key"])
        self.assertNotIn(SECRET, json.dumps(v))

    def test_fish_request_shape(self):
        with FakeService(wav_answer) as fake, mock.patch.dict(os.environ, {"SWEATCAST_FISH_URL": fake.url}):
            pcm = cloud.speaker(self.voice)("Set your feet.", 42)
        req = fake.requests[0]
        self.assertEqual((req.method, req.path), ("POST", "/v1/tts"))
        self.assertEqual(req.headers["authorization"], f"Bearer {SECRET}")
        self.assertEqual(req.headers["model"], "s2.1-pro")
        self.assertEqual(req.headers["content-type"], "application/msgpack")
        body = msgpack_min.unpack(req.body)
        with open(os.path.join(FIXTURE, "coach-test", "clip.wav"), "rb") as f:
            self.assertEqual(body["references"][0]["audio"], f.read())
        self.assertEqual(body["references"][0]["text"], "Set your feet. Chest up, and press.")
        self.assertEqual((body["text"], body["format"], body["sample_rate"]), ("Set your feet.", "wav", 24000))
        self.assertNotIn("seed", body)   # Fish's speech takes no seed
        self.assertAlmostEqual(len(pcm) / 2 / 24000, 0.4, delta=0.05)   # resampled to 24 kHz

    def test_fish_402_is_billing(self):
        with FakeService(lambda r: (402, {}, b'{"status": 402, "message": "No payment"}')) as fake, \
                mock.patch.dict(os.environ, {"SWEATCAST_FISH_URL": fake.url}):
            with self.assertRaises(cloud.ServiceError) as e:
                cloud.speaker(self.voice)("Hi.", 42)
        self.assertEqual(e.exception.kind, "billing")

    def test_fish_design_returns_24k_takes(self):
        import services.fish as fish
        candidate = base64.b64encode(tone_wav(1.0, rate=44100)).decode()
        answer = lambda r: (200, {"Content-Type": "application/json"},
                            json.dumps({"candidates": [{"audio_base64": candidate, "sample_rate": 44100},
                                                       {"audio_base64": candidate, "sample_rate": 44100}]}).encode())
        with FakeService(answer) as fake, mock.patch.dict(os.environ, {"SWEATCAST_FISH_URL": fake.url}):
            takes = fish.design("A warm coach in her forties.", "Okay, set your feet.", 2, 7)
        req = fake.requests[0]
        self.assertEqual((req.path, req.headers["model"]), ("/v1/voice-design", "voice-design-1"))
        body = json.loads(req.body)
        self.assertEqual((body["instruction"], body["n"], body["seed"]), ("A warm coach in her forties.", 2, 7))
        self.assertLessEqual(len(body["reference_text"]), 150)
        self.assertEqual(len(takes), 2)
        self.assertAlmostEqual(len(takes[0][0]) / 2 / 24000, 1.0, delta=0.15)
        self.assertEqual(takes[0][1], "Okay, set your feet.")


class ServiceCase(unittest.TestCase):
    """A fixture coach and a test key for one service, with the service pointed at a fake."""
    SERVICE = None

    def setUp(self):
        import keys
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        patches = [mock.patch.object(personas.paths, "PERSONAS", persona_home(self.d)),
                   mock.patch.dict(os.environ, {keys.SERVICE_VARS[self.SERVICE]: SECRET})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def coach(self):
        return personas.lookup("Coach Test")

    def serve(self, answer):
        fake = FakeService(answer)
        fake.__enter__()
        self.addCleanup(fake.__exit__)
        patch = mock.patch.dict(os.environ, {f"SWEATCAST_{self.SERVICE.upper()}_URL": fake.url})
        patch.start()
        self.addCleanup(patch.stop)
        return fake


def elevenlabs_answer(req):
    if req.path == "/v1/voices/add":
        return 200, {}, json.dumps({"voice_id": f"voice-{len(req.body)}", "requires_verification": False}).encode()
    if req.path.startswith("/v1/text-to-speech/"):
        return 200, {"Content-Type": "audio/pcm"}, tone_pcm(0.3)
    if req.path.startswith("/v1/text-to-voice/design"):
        preview = base64.b64encode(tone_pcm(1.0)).decode()
        return 200, {}, json.dumps({"previews": [{"audio_base_64": preview, "generated_voice_id": f"g{i}",
                                                  "media_type": "audio/pcm"} for i in range(3)], "text": "x"}).encode()
    return 404, {}, b"{}"


class ElevenLabs(ServiceCase):
    SERVICE = "elevenlabs"

    def test_elevenlabs_clones_once_per_clip(self):
        fake = self.serve(elevenlabs_answer)
        for _ in range(2):
            say = cloud.speaker(personas.voice_for(self.coach(), "elevenlabs"))
            say("Set your feet.", 42)
        adds = [r for r in fake.requests if r.path == "/v1/voices/add"]
        self.assertEqual(len(adds), 1)
        self.assertEqual(adds[0].headers["xi-api-key"], SECRET)
        self.assertIn(b'name="files"', adds[0].body)
        self.assertIn(b"multipart/form-data", adds[0].headers["content-type"].encode())
        with open(self.coach().clip, "rb") as f:
            self.assertIn(f.read(), adds[0].body)
        speech = [r for r in fake.requests if r.path.startswith("/v1/text-to-speech/")]
        self.assertTrue(all(r.path.startswith(f"/v1/text-to-speech/voice-") for r in speech))
        self.assertIn("output_format=pcm_24000", speech[0].path)
        with open(self.coach().clip, "ab") as f:   # a changed clip makes a new voice
            f.write(b"\x00\x00" * 100)
        cloud.speaker(personas.voice_for(self.coach(), "elevenlabs"))("Hi.", 42)
        self.assertEqual(len([r for r in fake.requests if r.path == "/v1/voices/add"]), 2)

    def test_elevenlabs_sends_neighbors_and_seed(self):
        fake = self.serve(elevenlabs_answer)
        pcm = cloud.speaker(personas.voice_for(self.coach(), "elevenlabs"))(
            "Two more.", 42, previous_text="Set your feet.", next_text="Rest.")
        body = json.loads([r for r in fake.requests if r.path.startswith("/v1/text-to-speech/")][0].body)
        self.assertEqual(body, {"text": "Two more.", "model_id": "eleven_multilingual_v2", "seed": 42,
                                "previous_text": "Set your feet.", "next_text": "Rest."})
        self.assertGreater(len(pcm), 0)

    def test_elevenlabs_design_previews_are_takes(self):
        import services.elevenlabs as el
        fake = self.serve(elevenlabs_answer)
        takes = el.design("A warm coach in her forties.", "Okay, set your feet.", 2, 7)
        self.assertEqual(len(takes), 2)
        self.assertEqual(takes[0][1], "x")   # the words the service says it spoke
        body = json.loads(fake.requests[0].body)
        self.assertEqual((body["voice_description"], body["seed"]), ("A warm coach in her forties.", 7))
        self.assertGreaterEqual(len(body["text"]), 100)
        self.assertIn("output_format=pcm_24000", fake.requests[0].path)


class Cartesia(ServiceCase):
    SERVICE = "cartesia"

    def test_cartesia_clones_once_and_requests_raw_pcm(self):
        def answer(req):
            if req.path == "/voices/clone":
                return 200, {}, json.dumps({"id": "cartesia-voice-1", "name": "x", "language": "en"}).encode()
            return 200, {"Content-Type": "audio/pcm"}, tone_pcm(0.3)
        fake = self.serve(answer)
        for _ in range(2):
            cloud.speaker(personas.voice_for(self.coach(), "cartesia"))("Set your feet.", 42)
        clones = [r for r in fake.requests if r.path == "/voices/clone"]
        self.assertEqual(len(clones), 1)
        self.assertIn(b'name="clip"', clones[0].body)
        self.assertIn(b'name="language"', clones[0].body)
        tts = [r for r in fake.requests if r.path == "/tts/bytes"][0]
        self.assertEqual(tts.headers["authorization"], f"Bearer {SECRET}")
        self.assertEqual(tts.headers["cartesia-version"], "2026-08-14")
        body = json.loads(tts.body)
        self.assertEqual(body["model_id"], "sonic-3.6")
        self.assertEqual(body["voice"], {"mode": "id", "id": "cartesia-voice-1"})
        self.assertEqual(body["output_format"], {"container": "raw", "encoding": "pcm_s16le", "sample_rate": 24000})
        self.assertEqual((body["transcript"], body["language"]), ("Set your feet.", "en"))


class Deepgram(ServiceCase):
    SERVICE = "deepgram"

    def stock(self):
        import context
        context.set_persona_setting(self.coach().path, "deepgram", "voice", "aura-2-apollo-en")
        return personas.voice_for(self.coach(), "deepgram")

    def test_deepgram_token_header_and_raw_pcm(self):
        fake = self.serve(lambda r: (200, {"Content-Type": "audio/l16;rate=24000"}, tone_pcm(0.3)))
        pcm = cloud.speaker(self.stock())("Set your feet.", 42)
        req = fake.requests[0]
        self.assertEqual(req.headers["authorization"], f"Token {SECRET}")
        self.assertTrue(req.path.startswith("/v1/speak?"))
        for part in ("model=aura-2-apollo-en", "encoding=linear16", "sample_rate=24000", "container=none"):
            self.assertIn(part, req.path)
        self.assertEqual(json.loads(req.body), {"text": "Set your feet."})
        self.assertGreater(len(pcm), 0)

    def test_deepgram_without_a_stock_voice_says_how_to_pick(self):
        with self.assertRaises(SystemExit) as e:
            personas.voice_for(self.coach(), "deepgram")
        self.assertIn("samples deepgram", str(e.exception.code))

    def test_deepgram_refuses_a_paragraph_over_2000_characters(self):
        fake = self.serve(lambda r: (200, {}, tone_pcm(0.3)))
        with self.assertRaises(cloud.ServiceError) as e:
            cloud.speaker(self.stock())("word " * 401, 42)
        self.assertEqual(e.exception.kind, "bad_request")
        self.assertIn("2000", str(e.exception))
        self.assertEqual(fake.requests, [])

    def test_a_stock_voice_has_its_own_cache_identity(self):
        a = self.stock()
        import context
        context.set_persona_setting(self.coach().path, "deepgram", "voice", "aura-2-thalia-en")
        b = personas.voice_for(self.coach(), "deepgram")
        self.assertNotEqual((a["key"], a["model"]), (b["key"], b["model"]))


class CloudRender(unittest.TestCase):
    """tools/render.py on a cloud route, end to end against the fake Fish server."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.home = os.path.join(self.d, "me")
        shutil.copytree(os.path.join(ROOT, "me.example"), self.home)
        persona_home(self.home)

    def render(self, url, *extra, **env):
        e = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
        e.update(SWEATCAST_HOME=self.home, SWEATCAST_FISH_URL=url, FISH_AUDIO_API_KEY=SECRET,
                 SWEATCAST_RETRY_WAIT="0", **env)
        return subprocess.run([sys.executable, os.path.join(ROOT, "tools", "render.py"), DRAFT, "--coach", "Coach Test",
                               "--engine", "fish", *extra], env=e, capture_output=True, text=True, timeout=120)

    def render_on(self, service, url, *extra):
        import keys
        e = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
        e.update({"SWEATCAST_HOME": self.home, f"SWEATCAST_{service.upper()}_URL": url,
                  keys.SERVICE_VARS[service]: SECRET, "SWEATCAST_RETRY_WAIT": "0"})
        return subprocess.run([sys.executable, os.path.join(ROOT, "tools", "render.py"), DRAFT, "--coach", "Coach Test",
                               "--engine", service, *extra], env=e, capture_output=True, text=True, timeout=120)

    def test_a_refused_clone_exits_4(self):
        with FakeService(lambda r: (401, {}, b'{"detail": {"message": "Invalid API key"}}')) as fake:
            out = self.render_on("elevenlabs", fake.url, "--out", os.path.join(self.d, "x.mp3"))
        self.assertEqual(out.returncode, cli.SERVICE, out.stdout + out.stderr)
        self.assertIn("ElevenLabs", out.stdout)
        self.assertNotIn("Traceback", out.stdout + out.stderr)

    def test_a_broken_answer_stops_sending_and_caches_nothing(self):
        with FakeService(lambda r: (200, {"Content-Type": "application/json"}, b'{"status": "queued"}')) as fake:
            out = self.render(fake.url, "--out", os.path.join(self.d, "x.mp3"))
        self.assertEqual(out.returncode, cli.ISSUES, out.stdout + out.stderr)
        self.assertLessEqual(len(fake.requests), 4)   # the queued paragraphs were never sent
        self.assertEqual(glob.glob(os.path.join(self.home, "workouts", ".audio-cache", "*.pcm")), [])

    def set_ceiling(self, n):
        prof = os.path.join(self.home, "profile.md")
        with open(prof, encoding="utf-8") as f:
            text = f.read()
        with open(prof, "w", encoding="utf-8") as f:
            f.write(text.replace("+++\n", f"+++\ncloud_max_chars = {n}\n", 1))

    def test_401_raises_auth_and_render_exits_4(self):
        with FakeService(lambda r: (401, {}, b'{"message": "Invalid api key"}')) as fake:
            out = self.render(fake.url, "--out", os.path.join(self.d, "x.mp3"))
        self.assertEqual(out.returncode, cli.SERVICE, out.stdout + out.stderr)
        self.assertIn("Fish Audio", out.stdout + out.stderr)
        self.assertIn("./sweatcast keys", out.stdout + out.stderr)

    def test_ceiling_stops_before_sending(self):
        self.set_ceiling(10)
        with FakeService(wav_answer) as fake:
            out = self.render(fake.url, "--out", os.path.join(self.d, "x.mp3"))
        self.assertEqual(out.returncode, cli.ISSUES, out.stdout + out.stderr)
        self.assertEqual(fake.requests, [])
        self.assertIn("cloud_max_chars", out.stdout)

    def test_follow_is_refused_on_a_cloud_route(self):
        with FakeService(wav_answer) as fake:
            for flag in ("--follow", "--clips-only"):
                out = self.render(fake.url, flag)
                self.assertEqual(out.returncode, cli.USAGE, flag)
                self.assertIn("billed", out.stdout + out.stderr)
            self.assertEqual(fake.requests, [])

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_key_never_reaches_records_logs_or_cache_keys(self):
        mp3 = os.path.join(self.d, "x.mp3")
        with FakeService(wav_answer) as fake:
            out = self.render(fake.url, "--out", mp3, "--tolerance", "1")
        self.assertIn(out.returncode, (0, cli.DRIFT), out.stdout + out.stderr)
        self.assertIn("Sending", out.stdout)
        texts = [out.stdout, out.stderr]
        for path in glob.glob(os.path.join(self.d, "*.build.json")) + \
                glob.glob(os.path.join(self.home, "workouts", ".logs", "*")) + \
                glob.glob(os.path.join(self.home, "personas", "*", "*.json")):
            with open(path, encoding="utf-8") as f:
                texts.append(f.read())
        self.assertFalse(any(SECRET in t for t in texts))
        with open(os.path.splitext(mp3)[0] + ".build.json") as f:
            record = json.load(f)
        self.assertEqual(record["route"], "fish")
        self.assertGreater(record["chars_sent"], 100)
        self.assertIn("usd_estimate", record)
        import render
        args = mock.Mock(coach="Coach Test", engine="fish", voice=None, model=None, seed=42)
        with mock.patch.object(personas.paths, "PERSONAS", os.path.join(self.home, "personas")), \
                mock.patch.object(personas.paths, "PROFILE", os.path.join(self.home, "profile.md")), \
                mock.patch.object(personas.paths, "ENV_FILE", os.path.join(self.home, ".env")), \
                mock.patch.dict(os.environ, {"FISH_AUDIO_API_KEY": SECRET}), \
                mock.patch.object(render, "check_pace_file"):
            a = render.setup_voice(args)[1]("Hello.")
            with mock.patch.dict(os.environ, {"FISH_AUDIO_API_KEY": "another-key"}):
                b = render.setup_voice(args)[1]("Hello.")
        self.assertEqual(a, b)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_interrupted_cloud_build_resumes_without_resending(self):
        state = {"ok": 3, "seen": 0}

        def answer(req):
            state["seen"] += 1
            if state["ok"] <= 0:
                return 503, {}, b"{}"
            state["ok"] -= 1
            return wav_answer(req)
        mp3 = os.path.join(self.d, "x.mp3")
        with FakeService(answer) as fake:
            first = self.render(fake.url, "--out", mp3, "--tolerance", "1")
            self.assertNotEqual(first.returncode, 0)
            cached = len(glob.glob(os.path.join(self.home, "workouts", ".audio-cache", "*.pcm")))
            self.assertEqual(cached, 3)
            sent_first = len([r for r in fake.requests if r.path == "/v1/tts"])
            state["ok"] = 1000
            second = self.render(fake.url, "--out", mp3, "--tolerance", "1")
        self.assertIn(second.returncode, (0, cli.DRIFT), second.stdout + second.stderr)
        first_to_render = int(first.stdout.split(" to render")[0].split()[-1])
        sent_second = len([r for r in fake.requests if r.path == "/v1/tts"]) - sent_first
        to_render = int(second.stdout.split(" to render")[0].split()[-1])
        self.assertEqual(to_render, first_to_render - 3)
        self.assertEqual(sent_second, to_render)
        self.assertIn("Sending", second.stdout)


if __name__ == "__main__":
    unittest.main()
