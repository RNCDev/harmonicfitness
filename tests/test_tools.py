"""Fast checks for the text, timing, log and feed logic. No models, no audio rendering,
no network.

    python3 -m unittest discover tests
"""
import datetime as dt
import glob
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import char_weight  # noqa: E402
import coverage  # noqa: E402
import feeds  # noqa: E402
import render  # noqa: E402
import tts_build  # noqa: E402
import voices  # noqa: E402
import youtube  # noqa: E402
from render import SR, assemble, chime, end_tone, silence  # noqa: E402
from tts_build import (CHIME, CHIME_SECONDS, PARAGRAPH_GAP, lint_line, parse, plan, spans,  # noqa: E402
                       structure_warnings, word_count)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFTS = sorted(glob.glob(os.path.join(ROOT, "workouts", "drafts", "*.draft.txt")))
OMNIVOICE_DURATION = os.path.expanduser(
    "~/Library/Application Support/VoiceStudio/runtime/project/omnivoice/utils/duration.py")


def secs(pcm):
    return len(pcm) / 2 / SR


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
                         [("Set up.", 3.0), ("Go.", 0.5), ("Now", tts_build.PAUSE_DEFAULT), ("end", 0.0)])

    def test_pause_is_capped(self):
        self.assertEqual(spans("Rest. [pause 30s]"), [("Rest.", tts_build.PAUSE_MAX)])

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
        self.assertFalse(tts_build.spoken(CHIME))
        self.assertFalse(tts_build.spoken(""))
        self.assertTrue(tts_build.spoken("Go."))
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
        a = 5 + PARAGRAPH_GAP + render.MAX_EXTRA_GAP + render.END_TAIL
        b = 1 + render.END_TAIL
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
        gap = render.MAX_EXTRA_GAP + PARAGRAPH_GAP
        # The second word starts after one second of speech plus the widened break.
        self.assertEqual(pcm[int((1 + gap) * SR) * 2 - 2:int((1 + gap) * SR) * 2], b"\x00\x00")
        self.assertEqual(pcm[int((1 + gap) * SR) * 2 + 2:int((1 + gap) * SR) * 2 + 4], b"\x01\x00")

    def test_long_segment_is_flagged_and_the_next_pays_it_back(self):
        segs = self.segs("@@ 3 | A\none two three four five\n@@ 10 | B\nsix\n")
        pcm, rows, _ = assemble(segs, self.fake_clip)
        self.assertEqual(rows[0][4], "  <-- long")
        # A runs two seconds late, so B keeps only what's left of its spare time.
        self.assertAlmostEqual(secs(pcm), 5 + 1 + render.END_TAIL, places=3)

    def test_small_overrun_is_not_flagged(self):
        segs = self.segs("@@ 20 | A\n" + " ".join(["w"] * 21) + "\n")
        _, rows, drift = assemble(segs, self.fake_clip)
        self.assertEqual(rows[0][4], "")
        self.assertAlmostEqual(drift, 0.05, places=3)

    def test_layout_matches_assemble(self):
        segs = self.segs("@@ 20 | A\none two\n\nthree\n@@ 4 | B\nfour five six\n\nseven\n@@ 30 | C\neight\n")
        pcm, _, _ = assemble(segs, self.fake_clip)
        predicted = tts_build.layout([(3 + PARAGRAPH_GAP, 1, 20), (4 + PARAGRAPH_GAP, 1, 4), (1, 0, 30)])
        self.assertAlmostEqual(secs(pcm), sum(length for _, length in predicted), places=3)

    def test_chime_opens_every_segment_but_the_first(self):
        segs = self.segs("@@ 5 | A\none\n@@ 5 | B\ntwo\n")
        lead = chime()
        self.assertAlmostEqual(secs(lead), CHIME_SECONDS, places=3)
        pcm, rows, _ = assemble(segs, self.fake_clip, lead=lead)
        self.assertEqual(bytes(pcm[:4]), b"\x01\x00\x01\x00")          # A starts with the voice
        b_start = int((1 + render.END_TAIL) * SR) * 2                    # A ends early, after its tail
        self.assertEqual(bytes(pcm[b_start:b_start + len(lead)]), lead)   # B starts with the bell
        self.assertAlmostEqual(rows[1][2], 1 + CHIME_SECONDS, places=3)
        self.assertAlmostEqual(secs(pcm), 2 * (1 + render.END_TAIL) + CHIME_SECONDS, places=3)

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
        self.assertAlmostEqual(secs(pcm), 2 + CHIME_SECONDS + render.END_TAIL, places=3)

    def test_end_tone_follows_the_last_segment(self):
        segs = self.segs("@@ 5 | A\none\n")
        tail = end_tone()
        pcm, _, _ = assemble(segs, self.fake_clip, tail=tail)
        self.assertAlmostEqual(secs(pcm), 1 + render.END_TAIL + secs(tail), places=3)
        self.assertEqual(bytes(pcm[-len(tail):]), tail)
        self.assertGreater(secs(tail), secs(chime()))   # longer and rising, so it can't pass for a bell


class Coverage(unittest.TestCase):
    LOG = """# Workout log

## Sessions
- 2026-10-19 | 15 min | Home | V | seated bent-over rowing, dead bug on the bench, straight-leg raise | topics
- 2026-10-20 | 20 min | Home | V | incline push-up, seated curl, right single-leg glute bridge, clamshell, side plank from the knee, seated punching finisher, mystery move | topics

## Feedback
- 2026-10-20 | not | a | session | line
"""

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".md")
        with os.fdopen(fd, "w") as f:
            f.write(self.LOG)

    def tearDown(self):
        os.remove(self.path)

    def test_reads_only_the_sessions_section(self):
        log = coverage.sessions(self.path)
        self.assertEqual([d for d, _ in log], ["2026-10-19", "2026-10-20"])

    def test_groups_and_gaps(self):
        hit, unmapped = coverage.coverage(coverage.sessions(self.path)[-1][1])
        self.assertEqual(hit["arms"], ["seated curl"])
        self.assertEqual(hit["hamstrings"], ["right single-leg glute bridge"])
        self.assertEqual(hit["lateral or anti-rotation core"], ["side plank from the knee"])
        self.assertEqual(hit["anti-extension core"], [])      # a side plank isn't anti-extension
        self.assertEqual(hit["quads"], [])
        self.assertEqual(unmapped, ["mystery move"])         # the finisher is skipped on purpose

    def test_tricky_names(self):
        self.assertEqual(coverage.groups_of("lying leg curl"), ["hamstrings"])
        self.assertEqual(coverage.groups_of("seated bent-over rowing"), ["horizontal pull"])
        self.assertNotIn("horizontal push", coverage.groups_of("overhead press"))


class CharWeight(unittest.TestCase):
    def test_basic_weights(self):
        self.assertAlmostEqual(char_weight.weight("ab c."), 1 + 1 + 0.2 + 1 + 0.5)
        self.assertAlmostEqual(char_weight.weight("7"), 3.5)
        self.assertAlmostEqual(char_weight.weight("é"), 1.0)
        self.assertAlmostEqual(char_weight.weight("e\u0301"), 1.0)   # NFC composes the accent

    @unittest.skipUnless(os.path.exists(OMNIVOICE_DURATION), "VoiceStudio's OmniVoice isn't installed")
    def test_matches_omnivoice_on_every_draft(self):
        # voice-pace.json was accumulated with OmniVoice's table; any drift shifts every prediction.
        spec = importlib.util.spec_from_file_location("_ov_duration", OMNIVOICE_DURATION)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        est = mod.RuleDurationEstimator()
        for path in DRAFTS:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertEqual(char_weight.weight(text), est.calculate_total_weight(text), path)


class SeedPace(unittest.TestCase):
    def test_median_of_measured_voices_only(self):
        data = {"a|chatterbox|m": {"weight": 1460.0, "seconds": 100.0},
                "b|qwen3|m": {"weight": 1200.0, "seconds": 100.0},
                "c|qwen3|m": {"weight": 1600.0, "seconds": 100.0},
                "short|qwen3|m": {"weight": 10.0, "seconds": 5.0},       # too little speech to count
                "omni": {"name": "x", "ref_text": "hi", "ref_tokens": 250}}  # OmniVoice entry, no rate
        self.assertAlmostEqual(voices.seed_pace(data), 14.6)

    def test_default_when_nothing_is_measured(self):
        self.assertEqual(voices.seed_pace({}), voices.DEFAULT_PACE)


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
            f.write(self.LOG)

    def tearDown(self):
        os.remove(self.path)

    def test_format_and_loads(self):
        e = coverage.entries(self.path)
        self.assertIsNone(e[0]["format"])
        self.assertEqual(e[0]["loads"], {})
        self.assertEqual(e[1]["format"], "circuits")
        self.assertEqual(e[1]["loads"], {"seated curl": "fifteens, three down", "squat": "bodyweight"})
        self.assertEqual(coverage.sessions(self.path)[1], ("2026-10-20", ["seated curl", "squat"]))

    def test_newest_load_wins(self):
        loads = coverage.last_loads(coverage.entries(self.path))
        self.assertEqual(loads["seated curl"], ("2026-10-21", "twenties"))
        self.assertEqual(loads["squat"], ("2026-10-20", "bodyweight"))


class YouTube(unittest.TestCase):
    def test_puzzles_line_and_fresh_filter(self):
        with tempfile.TemporaryDirectory() as d:
            prof = os.path.join(d, "profile.md")
            with open(prof, "w") as f:
                f.write("- YouTube favorites (x): A @chanA, B @chanB.\n"
                        "- Puzzles (quiz): Presh's MindYourDecisions @MindYourDecisions.\n")
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
        text = ("## Content\n- (rss): ignored outside the section\n## Feeds\nIntro line.\n"
                "- Weather, home (weather): 39.9, -75.1\n- Devils (espn): hockey/nhl/nj\n"
                "- Local (rss): https://example.org/feed/\n- Bad (ftp): x\n## Narrator\n- Tone: calm\n")
        self.assertEqual(feeds.config(text), [("Weather, home", "weather", "39.9, -75.1"),
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


if __name__ == "__main__":
    unittest.main()
