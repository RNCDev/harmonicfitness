"""The two writers' version (HARMONICFITNESS_WRITERS=two): what code does around the two models, without them."""
import os
import sys
import unittest

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from pydantic_ai.messages import ModelResponse, TextPart  # noqa: E402
from pydantic_ai.models.function import FunctionModel  # noqa: E402

from webapp import agent  # noqa: E402
from webapp.agent import tools, writers  # noqa: E402
from webapp.agent.writers import Told, Written  # noqa: E402

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


def told(rest, text, title="A title"):
    return Told(rest=rest, topic="-", format="quick_hit", title=title, source="the feeds sheet", text=text)


class Plan(unittest.TestCase):
    def test_budgets_are_read_from_the_skeletons_report(self):
        self.assertEqual(writers.budgets(REPORT), {1: 147, 2: 118, 3: 219, 4: 118, 5: 49, 6: 140})

    def test_only_a_rest_long_enough_carries_a_story(self):
        _, segs = writers.split(SKELETON)
        rests = writers.slots(segs, writers.budgets(REPORT))
        # the welcome, the sets, a twenty-second rest and the breathing close carry none
        self.assertEqual(rests, {3: (219 - 153, 153)})

    def test_the_coach_is_shown_each_story_and_writes_the_rest_of_its_rest(self):
        _, segs = writers.split(SKELETON)
        budget = writers.budgets(REPORT)
        story = told(1, "The Devils host the Oilers on Tuesday at seven thirty.")
        table = writers._plan_table(segs, budget, {3: (66, 153)}, {3: story}, "Stay for the answer.", "It was Venus.")
        row = next(r for r in table.split("\n") if r.startswith("#3 "))
        self.assertIn(f"about {round(219 * writers.COACH_AIM) - 10} words together", row)
        self.assertIn('"The Devils host the Oilers on Tuesday at seven thirty."', row)
        self.assertIn('ending on this line, which code adds: "Stay for the answer."', table)
        self.assertIn('after this line, which code puts first: "It was Venus."', table)
        self.assertIn("Markers: [count 3 go]", table)

    def test_three_story_writers_share_the_topics_and_the_rests(self):
        plan = ("## Topics due (never told first)\n- Yankees: scores\n- Soccer: the big matches\n- Deep tech: chips\n"
                "- Science: breakthroughs\n- TV (spare): prestige TV\n\n## What's on\n- Helium: comedy\n")
        parts = writers.split_topics(plan, 12)
        self.assertEqual([(a, b) for a, b, _ in parts], [(1, 4), (5, 8), (9, 12)])
        self.assertEqual(parts[0][2], ["Yankees", "Science"])
        self.assertIn("TV", parts[1][2])
        self.assertTrue(any("what's on" in x for x in parts[1][2]))
        topics = [x for _, _, ts in parts for x in ts]
        self.assertEqual(len(topics), len(set(topics)))
        self.assertEqual(writers.split_topics("no plan", 4), [(1, 4, ["any of the plan's topics"])])

    def test_a_hold_longer_than_the_silence_limit_becomes_words_to_talk_through(self):
        skeleton = ("movements: plank\n@@ 60 | Plank\n[count 3 go]\n[hold 40s]\n[cue rest]\n"
                    "@@ 30 | Breathing\n[pause 4s] [pause 6s]\n")
        out, freed = writers.open_holds(skeleton)
        self.assertEqual(freed, {1: 40.0})
        self.assertEqual(out, "movements: plank\n@@ 60 | Plank\n[count 3 go]\n[cue rest]\n"
                              "@@ 30 | Breathing\n[pause 4s] [pause 6s]\n")

    def test_a_thirty_minute_session_asks_for_about_a_dozen_stories(self):
        self.assertEqual(writers.pieces_for(30), 12)
        self.assertEqual(writers.pieces_for(10), 4)
        self.assertEqual(writers.pieces_for(1), 2)


class Assemble(unittest.TestCase):
    def test_each_rest_is_opener_story_handback_and_the_clock_is_the_skeletons(self):
        _, segs = writers.split(SKELETON)
        rests = writers.slots(segs, writers.budgets(REPORT))
        coaching = {1: Written(number=1, text="Evening. Second one today."),
                    2: Written(number=2, text="Ten goblet squats. [count 3 go] Sit down between the heels."),
                    3: Written(number=3, text="Set it down.", handback="Pick the bell back up."),
                    6: Written(number=6, text="Breathe in for four. [pause 4s] Good work today.")}
        draft = writers.assemble(SKELETON, coaching, {3: told(3, "First part.\n\nSecond [hold] part.")},
                                 "Stay for the answer.", "The answer is Venus.", rests)
        self.assertEqual([ln for ln in draft.split("\n") if ln.startswith("@@")],
                         [ln for ln in SKELETON.split("\n") if ln.startswith("@@")])
        rest = draft.split("@@ 90 | Rest after goblet squat set one\n")[1].split("@@")[0]
        self.assertEqual(rest.strip(), "Set it down.\n\n[story] First part.\n\nSecond part. [/story]\n\n"
                                       "Pick the bell back up.")
        self.assertIn("Second one today.\n\n[story] Stay for the answer. [/story]", draft)
        self.assertIn("[story] The answer is Venus. [/story]\n\nBreathe in for four.", draft)
        # a segment the coach didn't return keeps its markers, so the lint says what's left
        self.assertIn("@@ 50 | Goblet squat set two\n[count 3 go]", draft)

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
        coach, story = writers.guides(ROOT)
        self.assertIn("## Safety: the rules", coach)
        self.assertIn("Coach fully once", coach)
        self.assertNotIn("Coach fully once", story)
        self.assertIn("A rest holds one story", story)
        self.assertIn("Never invent facts", story)
        self.assertIn("Weave threads.** A quiz", story)
        for text in (coach, story):
            self.assertNotIn("./harmonicfitness", text)
            self.assertNotIn("<!-- web", text)


class Switch(unittest.TestCase):
    def test_the_instructions_name_one_way_of_writing(self):
        one, two = agent.preamble("one"), agent.preamble("two")
        for text in (one, two):
            self.assertNotIn("<!-- writers", text)
        self.assertIn("You have web search", one)
        self.assertNotIn("write_script", one)
        self.assertIn("write_script", two)
        self.assertNotIn("Then the rests, in one `edit_segments`", two)
        self.assertEqual(agent.PREAMBLE, one)
        # with two writers the agent reads script.md's safety, not the craft the writers write by
        self.assertIn("Coach fully once", agent.skill_text(ROOT))
        self.assertNotIn("Coach fully once", agent.skill_text(ROOT, writers="two"))
        self.assertIn("Only the menu.", agent.skill_text(ROOT, writers="two"))

    def test_write_script_is_offered_only_to_a_two_writer_turn(self):
        for writers_, offered in (("one", False), ("two", True)):
            seen = []

            def reply(messages, info):
                seen.append({t.name for t in info.function_tools})
                return ModelResponse(parts=[TextPart("ok")])
            deps = tools.Deps(engine_root=ROOT, home=ROOT, keys={}, today="2026-11-01", now="2026-11-01 Sunday 08:00",
                              writers=writers_)
            agent.AGENT.run_sync("hi", model=FunctionModel(reply), deps=deps)
            self.assertEqual("write_script" in seen[0], offered, writers_)
            self.assertIn("edit_segments", seen[0])

    def test_contractions_leave_a_clause_ending_verb_alone(self):
        self.assertEqual(tools.contract("Stay where you are or drop a plate.")[0], "Stay where you are or drop a plate.")
        self.assertEqual(tools.contract("You are almost there, and that is it.")[0], "You're almost there, and that's it.")
        self.assertEqual(tools.contract("Where you do not rush.")[0], "Where you don't rush.")


if __name__ == "__main__":
    unittest.main()
