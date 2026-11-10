"""The script-writing bench's quality checks and gate (web/bench/, which isn't a package)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bench"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import compare  # noqa: E402
import summarize  # noqa: E402

DAY_RULE = "## Never bring up\n- News, politics, today's date, the day of the week, the season or the weather\n"


class NeverSaid(unittest.TestCase):
    def test_a_weekday_is_flagged_when_the_day_is_never_brought_up(self):
        self.assertEqual(summarize.never_said("@@ 50 | Welcome\nTuesday, fifteen minutes.\n", DAY_RULE), ["Tuesday"])

    def test_nothing_is_flagged_when_the_listener_allows_it(self):
        self.assertEqual(summarize.never_said("@@ 50 | Welcome\nTuesday, fifteen minutes.\n", "## Never bring up\n- Politics\n"), [])

    def test_a_label_is_not_spoken_and_a_season_and_the_weather_are(self):
        draft = "@@ 50 | Winter warm-up\nIt is a rainy morning, a winter one.\n"
        self.assertEqual(summarize.never_said(draft, DAY_RULE), ["rainy", "winter"])


    def test_a_weekday_in_a_story_is_not_flagged_but_in_the_coaching_is(self):
        story = "@@ 50 | Rest\n[story] On Sunday night in nineteen seventy it happened. [/story]\n"
        self.assertEqual(summarize.never_said(story, DAY_RULE), [])
        self.assertEqual(summarize.never_said("@@ 50 | Welcome\nIt is Sunday.\n" + story, DAY_RULE), ["Sunday"])


class NotInNotes(unittest.TestCase):
    def check(self, notes, story):
        w = [{"who": "research", "prompt": "", "output": {"s": notes}}]
        return summarize.fidelity({"draft": f"@@ 60 | A\n@@ 60 | B\n[story] {story} [/story]\n@@ 60 | C\n", "writers": w})[0]

    def test_number_words_and_ordinals_are_not_names(self):
        self.assertEqual(self.check("nothing", "It was on the Thirtieth, aboard X-One, then Two."), [])

    def test_accents_are_folded(self):
        self.assertEqual(self.check("they met at a cafe", "They met at the Café."), [])

    def test_a_real_unknown_name_is_still_flagged(self):
        self.assertEqual(self.check("nothing", "It was Margaret Hamilton."), ["Hamilton", "Margaret"])


    def test_a_top_up_storys_names_count_as_noted(self):
        writers = [{"who": "research", "prompt": "", "output": {"stories": [{"text": "Miles Davis at Thirtieth Street"}]}},
                   {"who": "top-up", "prompt": "", "output": {"stories": [{"text": "Margaret Hamilton wrote the code"}]}}]
        draft = "@@ 60 | Welcome\n@@ 60 | Rest\n[story] Margaret Hamilton led the software team. [/story]\n@@ 60 | Close\n"
        unknown, _ = summarize.fidelity({"draft": draft, "writers": writers})
        self.assertEqual(unknown, [])


OK = {"priced": True, "lint_clean": True, "opening": [], "not_in_notes": [], "one_voice": [], "never_said": [],
      "cost": 0.20, "requests": 30, "input": 100000, "from_brief": 150}


class Gate(unittest.TestCase):
    base = [OK, {**OK, "cost": 0.22}, {**OK, "cost": 0.18}]

    def test_gate_passes_when_every_run_is_compliant_and_no_dearer(self):
        self.assertEqual(compare.gate(self.base, [{**OK, "cost": 0.15}] * 3), "GATE: pass (3 completed)")

    def test_gate_fails_when_any_candidate_run_is_not_compliant(self):
        self.assertIn("GATE: fail", compare.gate(self.base, [OK, OK, {**OK, "lint_clean": False}]))

    def test_gate_fails_on_a_flagged_check(self):
        self.assertIn("never_said", compare.gate(self.base, [OK, {**OK, "never_said": ["Tuesday"]}]))

    def test_a_provider_error_run_is_not_a_failure(self):
        err = {**OK, "priced": False, "lint_clean": False, "opening": ["no draft"], "error": "ModelHTTPError: status_code: 504, body"}
        out = compare.gate(self.base, [OK, OK, OK, err])
        self.assertTrue(out.startswith("GATE: pass"))
        self.assertIn("1 provider error", out)

    def test_too_few_completed_runs_fails(self):
        err = {**OK, "priced": False, "error": "ModelHTTPError: status_code: 429, body"}
        out = compare.gate(self.base, [OK, OK, err])
        self.assertIn("GATE: fail", out)
        self.assertIn("completed", out)

    def test_gate_fails_when_the_median_cost_is_higher(self):
        self.assertIn("cost", compare.gate(self.base, [{**OK, "cost": 0.30}] * 3))


class AgainstTheCommittedRuns(unittest.TestCase):
    def test_a_committed_run_reads_through_the_gate(self):
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "benchmark-script-writing", "20261110", "gemini-1")
        row = compare.run_row(d)
        self.assertTrue(row["priced"])
        self.assertGreater(row["cost"], 0)
        self.assertGreater(row["requests"], 0)


if __name__ == "__main__":
    unittest.main()
