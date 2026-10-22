"""Fast checks for the text, timing, log and feed logic. No models, no audio rendering,
no network. Python 3.11 or later (the project's environment).

    ./sweatcast test        # or, in CI: python -m unittest discover tests
"""
import datetime as dt
import glob
import shutil
import subprocess
import json
import os
import re
import sys
import time
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import cache  # noqa: E402
import catalog  # noqa: E402

# The shipped catalog only: a listener's private movements in me/ never change what the tests see.
catalog.paths.MY_MOVEMENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "no-private-movements.toml")
import char_weight  # noqa: E402
import cli  # noqa: E402
import context  # noqa: E402
import coverage  # noqa: E402
import draft  # noqa: E402
import engines  # noqa: E402
import feeds  # noqa: E402
import paths  # noqa: E402
import render  # noqa: E402
import tts_build  # noqa: E402
import migrate  # noqa: E402
import voices  # noqa: E402
import youtube  # noqa: E402
from draft import CHIME, CHIME_SECONDS, PARAGRAPH_GAP, parse, plan, spans  # noqa: E402
from render import SR, assemble, chime, end_tone, silence  # noqa: E402
from tts_build import lint_line, structure_warnings, word_count  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Drafts that ship with the engine; personal drafts in me/ are never test fixtures.
DRAFTS = sorted(glob.glob(os.path.join(ROOT, "tests", "fixtures", "*.draft.txt"))) + [paths.SMOKE_DRAFT]


def secs(pcm):
    return len(pcm) / 2 / SR


def with_schema(text):
    """A context file's text as the current engine writes it, front matter first."""
    return context.with_front_matter(text)


def profile_text(settings_toml, prose="# Profile\n"):
    """A schema-2 profile: TOML settings, then prose."""
    return f"+++\nschema = {context.SCHEMA}\n{settings_toml}\n+++\n{prose}"


def write_file(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def private_pattern():
    with open(os.path.join(ROOT, "tools", "hooks", "private-paths"), encoding="utf-8") as f:
        return next(l.strip() for l in f if l.strip() and not l.startswith("#"))


class Parse(unittest.TestCase):
    def test_segments_and_paragraphs(self):
        segs = parse("@@ 60 | Opening\nHello there.\nStill one paragraph.\n\nSecond one.\n@@ 30 | Next\nGo.\n")
        self.assertEqual([(s["seconds"], s["label"]) for s in segs], [(60, "Opening"), (30, "Next")])
        self.assertEqual(plan(segs[0]), [[("Hello there. Still one paragraph.", 0.0)], [("Second one.", 0.0)]])

    def test_text_before_first_marker_is_an_error(self):
        with self.assertRaises(SystemExit):
            parse("stray words\n@@ 60 | A\nHi.\n")

    def test_no_markers_is_an_error(self):
        with self.assertRaises(SystemExit):
            parse("Just text.\n")


class Spans(unittest.TestCase):
    def test_pause_units_and_default(self):
        self.assertEqual(spans("Set up. [pause 3s] Go. [pause 500ms] Now [pause] end"),
                         [("Set up.", 3.0), ("Go.", 0.5), ("Now", draft.PAUSE_DEFAULT), ("end", 0.0)])

    def test_pause_is_capped(self):
        self.assertEqual(spans("Rest. [pause 30s]"), [("Rest.", draft.PAUSE_MAX)])

    def test_leading_and_back_to_back_pauses(self):
        self.assertEqual(spans("[pause 2s] Breathe."), [("", 2.0), ("Breathe.", 0.0)])
        self.assertEqual(spans("Hold. [pause 2s] [pause 3s] Out."), [("Hold.", 5.0), ("Out.", 0.0)])

    def test_chime_marker(self):
        self.assertEqual(spans("Start at the bell. [chime] Work."),
                         [("Start at the bell.", 0.0), (CHIME, 0.0), ("Work.", 0.0)])
        # A pause after the bell is silence after the bell.
        self.assertEqual(spans("[chime] [pause 1s] Go."), [(CHIME, 1.0), ("Go.", 0.0)])
        self.assertEqual(spans("Rest. [pause 2s] [Chime]"), [("Rest.", 2.0), (CHIME, 0.0)])

    def test_chime_is_not_spoken_or_counted(self):
        self.assertFalse(draft.spoken(CHIME))
        self.assertFalse(draft.spoken(""))
        self.assertTrue(draft.spoken("Go."))
        self.assertEqual(lint_line(1, "Work starts at the bell. [chime] Go."), [])
        self.assertEqual(word_count([(1, "Ready. [chime] Go now.")]), 3)


class Lint(unittest.TestCase):
    def test_clean_line(self):
        self.assertEqual(lint_line(1, "Three sets of ten. [pause 3s] Three... two... one... switch."), [])

    def test_catches_tts_hazards(self):
        joined = " ".join(lint_line(1, "Do 3 sets, 25 lbs e.g. # now"))
        for expected in ("digits", "abbreviation 'lbs'", "abbreviation 'e.g.'", "forbidden characters"):
            self.assertIn(expected, joined)
        self.assertIn("markdown", " ".join(lint_line(1, "- a bullet")))
        self.assertIn("more than three dots", " ".join(lint_line(1, "Wait.... go")))

    def test_word_count_ignores_pauses_and_counts_hyphenated_as_one(self):
        self.assertEqual(word_count([(1, "Single-leg bridge. [pause 3s] Don't stop.")]), 4)


class Structure(unittest.TestCase):
    """Coaching-structure warnings (warn-only unless --strict)."""

    def test_clean_draft_has_no_warnings(self):
        segs = parse("@@ 60 | A\nWelcome. Three... two... one... go.\n"
                     "@@ 60 | B\nMinute two of five. Squats. Good.\n"
                     "@@ 60 | C\nWarm-up done. Rows now. Nice work.\n"
                     "@@ 30 | Close\nThat's the session. Good.\n")
        self.assertEqual(structure_warnings(segs), [])

    def test_missing_locator(self):
        segs = parse("@@ 60 | A\nWelcome.\n@@ 60 | B\nSquats now. Go.\n")
        warnings = structure_warnings(segs)
        self.assertEqual(len(warnings), 1)
        self.assertIn("segment 2", warnings[0])
        self.assertIn("locator", warnings[0])

    def test_two_countdowns_in_a_segment(self):
        segs = parse("@@ 60 | A\nThree... two... one... go. Later. Three… two… one… stop.\n")
        self.assertIn("2 countdowns", " ".join(structure_warnings(segs)))

    def test_exclamation_points(self):
        segs = parse("@@ 60 | A\nGo! Push! Yes! Done.\n")
        self.assertIn("3 exclamation points", " ".join(structure_warnings(segs)))

    def test_repeated_praise(self):
        segs = parse("@@ 60 | A\nGood. Squats.\n@@ 60 | B\nMinute two. Nice work. Good.\n"
                     "@@ 60 | C\nMinute three. Good!\n")
        joined = " ".join(structure_warnings(segs))
        self.assertIn('praise "good" used 3 times', joined)
        self.assertNotIn("nice work", joined)

    def test_existing_drafts_only_warn(self):
        # Warn-only: the checks never change what an existing draft exports.
        for path in DRAFTS:
            with open(path, encoding="utf-8") as f:
                segs = parse(f.read())
            for w in structure_warnings(segs):
                self.assertIsInstance(w, str)

    def test_spoken_seconds_counts_an_inline_chime(self):
        seg = parse("@@ 10 | A\nab [chime] cd\n")[0]
        v = {"engine": "chatterbox", "key": "x", "name": "x"}
        with mock.patch("voices.pace", return_value=(10.0, True)):
            got = tts_build.spoken_seconds(seg, v)
        self.assertAlmostEqual(got, 2 * (2 / 10.0 + voices.MLX_EDGE) + CHIME_SECONDS, places=6)


class Assemble(unittest.TestCase):
    """Layout of rendered clips on the plan's clock (render.assemble)."""

    @staticmethod
    def fake_clip(text):
        # One second of audio per word, nonzero so it can be told from silence.
        return b"\x01\x00" * (len(text.split()) * SR)

    def segs(self, draft):
        return parse(draft)

    def test_short_segment_widens_breaks_then_ends_early(self):
        segs = self.segs("@@ 20 | A\none two three\n\nfour five\n@@ 15 | B\nsix\n")
        pcm, rows, drift = assemble(segs, self.fake_clip)
        self.assertAlmostEqual(rows[0][2], 5 + PARAGRAPH_GAP, places=3)
        # A: speech, one break widened by the cap, a short tail. B: speech and a tail.
        a = 5 + PARAGRAPH_GAP + draft.MAX_EXTRA_GAP + draft.END_TAIL
        b = 1 + draft.END_TAIL
        self.assertAlmostEqual(secs(pcm), a + b, places=3)
        self.assertAlmostEqual(drift, (a + b) / 35 - 1, places=3)
        self.assertEqual(rows[0][4], "  <-- short")

    def test_little_spare_time_fills_the_slot(self):
        segs = self.segs("@@ 5 | A\none two three four\n")
        pcm, rows, drift = assemble(segs, self.fake_clip)
        self.assertAlmostEqual(secs(pcm), 5.0, places=3)
        self.assertAlmostEqual(drift, 0.0, places=3)
        self.assertEqual(rows[0][4], "")

    def test_spare_time_goes_into_paragraph_breaks_up_to_the_cap(self):
        segs = self.segs("@@ 20 | A\none\n\ntwo\n")
        pcm, _, _ = assemble(segs, self.fake_clip)
        gap = draft.MAX_EXTRA_GAP + PARAGRAPH_GAP
        # The second word starts after one second of speech plus the widened break.
        self.assertEqual(pcm[int((1 + gap) * SR) * 2 - 2:int((1 + gap) * SR) * 2], b"\x00\x00")
        self.assertEqual(pcm[int((1 + gap) * SR) * 2 + 2:int((1 + gap) * SR) * 2 + 4], b"\x01\x00")

    def test_long_segment_is_flagged_and_the_next_pays_it_back(self):
        segs = self.segs("@@ 3 | A\none two three four five\n@@ 10 | B\nsix\n")
        pcm, rows, _ = assemble(segs, self.fake_clip)
        self.assertEqual(rows[0][4], "  <-- long")
        # A runs two seconds late, so B keeps only what's left of its spare time.
        self.assertAlmostEqual(secs(pcm), 5 + 1 + draft.END_TAIL, places=3)

    def test_small_overrun_is_not_flagged(self):
        segs = self.segs("@@ 20 | A\n" + " ".join(["w"] * 21) + "\n")
        _, rows, drift = assemble(segs, self.fake_clip)
        self.assertEqual(rows[0][4], "")
        self.assertAlmostEqual(drift, 0.05, places=3)

    def test_a_hold_keeps_the_segment_full_and_silent_where_it_falls(self):
        segs = self.segs("@@ 30 | A\ngo [chime] push [hold] [chime] easy\n@@ 10 | B\nsix\n")
        pcm, rows, _ = assemble(segs, self.fake_clip, bell=b"\x02\x00" * SR)
        # A: three words and two one-second bells, 25 s of hold; then B ends early as usual
        self.assertAlmostEqual(secs(pcm), 30 + 1 + draft.END_TAIL, places=3)
        self.assertEqual(rows[0][4], "")   # a held segment is never flagged short
        quiet = pcm[int(4 * SR) * 2:int(28 * SR) * 2]   # after "go", bell, "push": the hold
        self.assertEqual(set(bytes(quiet)), {0})
        self.assertEqual(bytes(pcm[int(29.5 * SR) * 2:int(29.5 * SR) * 2 + 2]), b"\x01\x00")   # "easy" ends A
        predicted = draft.layout([(5, 0, 30, 1), (1, 0, 10)])
        self.assertAlmostEqual(secs(pcm), sum(length for _, length in predicted), places=3)

    def test_a_fixed_hold_is_exact_silence_and_the_rest_goes_to_the_bare_one(self):
        segs = self.segs("@@ 60 | A\ngo [hold 20s] stop [hold] next\n@@ 10 | B\nsix\n")
        pcm, rows, _ = assemble(segs, self.fake_clip)
        # A: three words, twenty fixed seconds, and the bare hold takes the other 37
        self.assertAlmostEqual(secs(pcm), 60 + 1 + draft.END_TAIL, places=3)
        self.assertEqual(set(bytes(pcm[int(1 * SR) * 2:int(21 * SR) * 2])), {0})
        self.assertEqual(bytes(pcm[int(21 * SR) * 2:int(21 * SR) * 2 + 2]), b"\x01\x00")   # "stop" at 21 s
        only = self.segs("@@ 30 | A\ngo [hold 10s] stop\n")
        pcm, _, _ = assemble(only, self.fake_clip)
        self.assertAlmostEqual(secs(pcm), 30, places=3)   # held, no bare hold: the spare goes to the end

    def test_hold_is_a_marker_not_speech(self):
        spans = draft.spans("Push. [hold] [chime] Easy.")
        self.assertEqual([t for t, _ in spans], ["Push.", draft.HOLD, CHIME, "Easy."])
        self.assertFalse(draft.spoken(draft.HOLD))
        self.assertEqual(draft.holds(parse("@@ 10 | A\none [hold] two [hold]\n")[0]), (2, 2))
        self.assertEqual(draft.spans("Go. [hold 20s] Stop."), [("Go.", 0.0), (draft.HOLD, 20.0), ("Stop.", 0.0)])
        self.assertEqual(draft.fill_flag(2, 30, held=True), "")
        self.assertEqual(draft.fill_flag(2, 30), "short")

    def test_layout_matches_assemble(self):
        segs = self.segs("@@ 20 | A\none two\n\nthree\n@@ 4 | B\nfour five six\n\nseven\n@@ 30 | C\neight\n")
        pcm, _, _ = assemble(segs, self.fake_clip)
        predicted = draft.layout([(3 + PARAGRAPH_GAP, 1, 20), (4 + PARAGRAPH_GAP, 1, 4), (1, 0, 30)])
        self.assertAlmostEqual(secs(pcm), sum(length for _, length in predicted), places=3)

    def test_chime_opens_every_segment_but_the_first(self):
        segs = self.segs("@@ 5 | A\none\n@@ 5 | B\ntwo\n")
        lead = chime()
        self.assertAlmostEqual(secs(lead), CHIME_SECONDS, places=3)
        pcm, rows, _ = assemble(segs, self.fake_clip, lead=lead)
        self.assertEqual(bytes(pcm[:4]), b"\x01\x00\x01\x00")          # A starts with the voice
        b_start = int((1 + draft.END_TAIL) * SR) * 2                    # A ends early, after its tail
        self.assertEqual(bytes(pcm[b_start:b_start + len(lead)]), lead)   # B starts with the bell
        self.assertAlmostEqual(rows[1][2], 1 + CHIME_SECONDS, places=3)
        self.assertAlmostEqual(secs(pcm), 2 * (1 + draft.END_TAIL) + CHIME_SECONDS, places=3)

    def test_chime_is_soft(self):
        import struct
        lead = chime()
        peak = max(abs(v) for v in struct.unpack(f"<{len(lead) // 2}h", lead))
        self.assertLess(peak, 0.15 * 32767)
        self.assertGreater(peak, 0.05 * 32767)

    def test_silence_never_negative(self):
        self.assertEqual(silence(-1), b"")

    def test_chime_marker_rings_inside_a_segment(self):
        segs = self.segs("@@ 10 | A\none [chime] two\n")
        bell = chime()
        pcm, rows, _ = assemble(segs, self.fake_clip, bell=bell)
        at = 1 * SR * 2   # after one second of speech
        self.assertEqual(bytes(pcm[at:at + len(bell)]), bell)
        self.assertAlmostEqual(rows[0][2], 2 + CHIME_SECONDS, places=3)
        self.assertAlmostEqual(secs(pcm), 2 + CHIME_SECONDS + draft.END_TAIL, places=3)

    def test_end_tone_follows_the_last_segment(self):
        segs = self.segs("@@ 5 | A\none\n")
        tail = end_tone()
        pcm, _, _ = assemble(segs, self.fake_clip, tail=tail)
        self.assertAlmostEqual(secs(pcm), 1 + draft.END_TAIL + secs(tail), places=3)
        self.assertEqual(bytes(pcm[-len(tail):]), tail)
        self.assertGreater(secs(tail), secs(chime()))   # longer and rising, so it can't pass for a bell


class Coverage(unittest.TestCase):
    LOG = """# Workout log

## Sessions
- 2026-10-19 | 15 min | Home | V | goblet squat, seated bent-over rowing | topics
- 2026-10-20 | 20 min | Home | V | incline push-up, goblet squat, seated punching finisher, mystery move | topics

## Feedback
- 2026-10-20 | not | a | session | line
"""

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".md")
        with os.fdopen(fd, "w") as f:
            f.write(with_schema(self.LOG))

    def tearDown(self):
        os.remove(self.path)

    def test_reads_only_the_sessions_section(self):
        log = context.sessions(self.path)
        self.assertEqual([s.date for s in log], ["2026-10-19", "2026-10-20"])

    def test_patterns_and_gaps(self):
        hit, unmapped = coverage.coverage(context.sessions(self.path)[-1].movements)
        self.assertIn("goblet squat", hit["squat"])
        self.assertIn("incline push-up", hit["horizontal-push"])
        self.assertEqual(hit["hinge"], [])
        self.assertEqual(list(hit), catalog.load().patterns)
        self.assertEqual(unmapped, ["mystery move"])   # the finisher is skipped on purpose

    def test_fallback_keywords_by_pattern(self):
        cat = catalog.load()
        self.assertEqual(coverage.patterns_of("seated bent-over rowing", cat), ["horizontal-pull"])
        self.assertNotIn("horizontal-push", coverage.patterns_of("overhead press", cat))
        self.assertEqual(coverage.patterns_of("mystery move", cat), [])

    def test_side_words_and_capitals_resolve(self):
        self.assertEqual(coverage.patterns_of("Right Goblet Squat"), coverage.patterns_of("goblet squat"))
        self.assertIn("squat", coverage.patterns_of("right goblet squat"))

    def test_finishers_and_skills_are_not_unmapped(self):
        _, unmapped = coverage.coverage(["seated punching finisher", "box breathing", "mystery move"])
        self.assertEqual(unmapped, ["mystery move"])

    def test_week_counts_sessions_per_pattern(self):
        counts = coverage.week(context.sessions(self.path), dt.date(2026, 10, 21))
        self.assertEqual(counts["squat"], 2)
        self.assertEqual(counts["horizontal-push"], 1)
        self.assertEqual(counts["horizontal-pull"], 1)
        self.assertEqual(counts["hinge"], 0)
        self.assertEqual(list(counts), catalog.load().patterns)

    def test_week_window_excludes_old_sessions(self):
        counts = coverage.week(context.sessions(self.path), dt.date(2026, 10, 26))
        self.assertEqual(counts["horizontal-pull"], 0)   # the 19th is 7 days back: outside
        self.assertEqual(counts["horizontal-push"], 1)


class CharWeight(unittest.TestCase):
    def test_basic_weights(self):
        self.assertAlmostEqual(char_weight.weight("ab c."), 1 + 1 + 0.2 + 1 + 0.5)
        self.assertAlmostEqual(char_weight.weight("7"), 3.5)
        self.assertAlmostEqual(char_weight.weight("é"), 1.0)
        self.assertAlmostEqual(char_weight.weight("e\u0301"), 1.0)   # NFC composes the accent


class SeedPace(unittest.TestCase):
    def test_median_of_measured_voices_only(self):
        data = {"a|chatterbox|m": {"weight": 1460.0, "seconds": 100.0},
                "b|qwen3|m": {"weight": 1200.0, "seconds": 100.0},
                "c|qwen3|m": {"weight": 1600.0, "seconds": 100.0},
                "short|qwen3|m": {"weight": 10.0, "seconds": 5.0},       # too little speech to count
                "old": {"name": "x", "ref_text": "hi", "ref_tokens": 250}}  # an entry with no rate
        self.assertAlmostEqual(voices.seed_pace(data), 14.6)

    def test_default_when_nothing_is_measured(self):
        self.assertEqual(voices.seed_pace({}), voices.DEFAULT_PACE)


class Voices(unittest.TestCase):
    def make(self, folder, name, conf):
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, name + ".wav"), "wb") as f:
            f.write(b"RIFF" + name.encode())
        with open(os.path.join(folder, name + ".txt"), "w") as f:
            f.write("Set your feet.")
        if conf is not None:
            with open(os.path.join(folder, name + ".json"), "w") as f:
                json.dump(conf, f)

    def test_private_voice_wins_and_models_default(self):
        with tempfile.TemporaryDirectory() as d:
            mine, shipped = os.path.join(d, "me"), os.path.join(d, "repo")
            self.make(shipped, "Coach", {"engine": "qwen3"})
            self.make(mine, "coach", {"engine": "chatterbox", "model": "x/turbo", "revision": "abc"})
            self.make(shipped, "Other", {"engine": "qwen3"})
            with mock.patch.object(voices, "VOICE_DIRS", (mine, shipped)):
                v = voices.lookup("COACH")
                self.assertEqual((v["engine"], v["model"], v["revision"]), ("chatterbox", "x/turbo", "abc"))
                self.assertEqual(voices.lookup("other")["model"], voices.STANDARD_MODELS["qwen3"])
                self.assertEqual(voices.names(), ["Other", "coach"])

    def test_aliases_find_the_renamed_voice(self):
        with tempfile.TemporaryDirectory() as d:
            self.make(d, "Chatterbox Coach", {"engine": "chatterbox", "aliases": ["Coach E"]})
            with mock.patch.object(voices, "VOICE_DIRS", (d,)):
                self.assertEqual(voices.lookup("coach e")["name"], "Chatterbox Coach")
                self.assertEqual(voices.names(), ["Chatterbox Coach"])

    def test_old_names_still_work_for_shipped_voices(self):
        self.assertEqual(voices.lookup("Coach E")["name"], "Chatterbox Coach")
        self.assertEqual(voices.lookup("Coach G")["name"], "Qwen3 Coach")

    def test_missing_settings_or_bad_engine(self):
        with tempfile.TemporaryDirectory() as d:
            self.make(d, "NoJson", None)
            self.make(d, "Omni", {"engine": "omnivoice"})
            with mock.patch.object(voices, "VOICE_DIRS", (d,)):
                for name in ("NoJson", "Omni", "Nobody"):
                    with self.assertRaises(SystemExit):
                        voices.lookup(name)

    def test_shipped_voices_pin_a_revision(self):
        for name in voices.names():
            v = voices.lookup(name)
            if v["ref_audio"].startswith(os.path.join(ROOT, "voices")):
                self.assertRegex(v["revision"] or "", r"^[0-9a-f]{40}$", name)


class PinnedExtras(unittest.TestCase):
    def fake_hub(self, fail=False):
        calls = []

        class Hub:
            @staticmethod
            def snapshot_download(repo, revision=None):
                if fail:
                    raise OSError("offline")
                calls.append(("snapshot", repo, revision))

            @staticmethod
            def hf_hub_download(repo_id=None, filename=None, revision=None):
                calls.append(("file", repo_id, revision))
                return "/cache/" + filename
        return Hub, calls

    def test_engine_extras_load_at_the_pinned_revision(self):
        hub, calls = self.fake_hub()
        repo, rev = voices.ENGINE_EXTRAS["chatterbox"][0]
        original = hub.hf_hub_download
        with engines.pinned_extras("chatterbox", hub):
            hub.hf_hub_download(repo_id=repo, filename="model.safetensors")
            hub.hf_hub_download(repo_id="other/repo", filename="x")
        self.assertEqual(calls, [("snapshot", repo, rev), ("file", repo, rev), ("file", "other/repo", None)])
        self.assertIs(hub.hf_hub_download, original)   # restored afterwards

    def test_a_pinned_extra_that_cant_be_fetched_stops_the_render(self):
        hub, _ = self.fake_hub(fail=True)
        with self.assertRaises(SystemExit):
            with engines.pinned_extras("chatterbox", hub):
                pass

    def test_qwen3_has_no_extras(self):
        hub, calls = self.fake_hub(fail=True)
        with engines.pinned_extras("qwen3", hub):
            pass
        self.assertEqual(calls, [])


class FreshFork(unittest.TestCase):
    """A new copy of the repo, with only me.example/ copied: the tools run on it."""

    def run_tool(self, home, *args):
        env = dict(os.environ, SWEATCAST_HOME=home, SWEATCAST_PYTHON=sys.executable)
        return subprocess.run(["sh", "sweatcast", *args], cwd=ROOT, env=env,
                              capture_output=True, text=True, timeout=60)

    def test_example_context_works(self):
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(paths.EXAMPLE, home)
            out = self.run_tool(home, "coverage")
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("No sessions", out.stdout)
            out = self.run_tool(home, "lint", os.path.join("tests", "fixtures", "example.draft.txt"),
                                "--out", os.path.join(d, "x.txt"), "--force")   # short on purpose
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
            self.assertNotIn("  line ", out.stdout)   # no text-to-speech problems
            self.assertTrue(os.path.exists(os.path.join(d, "x.txt")))
            prof = context.profile(os.path.join(home, "profile.md"))
            self.assertEqual(len(feeds.config(prof)), 6)          # the three [hint] feeds are skipped
            self.assertIn("MindYourDecisions", youtube.handles("Puzzles", profile=os.path.join(home, "profile.md")))
            self.assertEqual(context.default_voice(prof), "Chatterbox Coach")
            self.assertIn("deliver_to", prof.settings)

    def test_missing_context_says_run_setup(self):
        with tempfile.TemporaryDirectory() as d:
            out = self.run_tool(os.path.join(d, "nowhere"), "coverage")
            self.assertNotEqual(out.returncode, 0)
            self.assertIn("./sweatcast setup", out.stderr)

    def test_nothing_personal_is_tracked(self):
        if not os.path.isdir(os.path.join(ROOT, ".git")):
            self.skipTest("not a git checkout")
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
        pattern = private_pattern()
        self.assertTrue(re.search(pattern, "knowledge/health.md"))   # the one CI used to miss
        self.assertEqual([p for p in tracked if re.search(pattern, p)], [])


class LogFields(unittest.TestCase):
    LOG = """## Sessions
- 2026-10-19 | 15 min | Home | V | seated curl, rows | deep dive: news, x
- 2026-10-20 | 20 min | Home | V | seated curl, squat | topics | format: circuits | loads: seated curl = fifteens, three down; squat = bodyweight
- 2026-10-21 | 20 min | Home | V | seated curl | topics | format: rolling minutes | loads: seated curl = twenties

## Feedback
"""

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".md")
        with os.fdopen(fd, "w") as f:
            f.write(with_schema(self.LOG))

    def tearDown(self):
        os.remove(self.path)

    def test_rpe_round_trips(self):
        s = context.Session("2026-10-21", 20, "Home", "V", ["goblet squat"], "topics", rpe={"goblet squat": "7"})
        line = s.to_line()
        self.assertIn("| rpe: goblet squat = 7", line)
        self.assertEqual(context.parse_session(line).rpe, {"goblet squat": "7"})
        self.assertEqual(context.parse_session(line.replace("= 7", "= 7 to 8")).rpe, {"goblet squat": "7 to 8"})

    def test_rpe_rejects_separators(self):
        for bad in ("7; 8", "7 | 8"):
            s = context.Session("2026-10-21", 20, "Home", "V", ["goblet squat"], "topics", rpe={"goblet squat": bad})
            self.assertTrue(s.problems(), bad)

    def test_format_and_loads(self):
        e = context.sessions(self.path)
        self.assertIsNone(e[0].format)
        self.assertEqual(e[0].loads, {})
        self.assertEqual(e[1].format, "circuits")
        self.assertEqual(e[1].loads, {"seated curl": "fifteens, three down", "squat": "bodyweight"})
        self.assertEqual((e[1].date, e[1].minutes, e[1].movements), ("2026-10-20", 20, ["seated curl", "squat"]))

    def test_newest_load_wins(self):
        loads = coverage.last_loads(context.sessions(self.path))
        self.assertEqual(loads["seated curl"], ("2026-10-21", "twenties"))
        self.assertEqual(loads["squat"], ("2026-10-20", "bodyweight"))


class YouTube(unittest.TestCase):
    def test_puzzles_line_and_fresh_filter(self):
        with tempfile.TemporaryDirectory() as d:
            prof = os.path.join(d, "profile.md")
            write_file(prof, profile_text('youtube_favorites = ["chanA", "@chanB"]\n'
                                          'puzzles = ["MindYourDecisions", "[a channel]"]'))
            self.assertEqual(youtube.handles(profile=prof), ["chanA", "chanB"])
            self.assertEqual(youtube.handles("Puzzles", profile=prof), ["MindYourDecisions"])
            os.makedirs(os.path.join(d, "puzzles"))
            open(os.path.join(d, "puzzles", "used1.md"), "w").close()
            seen = youtube.used(os.path.join(d, "puzzles"))
        entries = [{"id": "used1", "duration": 300}, {"id": "short", "duration": 40},
                   {"id": "ok1", "duration": 240}, {"id": "long", "duration": 3600}, {"id": "ok2", "duration": 600}]
        got = youtube.fresh(entries, seen, 60, youtube.PUZZLE_MAX_SECONDS, 5)
        self.assertEqual([e["id"] for e in got], ["ok1", "ok2"])
        self.assertEqual([e["id"] for e in youtube.fresh(entries, seen, 60, 1800, 1)], ["ok1"])

    def test_series_state(self):
        self.assertEqual(youtube.series_state("# T\n- Channel: x\n"), (1, 1))
        self.assertEqual(youtube.series_state("# T\n- Parts: 3\n"), (3, 0))
        self.assertEqual(youtube.series_state("# T\n- Parts: 3\n- Parts done: 2\n"), (3, 2))

    def test_in_progress_and_done(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "abc.md"), "w") as f:
                f.write("# Long One\n- Channel: x\n- Parts: 2\n\n## Part one\n")
            with open(os.path.join(d, "old.md"), "w") as f:
                f.write("# Short\n- Channel: y\n")
            self.assertEqual(youtube.in_progress(d), [("abc", 1, 2, "Long One")])
            self.assertEqual(youtube.mark_done("abc", d), (1, 2))
            self.assertEqual(youtube.in_progress(d), [("abc", 2, 2, "Long One")])
            self.assertEqual(youtube.mark_done("abc", d), (2, 2))
            self.assertEqual(youtube.in_progress(d), [])
            with self.assertRaises(SystemExit):
                youtube.mark_done("old", d)

    def test_paragraphs_break_at_sentence_ends(self):
        events = [{"segs": [{"utf8": "word " * 119 + "end."}]}, {"segs": [{"utf8": "[Music] next part"}]}]
        out = youtube.paragraphs(events)
        self.assertEqual(len(out), 2)
        self.assertTrue(out[0].endswith("end."))
        self.assertEqual(out[1], "next part")

    def test_caption_track_prefers_the_creators(self):
        info = {"subtitles": {"en": [{"ext": "vtt", "url": "v"}, {"ext": "json3", "url": "mine"}]},
                "automatic_captions": {"en": [{"ext": "json3", "url": "asr"}]}}
        self.assertEqual(youtube.caption_track(info), ("mine", True))
        self.assertEqual(youtube.caption_track({"automatic_captions": info["automatic_captions"]}), ("asr", False))
        self.assertEqual(youtube.caption_track({}), (None, False))


class Feeds(unittest.TestCase):
    NOW = dt.datetime(2026, 10, 21, 16, 0, tzinfo=dt.timezone.utc)

    def test_config(self):
        p = context.Profile({"feeds": [
            {"label": "Weather, home", "kind": "weather", "value": "39.9, -75.1"},
            {"label": "Devils", "kind": "ESPN", "value": "hockey/nhl/nj"},
            {"label": "Local", "kind": "rss", "value": "https://example.org/feed/"},
            {"label": "Bad", "kind": "ftp", "value": "x"},
            {"label": "[Team]", "kind": "espn", "value": "[sport/league/team]"},   # not filled in: skipped
            {"label": "Empty", "kind": "rss", "value": ""}]}, "")
        self.assertEqual(feeds.config(p), [("Weather, home", "weather", "39.9, -75.1"),
                                           ("Devils", "espn", "hockey/nhl/nj"),
                                           ("Local", "rss", "https://example.org/feed/")])

    def test_rss_and_atom(self):
        rss = b"""<?xml version="1.0"?><rss><channel>
            <item><title>New &amp; old</title><link>https://a/1</link>
              <pubDate>Wed, 21 Oct 2026 10:00:00 -0400</pubDate><description>&lt;p&gt;Hello &lt;b&gt;there&lt;/b&gt;&lt;/p&gt;</description></item>
            <item><title>Stale</title><link>https://a/2</link><pubDate>Mon, 12 Oct 2026 10:00:00 GMT</pubDate></item>
            <item><title>Undated</title><link>https://a/3</link></item>
            </channel></rss>"""
        since = self.NOW - dt.timedelta(hours=72)
        items = feeds.parse_rss(rss, since)
        self.assertEqual([i["title"] for i in items], ["New & old"])
        self.assertEqual(items[0]["summary"], "Hello there")
        atom = b"""<feed xmlns="http://www.w3.org/2005/Atom">
            <entry><title>Paper</title><link rel="alternate" href="https://b/1"/>
              <published>2026-10-20T12:00:00Z</published><summary>Qubits.</summary></entry></feed>"""
        items = feeds.parse_rss(atom, since)
        self.assertEqual((items[0]["title"], items[0]["link"], items[0]["summary"]), ("Paper", "https://b/1", "Qubits."))

    def test_weekly_feed_reaches_back_eight_days_and_keeps_two(self):
        rss = b"""<?xml version="1.0"?><rss><channel>
            <item><title>This week</title><link>https://p/1</link><pubDate>Sun, 18 Oct 2026 07:00:00 -0400</pubDate></item>
            <item><title>Last week</title><link>https://p/2</link><pubDate>Sun, 11 Oct 2026 07:00:00 -0400</pubDate></item>
            <item><title>Older</title><link>https://p/3</link><pubDate>Fri, 16 Oct 2026 07:00:00 -0400</pubDate></item>
            <item><title>Ancient</title><link>https://p/4</link><pubDate>Sun, 04 Oct 2026 07:00:00 -0400</pubDate></item>
            </channel></rss>"""
        with mock.patch.object(feeds, "fetch", return_value=rss):
            lines = feeds.gather(("Puzzle", "weekly", "https://p/feed"), self.NOW, self.NOW - dt.timedelta(hours=72))
        self.assertEqual(len(lines), 2)
        self.assertIn("This week", lines[0])
        self.assertIn("Older", lines[1])
        self.assertIn(("Puzzle, x", "weekly", "https://p/feed"), feeds.config(context.Profile(
            {"feeds": [{"label": "Puzzle, x", "kind": "weekly", "value": "https://p/feed"}]}, "")))

    def test_espn_results_and_upcoming(self):
        def ev(i, date, home, away, hs=None, as_=None, done=True, hw=None):
            return {"id": i, "date": date, "competitions": [{
                "status": {"type": {"completed": done, "description": "Final" if done else "Scheduled"}},
                "venue": {"fullName": "Arena"},
                "competitors": [
                    {"homeAway": "home", "team": {"displayName": home}, "winner": hw,
                     "score": {"displayValue": hs} if hs else None},
                    {"homeAway": "away", "team": {"displayName": away}, "winner": (not hw) if hw is not None else None,
                     "score": {"displayValue": as_} if as_ else None}]}]}
        doc = {"team": {"displayName": "Devils"}, "events": [
            ev("1", "2026-10-20T23:00Z", "Devils", "Avalanche", "4", "3", hw=True),
            ev("2", "2026-10-17T17:00Z", "Capitals", "Devils", "4", "2", hw=True),
            ev("3", "2026-10-01T23:00Z", "Devils", "Flyers", "3", "2", hw=True),        # too old
            ev("4", "2026-10-22T23:00Z", "Devils", "Ducks", done=False),
            ev("5", "2026-11-20T23:00Z", "Devils", "Kings", done=False)]}             # too far out
        doc2 = {"events": [ev("4", "2026-10-22T23:00Z", "Devils", "Ducks", done=False),  # duplicate
                           ev("6", "2026-10-18T18:30Z", "Devils", "Charlotte", "2", "2", hw=False)]}
        team, results, upcoming = feeds.parse_espn([doc, doc2], self.NOW)
        self.assertEqual(team, "Devils")
        self.assertEqual([t for _, t in results], [
            "Avalanche 3, at Devils 4 (Final; Devils won)",
            "Charlotte 2, at Devils 2 (Final; Devils drew)",
            "Devils 2, at Capitals 4 (Final; Devils lost)"])
        self.assertEqual([t for _, t in upcoming], ["Ducks at Devils, Arena"])

    def test_weather(self):
        d = {"current": {"temperature_2m": 59.9, "weather_code": 0},
             "daily": {"temperature_2m_max": [66.2, 68], "temperature_2m_min": [48, 42.4],
                       "weather_code": [3, 61], "precipitation_probability_max": [0, 70],
                       "sunset": ["2026-10-21T18:12", "2026-10-22T18:10"]}}
        self.assertEqual(feeds.parse_weather(d), [
            "Now: 60 degrees, clear",
            "Today: high 66, low 48, overcast, 0 percent chance of rain, sunset 18:12",
            "Tomorrow: high 68, low 42, light rain, 70 percent chance of rain, sunset 18:10"])

    def test_on_this_day(self):
        d = {"selected": [{"year": 1959, "text": "The Guggenheim Museum (pictured) opened.",
                           "pages": [{"content_urls": {"desktop": {"page": "https://w/G"}}}]}]}
        self.assertEqual(feeds.parse_onthisday(d), [(1959, "The Guggenheim Museum opened.", "https://w/G")])

    def test_dates_and_cleaning(self):
        self.assertEqual(feeds.parse_date("2026-10-20T12:00:00Z"), dt.datetime(2026, 10, 20, 12, tzinfo=dt.timezone.utc))
        self.assertIsNone(feeds.parse_date("soon"))
        self.assertTrue(feeds.clean("word " * 100, limit=20).endswith("…"))


def run(args, home=None, cwd=ROOT, env=None, stdin=None):
    """Run a command with the context folder at `home`; returns CompletedProcess."""
    e = dict(os.environ, **(env or {}))
    if home:
        e["SWEATCAST_HOME"] = home
    return subprocess.run(args, cwd=cwd, env=e, capture_output=True, text=True, input=stdin, timeout=120)


def fresh_home(d):
    home = os.path.join(d, "me")
    shutil.copytree(paths.EXAMPLE, home)
    return home


class ExitCodes(unittest.TestCase):
    """A mistyped command exits 64, never 2, which means 'the workout ran long'."""

    def test_mistyped_options_exit_64(self):
        fixture = os.path.join("tests", "fixtures", "example.draft.txt")
        for args in (["tools/render.py", fixture, "--voice", "Chatterbox Coach", "--sed", "5", "--out", "x.mp3"],
                     ["tools/tts_build.py", fixture],                       # --out is missing
                     ["tools/coverage.py", "--bogus"],
                     ["tools/context.py", "get", "nothing"],
                     ["tools/voices.py", "measured", "Nobody At All"]):
            out = run([sys.executable, *args])
            self.assertEqual(out.returncode, cli.USAGE, (args, out.stdout, out.stderr))

    def test_voices_measured_codes(self):
        with tempfile.TemporaryDirectory() as d:
            out = run([sys.executable, "tools/voices.py", "measured", "Chatterbox Coach"], home=fresh_home(d))
            self.assertEqual(out.returncode, cli.ISSUES)   # estimated: nothing measured in a fresh copy


class BuildScript(unittest.TestCase):
    """tools/build.sh with a stand-in Python that fakes the lint and render."""

    STUB = """#!{python}
import os, sys
script = os.path.basename(sys.argv[1]) if len(sys.argv) > 1 else ""
args = sys.argv[2:]
if script in ("tts_build.py", "render.py"):
    with open(os.environ["STUB_LOG"], "a") as f:
        f.write(script + " " + " ".join(args) + "\\n")
    if "--out" in args:
        open(args[args.index("--out") + 1], "w").write("x")
    if script == "render.py":
        print("render failed for a test reason", file=sys.stderr)
        sys.exit(int(os.environ.get("STUB_RENDER_EXIT", "0")))
    sys.exit(0)
os.execv({python!r}, [{python!r}] + sys.argv[1:])
"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.home = fresh_home(d)
        self.phone = os.path.join(d, "phone")
        os.makedirs(self.phone)
        prof = os.path.join(self.home, "profile.md")
        with open(prof, encoding="utf-8") as f:
            text = f.read()
        text = re.sub(r"^deliver_to = .*$", f"deliver_to = {json.dumps(self.phone)}", text, flags=re.M)
        write_file(prof, text)
        self.stub = os.path.join(d, "python")
        write_file(self.stub, self.STUB.format(python=sys.executable))
        os.chmod(self.stub, 0o755)
        self.log = os.path.join(d, "calls.txt")

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, *extra, render_exit=0, estimated_ok=True):
        env = {"SWEATCAST_PYTHON": self.stub, "STUB_LOG": self.log, "STUB_RENDER_EXIT": str(render_exit)}
        flags = ["--allow-estimated"] if estimated_ok else []
        return run(["sh", "sweatcast", "build", os.path.join("tests", "fixtures", "example.draft.txt"), "Test build",
                    *flags, *extra], home=self.home, env=env)

    def calls(self):
        with open(self.log, encoding="utf-8") as f:
            return f.read()

    def test_success_copies_to_the_delivery_folder(self):
        out = self.build()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.phone, "Test build.mp3")))
        local = os.path.join(self.home, "workouts", "Test build.mp3")
        self.assertFalse(os.path.exists(local), "the local MP3 is removed once the copy is in place")
        self.assertTrue(os.path.exists(os.path.join(self.home, "workouts", "Test build.txt")))
        self.assertIn("--voice Chatterbox Coach", self.calls())   # the profile's default voice
        self.assertNotIn("--allow-estimated", self.calls())      # the build's own flags stay with it

    def test_a_failed_copy_keeps_the_local_mp3(self):
        os.chmod(self.phone, 0o500)   # the delivery folder can't be written
        try:
            out = self.build()
        finally:
            os.chmod(self.phone, 0o700)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("Couldn't copy", out.stdout)
        self.assertTrue(os.path.exists(os.path.join(self.home, "workouts", "Test build.mp3")))

    def test_drift_exits_2_without_a_copy_or_the_log(self):
        out = self.build(render_exit=2)
        self.assertEqual(out.returncode, 2)
        self.assertFalse(os.path.exists(os.path.join(self.phone, "Test build.mp3")))
        self.assertNotIn("test reason", out.stdout + out.stderr)

    def test_a_command_mistake_exits_64_and_shows_the_log(self):
        out = self.build(render_exit=64)
        self.assertEqual(out.returncode, 64)
        self.assertIn("render failed for a test reason", out.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.home, "workouts", ".logs", "Test build.log")))

    def test_unknown_voice_exits_64(self):
        out = self.build("--voice", "Nobody At All", estimated_ok=False)
        self.assertEqual(out.returncode, 64, out.stdout + out.stderr)
        self.assertNotIn("measured", out.stdout)

    def test_unmeasured_voice_exits_3(self):
        out = self.build(estimated_ok=False)
        self.assertEqual(out.returncode, 3, out.stdout + out.stderr)

    def test_lint_only_stops_before_the_render(self):
        out = self.build("--lint-only")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual([c.split()[0] for c in self.calls().splitlines()], ["tts_build.py"])

    def test_tolerance_reaches_the_lint_and_the_render(self):
        self.build("--tolerance", "0.05")
        lint, render_call = self.calls().splitlines()[:2]
        self.assertIn("--total-tolerance 0.05", lint)
        self.assertIn("--tolerance 0.05", render_call)

    def test_an_old_context_folder_stops_with_the_fix(self):
        prof = os.path.join(self.home, "profile.md")
        with open(prof, encoding="utf-8") as f:
            write_file(prof, context.body(f.read()))
        out = self.build()
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("./sweatcast migrate", out.stdout + out.stderr)


class PaceFile(unittest.TestCase):
    V1 = {"name": "One", "key": "k1", "engine": "chatterbox", "model": "m"}
    V2 = {"name": "Two", "key": "k2", "engine": "qwen3", "model": "m"}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "cache", "voice-pace.json")
        self.patch = mock.patch.object(voices, "PACE_FILE", self.path)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_two_voices_are_both_kept(self):
        voices.record_rate(self.V1, 600.0, 40.0)
        voices.record_rate(self.V2, 700.0, 50.0)
        voices.record_rate(self.V1, 600.0, 40.0)
        with open(self.path) as f:
            data = json.load(f)
        self.assertEqual(sorted(r["name"] for r in data.values()), ["One", "Two"])
        self.assertEqual(voices.pace(self.V1), (15.0, True))

    def test_a_damaged_file_is_set_aside_not_overwritten(self):
        voices.record_rate(self.V1, 600.0, 40.0)
        with open(self.path, "a") as f:
            f.write("\n{garbage")
        with open(self.path) as f:
            damaged = f.read()
        with self.assertRaises(SystemExit):
            voices.record_rate(self.V2, 700.0, 50.0)
        kept = glob.glob(self.path + ".corrupt-*")
        self.assertEqual(len(kept), 1)
        with open(kept[0]) as f:
            self.assertEqual(f.read(), damaged)
        self.assertFalse(os.path.exists(self.path))
        with self.assertRaises(SystemExit):
            write_file(self.path, "{nope")
            voices.check_pace_file()      # what render.py calls before loading a model

    def test_one_read_per_lint(self):
        segs = parse("@@ 20 | A\nOne line. [pause 2s] Two lines.\n\nThree.\n@@ 20 | B\nMinute two. Four.\n")
        voices.record_rate(self.V1, 600.0, 40.0)
        for v in (self.V1, self.V2):   # measured, and estimated from the others
            with mock.patch.object(voices, "_recorded", wraps=voices._recorded) as reads:
                tts_build.lint(segs, v)
            self.assertEqual(reads.call_count, 1, v["name"])


class LintReport(unittest.TestCase):
    def test_report_fields_without_printing(self):
        segs = parse("@@ 60 | A\nWarm up. Ten lbs.\n@@ 60 | B\nSquats now.\n")
        report = tts_build.lint(segs, wpm=60)
        self.assertEqual([r.flag for r in report.rows], ["short", "short"])
        self.assertTrue(any("abbreviation" in i for i in report.rows[0].line_issues))
        self.assertTrue(report.warnings)                        # B has no locator
        self.assertEqual(report.problems, 3)                     # two segments far off, one abbreviation
        strict = tts_build.lint(segs, wpm=60, strict=True)
        self.assertEqual(strict.problems, report.problems + len(report.warnings))

    def test_with_a_voice_the_total_is_held_to_plan(self):
        segs = parse("@@ 10 | A\n" + "word " * 40 + "\n")
        v = {"name": "x", "key": "x", "engine": "chatterbox", "model": "m"}
        with mock.patch("voices.pace", return_value=(10.0, True)):
            report = tts_build.lint(segs, v)
        self.assertGreater(report.drift, 0.03)
        self.assertTrue(report.total_off)
        self.assertEqual(report.rows[0].flag, "long")


class Hooks(unittest.TestCase):
    """The pre-push hook checks every pushed commit."""
    ZERO = "0" * 40

    def git(self, *args):
        out = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
                              "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                             cwd=self.repo, capture_output=True, text=True, check=True)
        return out.stdout.strip()

    def commit(self, msg, add=None, remove=None):
        if add:
            write_file(os.path.join(self.repo, add), "x\n")
            self.git("add", "-f", add)
        if remove:
            self.git("rm", "-q", "--cached", remove)
        self.git("commit", "-q", "--allow-empty", "-m", msg)
        return self.git("rev-parse", "HEAD")

    def push(self, local, remote):
        hook = os.path.join(ROOT, "tools", "hooks", "pre-push")
        return subprocess.run(["sh", hook, "origin", "url"], cwd=self.repo, capture_output=True, text=True,
                              input=f"refs/heads/main {local} refs/heads/main {remote}\n")

    def setUp(self):
        if not shutil.which("git"):
            self.skipTest("no git")
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        self.git("init", "-q")
        self.base = self.commit("base")

    def tearDown(self):
        self.tmp.cleanup()

    def test_added_then_removed_is_still_refused(self):
        self.commit("oops", add="me/health.md")
        head = self.commit("remove", remove="me/health.md")
        out = self.push(head, self.ZERO)
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn("me/health.md", out.stdout)

    def test_old_layout_health_file_is_refused(self):
        head = self.commit("old layout", add="knowledge/health.md")
        self.assertEqual(self.push(head, self.base).returncode, 1)

    def test_removing_an_already_pushed_file_is_allowed(self):
        added = self.commit("oops", add="me/log.md")
        self.git("update-ref", "refs/remotes/origin/main", added)
        head = self.commit("remove", remove="me/log.md")
        out = self.push(head, added)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_clean_pushes_pass(self):
        head = self.commit("engine change", add="tools/x.py")
        self.assertEqual(self.push(head, self.ZERO).returncode, 0)
        self.assertEqual(self.push(head, self.base).returncode, 0)


class Context(unittest.TestCase):
    SETTINGS = """# A comment that must survive edits.
words_per_minute = 170
deliver_to = "[a folder]"
youtube_favorites = ["chanA"]

[[voices]]
name = "Qwen3 Coach"
description = "crisp"

[[voices]]
name = "Chatterbox Coach"
description = "warm"

# Feeds come next.

[[feeds]]
label = "Weather"
kind = "weather"
value = "40.1, -75.2"

[[feeds]]
label = "Thing"
kind = "smoke"
value = "x\""""
    PROSE = "# Profile\n\n## Basics\n- Neighborhood: [neighborhood, city]\n- Goals right now: strength\n"
    LOG = with_schema("# Workout log\n\n## Sessions\n\n## Feedback\n- loved it\n")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.profile, self.log = os.path.join(d, "profile.md"), os.path.join(d, "log.md")
        write_file(self.profile, profile_text(self.SETTINGS, self.PROSE))
        write_file(self.log, self.LOG)

    def tearDown(self):
        self.tmp.cleanup()

    def test_profile_values(self):
        p = context.profile(self.profile)
        self.assertEqual(context.default_voice(p), "Qwen3 Coach")
        self.assertEqual([n for n, _ in context.voices(p)], ["Qwen3 Coach", "Chatterbox Coach"])
        self.assertEqual(context.wpm(p), 170)
        self.assertIsNone(context.delivery(p))                 # the template's hint isn't a folder
        self.assertEqual(context.handles(p, "YouTube favorites"), ["chanA"])
        self.assertEqual(context.feed_sources(p), [("Weather", "weather", "40.1, -75.2")])
        self.assertTrue(p.body.startswith("# Profile"))

    def test_delivery_folders_expand_stars(self):
        a, b = os.path.join(self.tmp.name, "GoogleDrive-a", "W"), os.path.join(self.tmp.name, "GoogleDrive-b", "W")
        os.makedirs(a)
        os.makedirs(b)
        p = context.Profile({"deliver_to": f"{self.tmp.name}/GoogleDrive-*/W"}, "")
        self.assertEqual(context.delivery_folders(p)[1], [a, b])
        self.assertEqual(context.delivery_folders(context.Profile({"deliver_to": f"{self.tmp.name}/no"}, ""))[1], [])

    def test_add_voice_keeps_comments_and_order(self):
        context.add_voice_to_profile("Coach Maya", "a woman in her thirties", default=True, path=self.profile)
        context.add_voice_to_profile("Coach Calm", "slow", path=self.profile)
        p = context.profile(self.profile)
        self.assertEqual([n for n, _ in context.voices(p)], ["Coach Maya", "Qwen3 Coach", "Chatterbox Coach", "Coach Calm"])
        with open(self.profile, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("# A comment that must survive edits.", text)
        self.assertLess(text.index('name = "Coach Calm"'), text.index("# Feeds come next."))
        self.assertEqual(len(context.feed_sources(p)), 1)
        context.add_voice_to_profile("coach maya", "again", path=self.profile)   # same name: replaced, moved last
        names = [n for n, _ in context.voices(context.profile(self.profile))]
        self.assertEqual(names, ["Qwen3 Coach", "Chatterbox Coach", "Coach Calm", "coach maya"])

    def test_log_session_round_trip(self):
        s = context.Session("2026-10-21", 25, "Home", "Chatterbox Coach", ["goblet squat", "seated row"],
                            "deep dive: news, a story", "rolling minutes",
                            {"goblet squat": "twenties, three down"})
        context.append_session(s, self.log)
        context.append_session(context.Session("2026-10-22", 15, "Travel", "Qwen3 Coach", ["push-up"], "x"), self.log)
        got = context.sessions(self.log)
        self.assertEqual([(g.date, g.minutes, g.movements, g.format, g.loads) for g in got],
                         [("2026-10-21", 25, ["goblet squat", "seated row"], "rolling minutes",
                           {"goblet squat": "twenties, three down"}),
                          ("2026-10-22", 15, ["push-up"], None, {})])
        with open(self.log, encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(context.schema_of(text), context.SCHEMA)
        self.assertIn("## Feedback\n- loved it", text)            # the rest of the file is untouched
        self.assertLess(text.index("2026-10-22"), text.index("## Feedback"))

    def test_bad_sessions_are_refused_on_write(self):
        for bad in (context.Session("21 Oct", 25, "Home", "V", ["squat"], "t"),
                    context.Session("2026-10-21", 25, "Home", "V", [], "t"),
                    context.Session("2026-10-21", 25, "Home | Gym", "V", ["squat"], "t")):
            with self.assertRaises(SystemExit):
                context.append_session(bad, self.log)

    def test_a_shifted_log_line_is_skipped_and_reported(self):
        write_file(self.log, with_schema("## Sessions\n- 2026-10-19 | 15 min | Home | squat, row | topics\n"
                                         "- 2026-10-20 | 20 min | Home | V | squat | topics | format: circuits\n"))
        with mock.patch("sys.stderr", new_callable=__import__("io").StringIO) as err:
            got = context.sessions(self.log)
        self.assertEqual([s.date for s in got], ["2026-10-20"])     # not read with its fields shifted
        self.assertIn("5 fields", err.getvalue())
        issues = context.check([self.profile, self.log])
        self.assertTrue(any(i.path == self.log and i.line == 5 for i in issues), issues)

    def test_check_flags_unfilled_lines_and_bad_feeds(self):
        issues = [i for i in context.check([self.profile, self.log]) if i.path == self.profile]
        problems = [i.message for i in issues if not i.note]
        notes = [i.message for i in issues if i.note]
        self.assertTrue(any("unknown kind 'smoke'" in m for m in problems), issues)
        hint = [i for i in issues if "'Neighborhood' isn't filled in" in i.message]
        self.assertEqual(len(hint), 1)
        with open(self.profile, encoding="utf-8") as f:
            self.assertIn("- Neighborhood:", f.read().splitlines()[hint[0].line - 1])   # the right line number
        self.assertTrue(any("deliver_to" in m for m in notes))
        self.assertFalse(any("Goals" in m for m in problems))

    def test_old_and_new_schemas_are_refused(self):
        write_file(self.profile, self.PROSE)
        with self.assertRaises(SystemExit) as e:
            context.profile(self.profile)
        self.assertIn("./sweatcast migrate", str(e.exception.code))
        write_file(self.profile, f"+++\nschema = {context.SCHEMA + 1}\n+++\n" + self.PROSE)
        with self.assertRaises(SystemExit) as e:
            context.profile(self.profile)
        self.assertIn("newer", str(e.exception.code))


class Migrate(unittest.TestCase):
    """1.x (schema 0) and 2.x (schema 1) folders migrate to the current schema in one run."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = fresh_home(self.tmp.name)
        with open(os.path.join(ROOT, "tests", "fixtures", "profile-schema1.md"), encoding="utf-8") as f:
            self.v1_profile = f.read()                      # me.example's profile as 2.0.0 shipped it
        self.bodies = {}
        for name in ("health.md", "log.md"):
            path = os.path.join(self.home, name)
            with open(path, encoding="utf-8") as f:
                self.bodies[name] = context.body(f.read())

    def tearDown(self):
        self.tmp.cleanup()

    def as_schema(self, n):
        write_file(os.path.join(self.home, "profile.md"),
                   context.with_front_matter(self.v1_profile, n) if n else context.body(self.v1_profile))
        for name, text in self.bodies.items():
            write_file(os.path.join(self.home, name), context.with_front_matter(text, n) if n else text)

    def migrated_profile(self):
        return context.profile(os.path.join(self.home, "profile.md"))

    def test_both_older_schemas_migrate(self):
        for start in (0, 1):
            self.as_schema(start)
            out = run([sys.executable, "tools/coverage.py"], home=self.home)
            self.assertIn("./sweatcast migrate", out.stderr)
            out = run([sys.executable, "tools/migrate.py"], home=self.home)
            self.assertIn("schema", out.stdout, out.stderr)
            p = self.migrated_profile()
            self.assertEqual(context.default_voice(p), "Chatterbox Coach")
            self.assertEqual([n for n, _ in context.voices(p)], ["Chatterbox Coach", "Qwen3 Coach"])
            self.assertEqual(context.wpm(p), 165)
            self.assertEqual(context.handles(p, "YouTube favorites"),
                             ["Asianometry", "BranchEducation", "PracticalEngineeringChannel"])
            self.assertEqual(len(context.feed_sources(p)), 6)
            self.assertIsNone(context.delivery(p))
            for gone in ("- Voices", "- Copy finished MP3s", "## Feeds", "- Measured words", "@Asianometry"):
                self.assertNotIn(gone, p.body)
            self.assertEqual(p.body.count(context.SETTINGS_NOTE), 1)
            self.assertIn("## Equipment kits", p.body)                 # the rest of the prose stays
            for name, text in self.bodies.items():
                with open(os.path.join(self.home, name), encoding="utf-8") as f:
                    self.assertEqual(context.body(f.read()), text)
            self.assertEqual(run([sys.executable, "tools/coverage.py"], home=self.home).returncode, 0)

    def test_backup_dry_run_and_idempotence(self):
        self.as_schema(1)
        profile = os.path.join(self.home, "profile.md")
        out = run([sys.executable, "tools/migrate.py", "--dry-run"], home=self.home)
        self.assertIn("Dry run", out.stdout)
        with open(profile, encoding="utf-8") as f:
            self.assertEqual(f.read(), context.with_front_matter(self.v1_profile, 1))
        run([sys.executable, "tools/migrate.py"], home=self.home)
        backups = glob.glob(os.path.join(self.home, ".backup-*"))
        self.assertEqual(len(backups), 1)
        with open(os.path.join(backups[0], "profile.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), context.with_front_matter(self.v1_profile, 1))
        with open(profile, encoding="utf-8") as f:
            once = f.read()
        out = run([sys.executable, "tools/migrate.py"], home=self.home)
        self.assertIn("already at schema", out.stdout)
        with open(profile, encoding="utf-8") as f:
            self.assertEqual(f.read(), once)
        self.assertEqual(len(glob.glob(os.path.join(self.home, ".backup-*"))), 1)

    def test_the_template_is_current_and_says_what_to_fill_in(self):
        out = run([sys.executable, "tools/context.py", "check"], home=fresh_home(self.tmp.name + "/t"))
        self.assertEqual(out.returncode, cli.ISSUES, out.stdout)
        self.assertNotIn("schema", out.stdout)
        self.assertIn("'Neighborhood' isn't filled in yet", out.stdout)
        self.assertIn("feed '[Team]' isn't filled in yet", out.stdout)


class Context3(unittest.TestCase):
    """Schema 3: experience, likes, dislikes, kits, and the health file's limits."""

    SETTINGS = """experience = "experienced"
likes = ["goblet-squat"]
dislikes = ["box-squat"]

[[kits]]
name = "garage"
equipment = ["dumbbells", "mat"]

[[voices]]
name = "Qwen3 Coach"
description = "crisp"
"""
    HEALTH = """# Health

## Active injuries and limitations
- Right wrist: invented strain.

## Clinician rules
- No jumping until cleared.
[what your clinician told you]
<!-- a note for the listener -->

## Other
- not a rule
"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def health_file(self, settings, prose=None):
        path = os.path.join(self.dir, "health.md")
        write_file(path, f"+++\nschema = {context.SCHEMA}\n{settings}\n+++\n{prose or self.HEALTH}")
        return path

    ROW = """[[limits]]
area = "wrist"
side = "right"
level = "delicate"
rehab = ["calf-raise"]
note = "Therapist: no weight through the hand."
"""

    def test_profile_settings(self):
        write_file(os.path.join(self.dir, "profile.md"), profile_text(self.SETTINGS))
        p = context.profile(os.path.join(self.dir, "profile.md"))
        self.assertEqual(context.SCHEMA, 3)
        self.assertEqual(context.experience(p), "experienced")
        self.assertEqual(context.likes(p), ["goblet-squat"])
        self.assertEqual(context.dislikes(p), ["box-squat"])
        self.assertEqual(context.kits(p), {"garage": ["dumbbells", "mat"]})
        for settings in ('experience = ""', 'experience = "expert"', ""):
            bare = context.Profile(context.front(profile_text(settings))[0], "")
            self.assertIsNone(context.experience(bare))
            self.assertEqual((context.likes(bare), context.dislikes(bare), context.kits(bare)), ([], [], {}))

    def test_health_limits_and_clinician_lines(self):
        h = context.health(self.health_file(self.ROW))
        self.assertEqual(context.limits(h), [catalog.Limit("wrist", "right", "delicate", [], ["calf-raise"],
                                                           "Therapist: no weight through the hand.")])
        self.assertEqual(context.clinician_lines(h), ["wrist delicate right: Therapist: no weight through the hand.",
                                                      "No jumping until cleared."])
        bare = context.health(self.health_file('[[limits]]\narea = "knee"\nlevel = "off-limits"\n'))
        self.assertEqual(context.clinician_lines(bare), ["knee off-limits", "No jumping until cleared."])
        self.assertEqual(context.limits(context.health(self.health_file(""))), [])

    def test_bad_limit_row_is_reported(self):
        bad = ('[[limits]]\narea = "elbowish"\nlevel = "delicate"\n\n[[limits]]\narea = "knee"\n'
               'side = "up"\nlevel = "off-limits"\n\n[[limits]]\narea = "knee"\nlevel = "sore"\n\n'
               '[[limits]]\narea = "knee"\nlevel = "off-limits"\n')
        path = self.health_file(bad)
        got = context.limits(context.health(path))
        self.assertEqual([(l.area, l.side, l.level) for l in got], [("knee", "both", "off-limits")])
        msgs = [i.message for i in context.check([path]) if not i.note]
        self.assertEqual(len(msgs), 3, msgs)
        self.assertTrue(any("elbowish" in m and "knee" in m for m in msgs))     # names the valid areas
        self.assertTrue(any("left, right or both" in m for m in msgs))
        self.assertTrue(any("off-limits or delicate" in m for m in msgs))

    def test_malformed_flags_or_rehab_drop_the_row(self):
        for bad in ('flags = "floor"', 'rehab = "towel-scrunch"', 'flags = ["wobbly"]', 'rehab = [3]'):
            with self.subTest(bad=bad):
                path = self.health_file(f'[[limits]]\narea = "knee"\nlevel = "off-limits"\n{bad}\n')
                self.assertEqual(context.limits(context.health(path)), [])
                msgs = [i.message for i in context.check([path]) if not i.note]
                self.assertTrue(any("[[limits]] row 1" in m and "ignored" in m for m in msgs), msgs)
        good = self.health_file('[[limits]]\narea = "knee"\nlevel = "off-limits"\nflags = ["floor"]\n')
        self.assertEqual(context.limits(context.health(good))[0].flags, ["floor"])

    def test_non_rehab_id_in_rehab_is_an_issue(self):
        issues = context.check([self.health_file(self.ROW.replace('"calf-raise"', '"goblet-squat"'))])
        self.assertTrue(any(not i.note and "goblet-squat" in i.message for i in issues), issues)
        issues = context.check([self.health_file(self.ROW.replace('"calf-raise"', '"towel-scrunch"'))])
        self.assertFalse(any(not i.note and "towel-scrunch" in i.message for i in issues), issues)   # a rehab entry

    def test_unlisted_injuries_need_no_limits_row(self):
        for line in ("- Unlisted: invented jaw soreness.", "- unlisted: invented jaw soreness."):
            prose = self.HEALTH.replace("- Right wrist: invented strain.", line)
            path = self.health_file("", prose)
            self.assertFalse(context.prose_injuries(context.health(path)), line)
            self.assertFalse(any("have no [[limits]]" in i.message for i in context.check([path])))
        both = self.HEALTH.replace("- Right wrist: invented strain.", "- Unlisted: invented jaw.\n- Left knee: invented.")
        self.assertTrue(context.prose_injuries(context.health(self.health_file("", both))))

    def test_rehab_ids_are_checked_as_notes(self):
        row = self.ROW.replace('"calf-raise"', '"no-such-move"')
        issues = context.check([self.health_file(row)])
        self.assertTrue(any(i.note and "no-such-move" in i.message for i in issues))
        self.assertFalse(any(not i.note for i in issues))

    def test_prose_injuries_without_limits_is_an_issue(self):
        path = self.health_file("")
        h = context.health(path)
        self.assertTrue(context.prose_injuries(h))
        found = [i for i in context.check([path]) if "no rule" in i.message or "[[limits]]" in i.message]
        self.assertEqual(len(found), 1)
        self.assertFalse(found[0].note)
        self.assertIn("injuries written in prose have no [[limits]] entry", found[0].message)
        with_row = context.health(self.health_file(self.ROW))
        self.assertTrue(context.prose_injuries(with_row))
        self.assertFalse(any("have no [[limits]]" in i.message for i in context.check([with_row.path])))
        none = self.HEALTH.replace("- Right wrist: invented strain.", "- None right now.")
        self.assertFalse(context.prose_injuries(context.health(self.health_file("", none))))
        commented = self.HEALTH.replace("- Right wrist: invented strain.",
                                        "- None right now.\n<!-- e.g.\n- Right wrist: strain\n-->")
        self.assertFalse(context.prose_injuries(context.health(self.health_file("", commented))))

    def test_profile_check_notes(self):
        write_file(os.path.join(self.dir, "profile.md"), profile_text(
            'experience = ""\nlikes = ["no-such-move"]\ndislikes = ["box-squat"]\n\n[[kits]]\nname = "x"\n'
            'equipment = ["dumbbells", "jetpack"]\n\n[[voices]]\nname = "V"\ndescription = "d"\n'))
        msgs = [i.message for i in context.check([os.path.join(self.dir, "profile.md")]) if i.note]
        self.assertTrue(any("no experience level: novice, experienced or advanced" in m for m in msgs))
        self.assertTrue(any("no-such-move" in m for m in msgs))
        self.assertFalse(any("box-squat" in m for m in msgs))
        self.assertTrue(any("jetpack" in m for m in msgs))
        self.assertFalse(any("dumbbells" in m for m in msgs))

    def test_get_experience(self):
        with tempfile.TemporaryDirectory() as d:
            home = fresh_home(d)
            out = run([sys.executable, "tools/context.py", "get", "experience"], home=home)
            self.assertEqual((out.returncode, out.stdout), (0, ""), out.stderr)
            path = os.path.join(home, "profile.md")
            with open(path, encoding="utf-8") as f:
                text = f.read()
            write_file(path, text.replace('experience = ""', 'experience = "advanced"'))
            out = run([sys.executable, "tools/context.py", "get", "experience"], home=home)
            self.assertEqual(out.stdout, "advanced\n")


class Migrate3(unittest.TestCase):
    """Schema 2 to 3, on the schema-2 shape of the example files."""

    PROFILE2 = ('+++\nschema = 2\n# rate\nwords_per_minute = 165\ndeliver_to = ""\n\n[[voices]]\n'
                'name = "V"\ndescription = "d"\n+++\n# My Profile\n')
    HEALTH2 = ("+++\nschema = 2\n+++\n# Health\n\n## Active injuries and limitations\n"
               "- Right wrist: invented strain.\n")

    def test_migrate_2_to_3_adds_the_keys(self):
        p = migrate.to_3(self.PROFILE2, "profile.md")
        settings, rest = context.front(p)
        self.assertEqual((settings["schema"], settings["experience"], settings["likes"], settings["dislikes"]),
                         (3, "", [], []))
        self.assertNotIn("kits", settings)
        self.assertLess(p.index("words_per_minute"), p.index("experience"))
        self.assertLess(p.index("experience"), p.index("deliver_to"))
        self.assertIn(f"# {context.SETTINGS_COMMENTS['experience']}", p)
        self.assertEqual(settings["voices"], [{"name": "V", "description": "d"}])
        self.assertEqual(rest, "# My Profile\n")
        h = migrate.to_3(self.HEALTH2, "health.md")
        settings, rest = context.front(h)
        self.assertEqual(settings, {"schema": 3})
        self.assertIn("[[limits]]", h.split("+++")[1])                  # the comment line names it
        note = " ".join(h.split("+++")[1].split())
        self.assertIn("delete the old comment", note.lower())   # the 3.x template's comment named removed files
        self.assertIn("injury-rules.toml", note)
        self.assertIn("phase", note)
        self.assertIn("assumes novice", context.SETTINGS_COMMENTS["experience"])
        self.assertEqual(rest, context.body(self.HEALTH2))
        log = migrate.to_3("+++\nschema = 2\n+++\n# Log\n", "log.md")
        self.assertEqual(log, "+++\nschema = 3\n+++\n# Log\n")

    def test_limits_row_after_migration_parses(self):
        h = migrate.to_3(self.HEALTH2, "health.md")
        h = h.replace("\n+++\n# Health", ('\n[[limits]]\narea = "wrist"\nside = "right"\n'
                                          'level = "off-limits"\n+++\n# Health'), 1)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "health.md")
            write_file(path, h)
            got = context.limits(context.health(path))
        self.assertEqual(got, [catalog.Limit("wrist", "right", "off-limits", [], [], "")])

    def test_migrate_runs_through_the_command(self):
        with tempfile.TemporaryDirectory() as d:
            home = fresh_home(d)
            for name, text in (("profile.md", self.PROFILE2), ("health.md", self.HEALTH2)):
                write_file(os.path.join(home, name), text)
            for name in ("log.md",):
                path = os.path.join(home, name)
                with open(path, encoding="utf-8") as f:
                    write_file(path, context.with_front_matter(context.body(f.read()), 2))
            out = run([sys.executable, "tools/migrate.py"], home=home)
            self.assertIn("schema 2 to 3", out.stdout, out.stderr)
            # the migrated prose injury has no [[limits]] row yet: the one issue left to fix
            issues = [i for i in context.check([os.path.join(home, "health.md")]) if not i.note]
            self.assertEqual(len(issues), 1)
            self.assertIn("injuries written in prose have no [[limits]] entry", issues[0].message)

    def test_example_is_schema_3(self):
        issues = context.check([os.path.join(paths.EXAMPLE, n) for n in
                                ("profile.md", "health.md", "log.md")])
        self.assertFalse([i for i in issues if "schema" in i.message])
        hard = [i for i in issues if not i.note]
        self.assertTrue(all(os.path.basename(i.path) == "profile.md" and "isn't filled in yet" in i.message
                            for i in hard), hard)
        h = context.health(os.path.join(paths.EXAMPLE, "health.md"))
        self.assertEqual((context.limits(h), context.clinician_lines(h)), ([], []))
        p = context.profile(os.path.join(paths.EXAMPLE, "profile.md"))
        self.assertEqual(context.kits(p), {"home": ["dumbbells", "band", "mat"]})
        self.assertEqual(context.SCHEMA, 3)


class VoiceDesign(unittest.TestCase):
    """design and keep, with the model replaced by a stand-in."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = fresh_home(self.tmp.name)
        self.takes = os.path.join(self.home, "voices", ".takes")
        self.voices = os.path.join(self.home, "voices")

    def tearDown(self):
        self.tmp.cleanup()

    def test_design_then_keep(self):
        calls = []

        def fake(desc, line, n, seed):
            calls.append((desc, line, n, seed))
            return [b"\x01\x00" * 24000 * (i + 1) for i in range(n)]
        takes = voices.design("Coach Maya", "A woman in her thirties", takes=2, folder=self.takes, make_takes=fake)
        self.assertEqual([os.path.basename(t) for t in takes], ["Coach Maya-1.wav", "Coach Maya-2.wav"])
        self.assertEqual(calls[0][2:], (2, 7))
        import wave as wv
        with wv.open(takes[1]) as w:
            self.assertEqual((w.getframerate(), w.getnframes()), (24000, 48000))

        profile = os.path.join(self.home, "profile.md")
        with mock.patch.object(voices, "VOICE_DIRS", (self.voices, os.path.join(ROOT, "voices"))):
            name = voices.keep(takes[1], "chatterbox", default=True, folder=self.voices, profile_path=profile)
            self.assertEqual(name, "Coach Maya")
            v = voices.lookup("coach maya")
            self.assertEqual((v["engine"], v["model"]), ("chatterbox", "mlx-community/chatterbox-turbo-fp16"))
            self.assertRegex(v["revision"], r"^[0-9a-f]{40}$")
            self.assertEqual(v["ref_text"], voices.DESIGN_LINE)
            with self.assertRaises(SystemExit):                       # no silent overwrite
                voices.keep(takes[0], "qwen3", folder=self.voices, profile_path=profile)
        p = context.profile(profile)
        self.assertEqual(context.default_voice(p), "Coach Maya")
        self.assertEqual(dict(context.voices(p))["Coach Maya"], "A woman in her thirties")

    def test_keep_needs_the_words(self):
        clip = os.path.join(self.tmp.name, "mine.wav")
        voices.write_wav(clip, b"\x00\x00" * 100)
        with self.assertRaises(SystemExit):
            voices.keep(clip, "qwen3", folder=self.voices, profile_path=os.path.join(self.home, "profile.md"))


class Wrapper(unittest.TestCase):
    """./sweatcast, the one command."""

    def sweatcast(self, *args, home=None):
        return run(["sh", "sweatcast", *args], home=home, env={"SWEATCAST_PYTHON": sys.executable})

    def test_help_and_unknown_commands(self):
        out = self.sweatcast("help")
        self.assertEqual(out.returncode, 0)
        for cmd in ("build", "voices", "check", "log-session", "migrate"):
            self.assertIn(cmd, out.stdout)
        self.assertEqual(self.sweatcast("nonsense").returncode, cli.USAGE)

    def test_subcommands_reach_their_tools(self):
        with tempfile.TemporaryDirectory() as d:
            home = fresh_home(d)
            self.assertEqual(self.sweatcast("get", "default-voice", home=home).stdout.strip(), "Chatterbox Coach")
            out = self.sweatcast("voices", "measured", "Nobody", home=home)
            self.assertEqual(out.returncode, cli.USAGE)
            out = self.sweatcast("lint", "--bogus", home=home)
            self.assertEqual(out.returncode, cli.USAGE)
            self.assertIn("sweatcast lint", out.stderr)                # usage names the command
            out = self.sweatcast("log-session", "--minutes", "10", "--kit", "Home", "--voice", "V",
                                 "--movements", "squat", "--topics", "t", home=home)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(len(context.sessions(os.path.join(home, "log.md"))), 1)

    def test_without_an_environment_it_says_run_setup(self):
        out = run(["sh", "sweatcast", "check"], env={"SWEATCAST_PYTHON": "/nonexistent/python"})
        self.assertEqual(out.returncode, 1)
        self.assertIn("./sweatcast setup", out.stderr)


class CachePrune(unittest.TestCase):
    def test_prunes_only_clips_unused_for_the_window(self):
        with tempfile.TemporaryDirectory() as d:
            old, new, pace = (os.path.join(d, n) for n in ("old.pcm", "new.pcm", "voice-pace.json"))
            for p in (old, new, pace):
                write_file(p, "abcd")
            month = time.time() - 60 * 86400
            os.utime(old, (month, month))
            os.utime(pace, (month, month))
            self.assertEqual(cache.prune(45, d), (1, 4))
            self.assertEqual(sorted(os.listdir(d)), ["new.pcm", "voice-pace.json"])
            self.assertEqual(cache.size(d), (1, 4))


class Engines(unittest.TestCase):
    def test_tested_mlx_audio_matches_the_lock(self):
        with open(os.path.join(ROOT, "uv.lock"), encoding="utf-8") as f:
            lock = f.read()
        m = re.search(r'name = "mlx-audio"\nversion = "([^"]+)"', lock)
        self.assertEqual(m.group(1), engines.TESTED_MLX_AUDIO)

    def test_loudness_stats(self):
        stderr = ('[Parsed_loudnorm_0 @ 0x1] \n{\n\t"input_i" : "-27.61",\n\t"input_tp" : "-4.47",\n'
                  '\t"input_lra" : "18.06",\n\t"input_thresh" : "-39.20",\n\t"output_i" : "-16.58",\n'
                  '\t"target_offset" : "0.58"\n}\n')
        self.assertEqual(render.loudness_stats(stderr)["input_i"], "-27.61")
        with self.assertRaises(SystemExit) as e:
            render.loudness_stats("Error opening input")
        self.assertIn("Error opening input", str(e.exception.code))


class RenderLock(unittest.TestCase):
    def test_a_second_render_waits_for_the_first(self):
        with tempfile.TemporaryDirectory() as d:
            ready = os.path.join(d, "ready")
            holder = subprocess.Popen([sys.executable, "-c", (
                "import sys, time; sys.path.insert(0, 'tools'); import render\n"
                f"with render.render_lock({d!r}):\n"
                f"    open({ready!r}, 'w').close(); time.sleep(1.0)\n")], cwd=ROOT)
            try:
                deadline = time.time() + 20
                while not os.path.exists(ready) and time.time() < deadline:
                    time.sleep(0.02)
                started = time.time()
                with mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out:
                    with render.render_lock(d):
                        waited = time.time() - started
                self.assertGreater(waited, 0.5)
                self.assertIn("waiting", out.getvalue())
            finally:
                holder.wait(timeout=20)


class BuildRecord(unittest.TestCase):
    def test_record_written_beside_the_mp3_and_to_the_log(self):
        with tempfile.TemporaryDirectory() as d:
            draft_path = os.path.join(d, "x.draft.txt")
            write_file(draft_path, "@@ 10 | A\nGo.\n")
            out = os.path.join(d, "Workout.mp3")
            v = {"name": "V", "key": "k", "engine": "qwen3", "model": "m", "revision": "r"}
            rec = render.build_record(draft_path, out, v, 42, 3, 1, 600, 606, 0.01, 12.3, time.time())
            log = os.path.join(d, ".logs", "builds.jsonl")
            render.save_build_record(rec, out, log)
            with open(os.path.join(d, "Workout.build.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["draft_sha256"], rec["draft_sha256"])
            with open(log, encoding="utf-8") as f:
                self.assertEqual(json.loads(f.readline())["seed"], 42)


class FeedLimits(unittest.TestCase):
    def test_only_web_addresses(self):
        for url in ("file:///etc/hosts", "ftp://example.org/x", "/etc/hosts"):
            with self.assertRaises(ValueError):
                feeds.fetch(url)

    def test_oversized_responses_are_skipped(self):
        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, n=-1):
                return b"x" * (n if n > 0 else 10)
        with mock.patch("urllib.request.urlopen", return_value=Resp()):
            with self.assertRaises(ValueError):
                feeds.fetch("https://example.org/feed", limit=100)
            self.assertEqual(len(Resp().read(50)), 50)


if __name__ == "__main__":
    unittest.main()
