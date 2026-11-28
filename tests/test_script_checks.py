"""Checks the engine holds on a written script: "heavy" under a limit, the opening's side and AI line, the menu
check's reading of ordinary speech, a set's [reps N] timing, and a time said in words."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import build  # noqa: E402
import catalog  # noqa: E402
import draft  # noqa: E402
import menu  # noqa: E402
import tts_build  # noqa: E402

CAT = catalog.load()
KNEE = {"request": {"limits": ["knee=delicate:left"]}}
PRESS = {"single-arm-floor-press": {"id": "single-arm-floor-press", "side": "left"}}   # the healthy side's press


def segs(text):
    return draft.parse("movements: farmer carry\n" + text)


class HeavyUnderALimit(unittest.TestCase):
    def test_heavy_beside_a_movement_that_loads_a_limited_area_is_found(self):
        found = menu.load_problems(CAT, KNEE, segs("@@ 60 | Carry\nPick up a heavy pair for the farmer carry, and walk.\n"))
        self.assertEqual(len(found), 1)
        self.assertIn('"heavy" with farmer carry, which loads today\'s limited knee', found[0])
        self.assertTrue(menu.load_problems(CAT, KNEE, segs("@@ 60 | Carries\nTwo heavy suitcase carries now.\n")))
        two = segs("@@ 45 | Rest\nPick up one heavy dumbbell in your right hand.\n\n"
                   "@@ 60 | Set one\nSuitcase carry, walk tall, short steps.\n")   # set up in the rest before
        found = menu.load_problems(CAT, KNEE, two)
        self.assertEqual(len(found), 1)
        self.assertIn('segment "Rest"', found[0])
        after = segs("@@ 60 | Set one\nSuitcase carry, walk tall.\n\n@@ 60 | Carry set 2\nHold that heavy bell steady.\n")
        self.assertIn('segment "Carry set 2"', menu.load_problems(CAT, KNEE, after)[0])
        for text, mid in (("farmer carries", "farmer-carry"), ("suitcase carries", "suitcase-carry"),
                          ("push-ups", "push-up"), ("goblet squats", "goblet-squat")):
            self.assertEqual([m for m, _, _ in menu.mentions(CAT, text)], [mid], text)
        text = "@@ 60 | Press\nA heavy bell for the half-kneeling kettlebell press.\n"
        both = {"request": {"limits": ["shoulder=delicate:both"]},
                "movements": [{"id": "half-kneeling-kettlebell-press"}]}
        self.assertTrue(menu.load_problems(CAT, both, segs(text)))

    def test_light_words_a_story_no_limit_or_the_healthy_side_pass(self):
        for text in ("@@ 60 | Carry\nNothing too heavy on the farmer carry today, light pair.\n",
                     "@@ 60 | Carry\nA light pair for the farmer carry.\n[story] She lifted heavy at the farmer carry "
                     "worlds. [/story]\n"):
            self.assertEqual(menu.load_problems(CAT, KNEE, segs(text)), [], text)
        self.assertEqual(menu.load_problems(CAT, {"request": {}}, segs("@@ 60 | C\nA heavy farmer carry.\n")), [])
        right = {"request": {"limits": ["shoulder=delicate:right"]},
                 "movements": [{"id": "half-kneeling-kettlebell-press", "side": "left"}]}
        text = "@@ 60 | Press\nA heavy bell for the half-kneeling kettlebell press.\n"
        self.assertEqual(menu.load_problems(CAT, right, segs(text)), [])   # the left arm works; the right rests


class TheOpeningNamesTheSide(unittest.TestCase):
    """Under a one-sided limit, the opening names the sore side with its body part, never the other side's care."""

    def test_the_openings_side(self):
        """Each row: the limits, the welcome's words, and what the refusal says (None: it passes)."""
        both = {"request": {"limits": ["knee=delicate:left", "shoulder=off-limits:right"]}}
        rows = (
            (KNEE, "The right side stays light today, and no jumping.",
             "ties today's care to the right side, but the limit is the left knee"),
            (KNEE, "Your knee stays light today.", "never names the left knee"),
            (KNEE, "[pause 2s]\n\n@@ 40 | Set", None),   # a skeleton's empty opening waits for its words
            (KNEE, "Your left knee stays light today, and the right leg does the lunges, two left in the tank.", None),
            (KNEE, "Easy on the knee on the left today. Right side lateral lunges only.", None),
            (KNEE, "Your left-side knee stays light. [story] The right back was sore all season. [/story]", None),
            ({"request": {}}, "Twenty minutes, let's go.", None),
            ({"request": {"limits": ["knee=delicate:both"]}}, "Twenty minutes, let's go.", None),
            (both, "Your left knee stays light today, only as deep as is comfortable. Your right arm rests today, "
                   "nothing pushing or pulling on it.", None),
            (both, "Your left knee stays light today. Keep the left arm easy today.",
             '"Keep the left arm easy today" ties today\'s care to the left side'),
        )
        for limits, text, refused in rows:
            with self.subTest(text=text):
                found = menu.opening_problems(limits, segs(f"@@ 60 | Welcome\n{text}\n"))
                if refused is None:
                    self.assertEqual(found, [])
                else:
                    self.assertEqual(len(found), 1, found)
                    self.assertIn(refused, found[0])
        found = menu.opening_problems(KNEE, segs("@@ 60 | Welcome\nThe right side stays light today.\n"))
        self.assertIn('"Your left knee stays light today', found[0])   # the brief's own line, to put back

    def test_the_healthy_sides_set_may_name_the_resting_side_only_to_spare_it(self):
        # the brief's own opening line names the sore side; the welcome naming the left-arm press may still say it
        ok = ("Your right arm rests today, nothing pushing, pulling or leaning on it. "
              "Today it's the left single-arm floor press, left side only.")
        self.assertEqual(menu.side_problems(CAT, PRESS, ok), [])
        own = "Your right arm sits out. Today it's the left single-arm floor press, left side only."
        self.assertTrue(menu.side_problems(CAT, PRESS, own))   # the writer's own wording still fails safe
        # an off-limits area's stop signs go at the first working set, often the healthy side's movement
        for line in ("Stop that movement on any pain in the right shoulder.",
                     "Stop for today on pain in that shoulder that's still worse than when you started after a short rest."):
            self.assertEqual(menu.side_problems(CAT, PRESS, f"Left single-arm floor press, left side only. {line}"),
                             [], line)
        turn = "Left single-arm floor press. Any pain in the right shoulder, then switch to it."
        self.assertTrue(menu.side_problems(CAT, PRESS, turn))

    def test_the_resting_sides_care_warns_and_a_turn_to_it_stops(self):
        for line in ("Down to the floor without loading that right arm.", "The other arm rests limp.",
                     "Notice how that left knee and right shoulder feel.", "Keep your right arm totally relaxed.",
                     "Done, protecting your left knee and keeping off that right shoulder."):
            stops, warns = menu.side_issues(CAT, PRESS, f"Left single-arm floor press, ten. {line}")
            self.assertEqual(stops, [], line)
            self.assertTrue(warns, line)
        for turn in ("Left single-arm floor press, ten. Then the right.", "Left single-arm floor press, ten each side.",
                     "Left single-arm floor press. Now switch arms.", "Left single-arm floor press with both arms."):
            self.assertTrue(menu.side_issues(CAT, PRESS, turn)[0], turn)
        for line in ("If it felt smooth, hold steady right there.", "Pin both shoulder blades to the floor.",
                     "All right, right now we press."):   # idioms and setup cues are no side
            self.assertEqual(menu.side_issues(CAT, PRESS, f"Left single-arm floor press, ten. {line}"), ([], []), line)

    def test_heavy_and_the_other_sides_care_are_warnings_in_the_build(self):
        menu_ = {"request": {"limits": ["knee=delicate:left"]}, "seconds": 120,
                 "movements": [{"id": "farmer-carry"}]}
        text = ("movements: farmer carry\n@@ 60 | Welcome\nMade by AI, so your body has the final say. Your left knee "
                "stays easy.\n@@ 60 | Carry\nPick up a heavy pair for the farmer carry, and walk.\n")
        issues, warnings = menu.check(CAT, menu_, text, draft.parse(text))
        self.assertEqual(issues, [])
        self.assertTrue(any("heavy" in w for w in warnings))
        text = "@@ 60 | Welcome\nYour left knee stays light today. Keep the right side easy too.\n"
        stops, warns = menu.opening_issues(KNEE, segs(text))
        self.assertEqual(stops, [])
        self.assertTrue(warns)

    def test_the_opening_says_its_made_by_ai(self):
        two = "@@ 60 | Welcome\n{}\n@@ 60 | Set\nTen reps.\n"
        self.assertTrue(menu.ai_problems(segs(two.format("Twenty minutes, let's go."))))
        self.assertTrue(menu.ai_problems(segs(two.format("Plan A is the push-up. I like it. PAIN means stop."))))
        for said in ("This was put together by AI, so you have the final say.", "Written by artificial intelligence.",
                     "This workout was put together by an A I, not a trainer.", "Made by A.I., as always.",
                     "An A. I. wrote this one."):   # spelled out for the voice, as a host writes it
            self.assertEqual(menu.ai_problems(segs(two.format(said))), [], said)
        self.assertEqual(menu.ai_problems(segs(two.format("[pause 2s]"))), [])          # a skeleton's empty welcome
        self.assertEqual(menu.ai_problems(segs("@@ 60 | Work\nTen reps.\n")), [])       # a fragment has no opening


class OrdinarySpeech(unittest.TestCase):
    """The menu check reads a name, not every phrase that shares its words (eval round 3, 2026-11-02)."""

    def test_a_name_used_as_a_verb_is_no_movement_and_not_using_one_is_a_negation(self):
        def said(text):
            return [(mid, menu.negated(before)) for mid, _, before in menu.mentions(CAT, text)]
        self.assertEqual(said("Holding the weight at your chest presses on the ribs, so keep it high."), [])
        self.assertEqual(said("Ten chest presses on the bench."), [("machine-chest-press", False)])
        self.assertEqual(said("Do ten chest presses."), [("machine-chest-press", False)])
        self.assertEqual(said("We are not using the goblet squat today."), [("goblet-squat", True)])
        self.assertEqual(said("Do not stop your goblet squats."), [("goblet-squat", False)])


class Reps(unittest.TestCase):
    """[reps N]: a set's reps timed against the movement, so its words fit its seconds."""
    V = {"name": "x", "key": "x", "engine": "chatterbox", "model": "m"}

    def lint(self, text, timer="catalog"):
        timer = build.rep_timer(CAT) if timer == "catalog" else timer
        with mock.patch("voices.pace", return_value=(14.0, True)):
            return tts_build.lint(draft.parse("movements: goblet squat\n" + text), self.V, rep_timer=timer)

    def issues(self, text, timer="catalog"):
        return " ".join(i for r in self.lint(text, timer).rows for i in r.clip_issues)

    def test_the_marker_is_silent_and_times_the_set(self):
        seg = draft.parse("@@ 40 | Goblet squat\nTen reps. [count 3 go] [reps 10] Sit down slow.\n")[0]
        self.assertEqual([t for para in draft.plan(seg) for t, _ in para if "reps 10" in t], [])
        self.assertEqual(tts_build.lint_line(1, "[count 3 go] [reps 10] Sit down slow."), [])
        self.assertEqual(tts_build.word_count(seg["lines"]), 5)
        cues = ("Sit down slow between your heels. [hold 3s] Drive up through the whole foot. [hold 3s] Keep the chest "
                "proud and the elbows in. [hold 3s] Breathe out as you stand. [hold 3s] Last two, smooth, and set it down.")
        self.assertEqual(self.issues(f"@@ 45 | Goblet squat\nGoblet squat, ten reps. [count 3 go] [reps 10] {cues}\n"), "")
        self.assertRegex(self.issues("@@ 45 | Goblet squat\nGoblet squat, ten reps. [count 3 go] [reps 10] Down slow, "
                                     "and up.\n"), r"10 reps of goblet squat take about \d+ s .* add about \d+ s")
        self.assertRegex(self.issues("@@ 90 | Goblet squat\nGoblet squat. [count 3 go] [reps 4] " + cues + " " + cues
                                     + "\n"), r"cut about \d+ s")
        plain = self.lint("@@ 45 | Goblet squat\n[count 3 go]\n").rows[0].guide
        skeleton = self.lint("@@ 45 | Goblet squat\n[count 3 go] [reps 10]\n").rows[0].guide
        self.assertLess(skeleton, plain - 20)   # ten reps' quiet isn't talk

    def test_what_cant_be_timed_or_has_no_go_is_named(self):
        """Each row: a segment, and the words its refusal holds."""
        rows = (("@@ 40 | Goblet squat\n[count 3 go] [reps ten] Down slow. [hold 3s] Up.\n", "write [reps N]"),
                ("@@ 40 | Forearm plank\nForearm plank. [count 3 go] [reps 10] Brace. [hold 3s] Breathe.\n",
                 "timed, not counted"),
                ("@@ 40 | Goblet squat\n[count 3 go] [reps 10] Down slow. [hold] Up.\n", "a bare [hold] after [reps 10]"),
                ("@@ 40 | Goblet squat\n[reps 8] [count 3 go]\n", "comes before the set's go"),
                ("@@ 10 | Warm-up\nGoblet squats first. [count 3 go]\n\n@@ 40 | Goblet squat\n[reps 8]\n",
                 "has no go before it in this segment"))
        for text, words in rows:
            with self.subTest(words=words):
                self.assertIn(words, self.issues(text))
        self.assertIn("no go", self.issues("@@ 40 | Goblet squat\n[reps 8]\n", timer=None))   # a skeleton too
        for fine in ("[count 3 go] [reps 8]", "[cue go] [reps 8]", "Ready, and go. [reps 8]",
                     "[count 3 go] [reps 8] [hold 3s] Switch sides. [reps 8]"):
            self.assertNotIn("go before", self.issues(f"@@ 60 | Goblet squat\n{fine}\n"), fine)


class TimeChecks(unittest.TestCase):
    """A time the coach says in words ("fifteen seconds left") is true where the render lays it (2026-11-22: "twenty-two
    down", "fifteen left" and "ten left" came seconds apart)."""
    V = {"name": "x", "key": "x", "engine": "chatterbox", "model": "m"}

    def issues(self, body, seconds=60):
        with mock.patch("voices.pace", return_value=(14.5, True)):
            report = tts_build.lint(draft.parse(f"@@ {seconds} | Plank\n{body}\n"), self.V, headroom=False)
        return [i for r in report.rows for i in r.clip_issues if "takes the coach's word" in i]

    def test_time_checks_bunched_together_are_refused(self):
        bunched = ("Plank, forty seconds, hips level. [count 3 go]\nBreathe, long and slow. [hold]\n"
                   "Twenty-two seconds down. Fifteen seconds left. Ten seconds left, stay tall. [cue rest]")
        self.assertEqual(len(self.issues(bunched, 45)), 3)

    def test_time_checks_where_they_are_true_pass(self):
        placed = ("Plank, forty seconds, hips level. [count 3 go]\nBreathe, long and slow. [hold 5s]\n"
                  "Squeeze the glutes and keep the ribs down. [hold 5s]\nHalfway, keep breathing. [hold 5s]\n"
                  "Long through the heels, stay with it. [hold]\nTen seconds left. [hold 4s] [count 5 rest]")
        self.assertEqual(self.issues(placed, 50), [])

    def test_a_storys_clock_is_the_storys(self):
        told = ("Plank, forty seconds. [count 3 go]\n[story] Ten seconds left in the final, and she shot from the "
                "halfway line. Twenty seconds down and it went in. [/story]\n[hold]\nStay with it. "
                "[hold 4s] [count 5 rest]")
        self.assertEqual(self.issues(told, 50), [])


if __name__ == "__main__":
    unittest.main()
