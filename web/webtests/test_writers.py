"""The writers' room (the site's way since 0.51.0; trainer, researcher, host and review since 0.55.0): what code does
around the models, without them."""
import os
import sys
import unittest

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from pydantic_ai.messages import ModelResponse, TextPart  # noqa: E402
from pydantic_ai.models.function import FunctionModel  # noqa: E402

from webapp import agent  # noqa: E402
from webapp.agent import tools, writers  # noqa: E402
from webapp.agent.writers import Edited, Told  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

SKELETON = """movements: goblet-squat, box-breathing
@@ 60 | Welcome
@@ 50 | Goblet squat set one
[count 3 go]
@@ 90 | Rest after goblet squat set one
@@ 50 | Goblet squat set two
[count 3 go]
@@ 20 | Rest before the last set
@@ 60 | Box breathing and close
[pause 4s]
"""

REPORT = """Skeleton: 6 segments, 330 s. Word budgets with Coach Freya (about 147 words a minute):
  #  secs budget words to write  label
  1    60    147     0      147  Welcome
  2    50    118     0      118  Goblet squat set one
  3    90    219     0      219  Rest after goblet squat set one
  4    50    118     0      118  Goblet squat set two
  5    20     49     0       49  Rest before the last set
  6    60    140     0      140  Box breathing and close
About 791 words still to write."""


def told(number, text, title="A title"):
    return Told(number=number, topic="-", format="quick_hit", title=title, source="the feeds sheet", text=text)


class Plan(unittest.TestCase):
    def test_budgets_are_read_from_the_skeletons_report(self):
        self.assertEqual(writers.budgets(REPORT), {1: 147, 2: 118, 3: 219, 4: 118, 5: 49, 6: 140})

    def test_only_a_rest_long_enough_carries_a_story(self):
        _, segs = writers.split(SKELETON)
        rests = writers.slots(segs, writers.budgets(REPORT))
        # the welcome, the sets, a twenty-second rest and the breathing close carry none
        self.assertEqual(rests, {3: (219 - 153, 153)})

    def test_the_trainer_sees_the_clock_and_where_each_story_goes_not_word_counts(self):
        _, segs = writers.split(SKELETON)
        budget = writers.budgets(REPORT)
        rests = writers.slots(segs, budget)
        self.assertEqual(writers.story_words(budget, rests), {3: writers.STORY_WORDS})
        table = writers._plan_table(segs, budget, {3: 140})
        row = next(r for r in table.split("\n") if r.startswith("#3 "))
        self.assertIn("A story is told here, in the rest.", row)
        self.assertIn("Markers: [count 3 go]", table)
        self.assertNotIn("words", table)

    def test_the_host_gets_each_segments_words_markers_notes_and_story(self):
        _, segs = writers.split(SKELETON)
        budget = writers.budgets(REPORT)
        plan = writers.host_plan(segs, budget, {2: "SAY EXACTLY: Knees over the toes.\nTen reps, two in the tank."},
                                 {3: told(3, "Why it's theirs: their team.\nThe Flyers won four to two.")})
        two = plan.split("## #2 ", 1)[1].split("## #3 ", 1)[0]
        self.assertIn(f"Write about {round(118 * writers.COACH_AIM)} words. Markers, in order: [count 3 go].", two)
        self.assertIn("SAY EXACTLY: Knees over the toes.", two)
        three = plan.split("## #3 ", 1)[1].split("## #4 ", 1)[0]
        self.assertIn("Tell this story here (in the rest; quick_hit, -):\nWhy it's theirs: their team.", three)
        self.assertIn("Trainer's notes:\nnone", three)

    def test_a_story_rest_tells_the_host_the_storys_share_of_its_words(self):
        _, segs = writers.split(SKELETON)
        budget = writers.budgets(REPORT)
        rests = writers.slots(segs, budget)
        plan = writers.host_plan(segs, budget, {}, {3: told(3, "The Flyers won four to two.")}, frozenset(), rests)
        three = plan.split("## #3 ", 1)[1].split("## #4 ", 1)[0]
        words = round(budget[3] * writers.COACH_AIM)
        self.assertIn(f"Write about {words} words. About {round(words * rests[3][1] / budget[3])} of them are the "
                      "story, told whole", three)
        two = plan.split("## #2 ", 1)[1].split("## #3 ", 1)[0]
        self.assertNotIn("of them are the story", two)

    def test_the_review_gets_the_must_say_lines_as_a_checklist(self):
        notes = {1: "Warm welcome.\nSAY, EVERY PART KEPT: Your left knee stays light today.\nSAY EXACTLY: Stop on a pinch.",
                 4: "- SAY EXACTLY: Keep the left knee over the toes.", 2: "Ten reps."}
        self.assertEqual(writers.must_say(notes),
                         "- #1, every part kept: Your left knee stays light today.\n"
                         "- #1, word for word: Stop on a pinch.\n"
                         "- #4, word for word: Keep the left knee over the toes.")
        self.assertEqual(writers.must_say({1: "No lines to say."}), "")

    def test_a_hold_longer_than_the_silence_limit_becomes_words_to_talk_through(self):
        skeleton = ("movements: plank\n@@ 60 | Plank\n[count 3 go]\n[hold 40s]\n[cue rest]\n"
                    "@@ 30 | Breathing\n[pause 4s] [pause 6s]\n")
        out, freed = writers.open_holds(skeleton)
        self.assertEqual(freed, {1: 40.0})
        self.assertEqual(out, "movements: plank\n@@ 60 | Plank\n[count 3 go]\n[cue rest]\n"
                              "@@ 30 | Breathing\n[pause 4s] [pause 6s]\n")

    def test_a_steady_timed_set_marked_in_the_skeleton_carries_a_story_and_says_how(self):
        skeleton = SKELETON.replace("@@ 50 | Goblet squat set two\n[count 3 go]\n",
                                    "@@ 50 | Goblet squat set two\n[count 3 go] [story] [/story]\n[hold]\n[cue rest]\n")
        _, segs = writers.split(skeleton)
        budget = writers.budgets(REPORT)
        self.assertEqual(writers.steady(segs), {4})
        warm = writers.split(SKELETON.replace("@@ 60 | Welcome\n", "@@ 60 | Welcome\n[count 3 go] [story] [/story]\n"))[1]
        self.assertIn(1, writers.slots(warm, budget))   # a marked warm-up carries one, though it opens the session
        rests = writers.slots(segs, budget)
        self.assertEqual(rests[4], (118 - round(118 * writers.WORK_STORY_SHARE), round(118 * writers.WORK_STORY_SHARE)))
        table = writers._plan_table(segs, budget, writers.story_words(budget, rests), frozenset({4}))
        row = next(r for r in table.split("\n") if r.startswith("#4 "))
        self.assertIn("A story is told here, during the set, after its first cue.", row)
        self.assertIn("Markers: [count 3 go] [hold] [cue rest]", row)   # the mark itself isn't the coach's to write

    def test_each_story_goes_to_a_slot_it_suits_in_the_order_told(self):
        quiz = Told(number=1, topic="-", format="quiz", title="Q", source="s", text="Which planet?", lands="rest")
        serial = Told(number=2, topic="-", format="serial", title="S", source="s", text="Part one.", lands="steady")
        answer = Told(number=3, topic="-", format="quiz", title="A", source="s", text="Venus.", lands="rest")
        placed = writers.place([quiz, serial, answer], {2: (10, 50), 3: (10, 50), 5: (10, 50)}, {2})
        self.assertEqual({n: s.title for n, s in placed.items()}, {2: "S", 3: "Q", 5: "A"})

    def test_a_guide_bullet_renamed_away_is_an_error_not_a_silent_gap(self):
        with self.assertRaises(ValueError):
            writers.bullets("- **One thing.** Text.", "Another thing")

    def test_a_thirty_minute_session_asks_for_about_a_dozen_stories(self):
        self.assertEqual(writers.pieces_for(30), 12)
        self.assertEqual(writers.pieces_for(10), 4)
        self.assertEqual(writers.pieces_for(1), 2)


class Assemble(unittest.TestCase):
    def test_the_hosts_script_keeps_the_skeletons_clock_and_a_segment_left_out_keeps_its_markers(self):
        draft = writers.apply_edits(SKELETON, [
            Edited(number=1, text="Evening. Second one today."),
            Edited(number=3, text="Set it down.\n\n[story] The Flyers won. [/story]\n\nPick the bell back up.")])
        self.assertEqual([ln for ln in draft.split("\n") if ln.startswith("@@")],
                         [ln for ln in SKELETON.split("\n") if ln.startswith("@@")])
        self.assertIn("@@ 60 | Welcome\nEvening. Second one today.\n", draft)
        self.assertIn("Set it down.\n\n[story] The Flyers won. [/story]\n\nPick the bell back up.", draft)
        self.assertIn("@@ 50 | Goblet squat set two\n[count 3 go]", draft)   # the lint says what's left

    def test_the_editor_changes_only_the_words_of_the_segments_it_returns(self):
        draft = "movements: plank\n@@ 30 | Welcome\nHello.\n\n@@ 40 | Plank\n[count 3 go] Brace.\n"
        out = writers.apply_edits(draft, [Edited(number=1, text="@@ 99 | Hijacked\nEvening, Sam."),
                                          Edited(number=7, text="nothing there")])
        self.assertEqual(out, "movements: plank\n@@ 30 | Welcome\nEvening, Sam.\n\n@@ 40 | Plank\n[count 3 go] Brace.\n")
        self.assertIn("#2 @@ 40 | Plank", writers.numbered(draft))

    def test_a_retold_item_is_caught_by_its_words(self):
        titles = writers.told_titles("## Told in the last 30 days\n- 2026-11-01 New Jersey Devils / quick_hit: "
                                     "Devils beat Golden Knights 5-2 in Vegas\n")
        self.assertEqual(titles, ["Devils beat Golden Knights 5-2 in Vegas"])
        again = told(3, "The Devils went into Vegas and beat the Golden Knights five to two.", "Devils win in Vegas")
        self.assertEqual(writers.retold(again, titles), titles[0])
        self.assertIsNone(writers.retold(told(3, "The Devils host the Oilers on Tuesday night."), titles))


class Brief(unittest.TestCase):
    def test_the_coach_gets_only_the_plans_movements_from_the_menu(self):
        brief = ("# Today's brief\nWritten at 17:48.\n\n## The listener\n- Name: Sam\n\n## Safe menu\nEvery movement...\n"
                 "LIGHT ONLY today marks a movement that loads a limited area.\n\n### squat\n"
                 "- **goblet squat** (`goblet-squat`): standing; kettlebell; LIGHT ONLY today.\n  Easier: air squat\n"
                 "- **air squat** (`air-squat`): standing; bodyweight.\n### Healthy side only\n"
                 "Only the named side works; say why the other side rests.\n"
                 "- **step-up** (`step-up`): standing, right side only; box.\n\n"
                 "## Writing it\n- First line: movements.\n- Counts: write a countdown as [count 5].\n")
        out = writers.coach_brief(brief, ["goblet-squat", "step-up"])
        self.assertIn("goblet squat", out)
        self.assertIn("  Easier: air squat", out)
        self.assertNotIn("(`air-squat`)", out)
        self.assertIn("right side only; box. (healthy side only)", out)
        self.assertIn("Only the named side works", out)
        self.assertIn("LIGHT ONLY today marks", out)
        self.assertIn("- Counts:", out)
        self.assertNotIn("First line", out)

    def test_each_writer_reads_its_part_of_the_guides_without_commands(self):
        g = writers.guides(ROOT)
        trainer, research, host, review = g["trainer"], g["research"], g["host"], g["review"]
        self.assertIn("## Safety: the rules", trainer)
        self.assertIn("SAY EXACTLY:", trainer)
        self.assertIn("Set it up, then keep them company", trainer)
        self.assertNotIn("Set it up, then keep them company", research)
        self.assertIn("Tell it the way a friend would", research)
        self.assertIn("Never invent facts", research)
        self.assertIn("Weave threads.** A quiz", research)
        # the host writes every word: the voice, the craft and what a voice can read, the safety lines from the notes
        self.assertIn("The coach's voice", host)
        self.assertIn("## Markers", host)
        self.assertNotIn("## Safety: the rules", host)
        self.assertIn("Leave the host's voice alone", review)
        self.assertIn("## Safety: the rules", review)
        for text in (trainer, research, host, review):
            self.assertNotIn("./harmonicfitness", text)
            self.assertNotIn("<!-- web", text)


class Patience(unittest.TestCase):
    def test_a_writer_past_its_patience_is_asked_again_thinking_less(self):
        import asyncio
        from pydantic_ai.messages import ToolCallPart
        from pydantic_ai.usage import RunUsage
        calls = []

        async def reply(messages, info):
            calls.append(len(calls))
            if len(calls) == 1:
                await asyncio.sleep(1)   # the first try thinks too long
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"segments": []})])
        deps = tools.Deps(engine_root=ROOT, home=ROOT, keys={}, today="2026-11-01", now="2026-11-01 Sunday 08:00")
        old = dict(writers.PATIENCE)
        writers.PATIENCE["review"] = 0.2
        self.addCleanup(writers.PATIENCE.update, old)
        out = asyncio.run(writers._ask(deps, "review", writers.REVIEW, FunctionModel(reply), "edit", RunUsage(), "HIGH"))
        self.assertEqual(out.output.segments, [])
        self.assertEqual(len(calls), 2)   # asked once more, a level lower


class Switch(unittest.TestCase):
    def test_the_instructions_name_one_way_of_writing(self):
        one, two = agent.preamble("one"), agent.preamble("three")
        for text in (one, two):
            self.assertNotIn("<!-- writers", text)
        self.assertIn("You have web search", one)
        self.assertNotIn("write_script", one)
        self.assertIn("write_script", two)
        self.assertIn("Then the rests and the marked timed sets, in one `edit_segments`", one)
        self.assertNotIn("Then the rests and the marked timed sets, in one `edit_segments`", two)
        self.assertEqual(agent.PREAMBLE, one)
        # with three writers the agent reads script.md's safety, not the craft the writers write by
        self.assertIn("Set it up, then keep them company", agent.skill_text(ROOT))
        self.assertNotIn("Set it up, then keep them company", agent.skill_text(ROOT, writers="three"))
        self.assertIn("Only the menu.", agent.skill_text(ROOT, writers="three"))

    def test_write_script_is_offered_only_to_a_three_writer_turn(self):
        for writers_, offered in (("one", False), ("three", True)):
            seen = []

            def reply(messages, info):
                seen.append({t.name for t in info.function_tools})
                return ModelResponse(parts=[TextPart("ok")])
            deps = tools.Deps(engine_root=ROOT, home=ROOT, keys={}, today="2026-11-01", now="2026-11-01 Sunday 08:00",
                              writers=writers_)
            agent.AGENT.run_sync("hi", model=FunctionModel(reply), deps=deps)
            self.assertEqual("write_script" in seen[0], offered, writers_)
            self.assertIn("edit_segments", seen[0])

    def test_a_turn_has_three_writers_unless_the_setting_says_one(self):
        def reply(messages, info):
            return ModelResponse(parts=[TextPart("ok")])
        for setting, want in ((None, "three"), ("one", "one"), ("nonsense", "three")):
            deps = tools.Deps(engine_root=ROOT, home=ROOT, keys={}, today="2026-11-01", now="2026-11-01 Sunday 08:00")
            old = os.environ.pop("HARMONICFITNESS_WRITERS", None)
            if setting:
                os.environ["HARMONICFITNESS_WRITERS"] = setting
            try:
                agent.run_turn(FunctionModel(reply), deps, None, "hi")
            finally:
                os.environ.pop("HARMONICFITNESS_WRITERS", None)
                if old is not None:
                    os.environ["HARMONICFITNESS_WRITERS"] = old
            self.assertEqual(deps.writers, want, setting)

    def test_contractions_leave_a_clause_ending_verb_alone(self):
        self.assertEqual(tools.contract("Stay where you are or drop a plate.")[0], "Stay where you are or drop a plate.")
        self.assertEqual(tools.contract("You are almost there, and that is it.")[0], "You're almost there, and that's it.")
        self.assertEqual(tools.contract("Where you do not rush.")[0], "Where you don't rush.")


if __name__ == "__main__":
    unittest.main()
