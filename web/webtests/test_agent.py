import json
import os
import shutil
import sys
import tempfile
import unittest

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from pydantic_ai import ModelMessagesTypeAdapter  # noqa: E402
from pydantic_ai.messages import ModelRequest, ModelResponse, RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart  # noqa: E402
from pydantic_ai.models.function import AgentInfo, FunctionModel  # noqa: E402

from webapp import folder  # noqa: E402
from webapp import agent  # noqa: E402
from webapp.agent import tools  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
TODAY = "2026-10-28"
STEM = f"{TODAY}-strength-20"
BRIEF_ARGS = {"goal": "strength", "minutes": 20, "kit": None, "preset": "bodyweight",
              "equipment": None, "coach": "Coach Andy"}
QUESTION = {"id": "q1", "prompt": "Anything sore or off today?", "multi": True, "other": True,
            "options": [{"label": "Nothing new", "recommended": True},
                        {"label": "Sore somewhere else", "description": "say where"}]}


def parts(messages, kind):
    return [p for m in messages for p in m.parts if isinstance(p, kind)]


class AgentCase(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="hf-agent-")
        self.addCleanup(shutil.rmtree, self.home, True)
        folder.materialize(folder.seed(ROOT), self.home)
        self.deps = tools.Deps(engine_root=ROOT, home=self.home, keys={}, today=TODAY,
                               now=f"{TODAY} Wednesday 08:00")

    def menu_names(self):
        path = os.path.join(self.home, "workouts", STEM, f"{STEM}.menu.json")
        with open(path, encoding="utf-8") as f:
            return [m["name"] for m in json.load(f)["movements"]]


class Turns(AgentCase):
    def test_turn_asks_then_resumes(self):
        seen = {}

        def script(messages, info: AgentInfo):
            returned = parts(messages, ToolReturnPart)
            names = [p.tool_name for p in returned]
            if not names:
                return ModelResponse(parts=[ToolCallPart("get_coach", {}, tool_call_id="c1")])
            if names == ["get_coach"]:
                return ModelResponse(parts=[ToolCallPart("ask_user", {"questions": [QUESTION]},
                                                         tool_call_id="c2")])
            seen["answer"] = returned[-1].content
            return ModelResponse(parts=[TextPart("Thanks, planning now.")])

        model = FunctionModel(script)
        first = agent.run_turn(model, self.deps, None, "a 20-minute strength workout", None)
        self.assertIsNone(first.reply)
        self.assertEqual(first.question["tool_call_id"], "c2")
        self.assertEqual(first.question["questions"][0]["id"], "q1")
        self.assertIsNone(first.plan)

        second = agent.run_turn(model, self.deps, first.history_json, None,
                                ("c2", {"q1": ["Nothing new"]}))
        self.assertEqual(seen["answer"], {"q1": ["Nothing new"]})
        self.assertEqual(second.reply, "Thanks, planning now.")
        self.assertIsNone(second.question)
        self.assertIn("requests", second.usage)

    def test_two_asks_in_one_step_never_wedge(self):
        seen = {}

        def script(messages, info):
            returned = parts(messages, ToolReturnPart)
            if not returned:
                return ModelResponse(parts=[
                    ToolCallPart("ask_user", {"questions": [QUESTION]}, tool_call_id="a1"),
                    ToolCallPart("ask_user", {"questions": [dict(QUESTION, id="q2")]}, tool_call_id="a2")])
            seen.update({p.tool_call_id: p.content for p in returned})
            return ModelResponse(parts=[TextPart("ok")])

        model = FunctionModel(script)
        first = agent.run_turn(model, self.deps, None, "go", None)
        self.assertEqual(first.question["tool_call_id"], "a1")
        second = agent.run_turn(model, self.deps, first.history_json, None, ("a1", {"q1": ["Nothing new"]}))
        self.assertEqual(second.reply, "ok")
        self.assertEqual(seen["a1"], {"q1": ["Nothing new"]})
        self.assertEqual(seen["a2"], agent.NOT_SHOWN)
        third = agent.run_turn(model, self.deps, second.history_json, "and now?", None)
        self.assertEqual(third.reply, "ok")

    def test_a_new_line_closes_the_open_question(self):
        seen = {}

        def script(messages, info):
            returned = parts(messages, ToolReturnPart)
            if not returned:
                return ModelResponse(parts=[ToolCallPart("ask_user", {"questions": [QUESTION]}, tool_call_id="a1")])
            seen.update({p.tool_call_id: p.content for p in returned})
            return ModelResponse(parts=[TextPart("ok")])

        model = FunctionModel(script)
        first = agent.run_turn(model, self.deps, None, "go", None)
        second = agent.run_turn(model, self.deps, first.history_json, "actually, make it 30", None)
        self.assertEqual(second.reply, "ok")
        self.assertEqual(seen["a1"], agent.NOT_ANSWERED)
        with self.assertRaises(agent.TurnError) as caught:
            agent.run_turn(model, self.deps, second.history_json, None, ("a1", {"q1": ["Nothing new"]}))
        self.assertEqual(caught.exception.reason, agent.NOT_OPEN)

    def test_a_deferred_call_that_isnt_a_question_is_unfinishable(self):
        from types import SimpleNamespace
        from unittest import mock
        from pydantic_ai import DeferredToolRequests
        stopped = SimpleNamespace(output=DeferredToolRequests(calls=[ToolCallPart("brief", {}, tool_call_id="x1")]))
        with mock.patch.object(agent.AGENT, "run_sync", return_value=stopped):
            with self.assertRaises(agent.TurnError) as caught:
                agent.run_turn(FunctionModel(lambda m, i: None), self.deps, None, "go", None)
        self.assertEqual(caught.exception.reason, agent.UNFINISHABLE)

    def test_ask_user_refuses_a_bad_question(self):
        retries = []

        def script(messages, info):
            retried = parts(messages, RetryPromptPart)
            if not retried:
                bad = dict(QUESTION, options=[{"label": "Only one", "recommended": True}])
                return ModelResponse(parts=[ToolCallPart("ask_user", {"questions": [bad]}, tool_call_id="c1")])
            retries.extend(retried)
            return ModelResponse(parts=[TextPart("ok")])

        out = agent.run_turn(FunctionModel(script), self.deps, None, "go", None)
        self.assertEqual(out.reply, "ok")
        self.assertIsNone(out.question)
        self.assertTrue(retries)

    def test_ask_user_takes_one_to_four(self):
        for questions in ([], [dict(QUESTION, id=f"q{n}") for n in range(5)]):
            with self.subTest(n=len(questions)):
                retried = []

                def script(messages, info):
                    found = parts(messages, RetryPromptPart)
                    if not found:
                        return ModelResponse(parts=[ToolCallPart("ask_user", {"questions": questions},
                                                                 tool_call_id="c1")])
                    retried.extend(found)
                    return ModelResponse(parts=[TextPart("ok")])

                out = agent.run_turn(FunctionModel(script), self.deps, None, "go", None)
                self.assertIsNone(out.question)
                self.assertTrue(retried)

    def test_history_roundtrip(self):
        def script(messages, info):
            names = [p.tool_name for p in parts(messages, ToolReturnPart)]
            if not names:
                return ModelResponse(parts=[ToolCallPart("check", {}, tool_call_id="c1"),
                                            ToolCallPart("read_file", {"name": "profile.md"}, tool_call_id="c2")])
            return ModelResponse(parts=[ToolCallPart("ask_user", {"questions": [QUESTION]}, tool_call_id="c3")])

        out = agent.run_turn(FunctionModel(script), self.deps, None, "workout", None)
        self.assertIsInstance(out.history_json, str)
        history = ModelMessagesTypeAdapter.validate_json(out.history_json)
        calls = [p.tool_name for p in parts(history, ToolCallPart)]
        self.assertEqual(calls, ["check", "read_file", "ask_user"])
        self.assertTrue(any(isinstance(m, ModelRequest) for m in history))


class ShowPlan(AgentCase):
    def plan(self, movements, seconds=(300, 600, 300), total=1200):
        rows = [{"block": b, "movements": movements, "dose": "3 x 10", "seconds": s}
                for b, s in zip(("Warm-up", "Main", "Cool-down"), seconds)]
        return {"plan": {"format": "Straight sets", "equipment": "bodyweight", "rows": rows,
                         "left_out": "nothing", "total_seconds": total}}

    def test_show_plan_needs_brief(self):
        retries = []

        def script(messages, info):
            retried = parts(messages, RetryPromptPart)
            if not retried:
                return ModelResponse(parts=[ToolCallPart("show_plan", self.plan(["squat"]), tool_call_id="c1")])
            retries.extend(r.content for r in retried)
            return ModelResponse(parts=[TextPart("ok")])

        out = agent.run_turn(FunctionModel(script), self.deps, None, "go", None)
        self.assertIn("run brief first", str(retries))
        self.assertIsNone(out.plan)
        self.assertIsNone(self.deps.plan)

    def test_show_plan_refuses_off_menu(self):
        retries = []
        good = {}

        def script(messages, info):
            names = [p.tool_name for p in parts(messages, ToolReturnPart)]
            retried = parts(messages, RetryPromptPart)
            if not names:
                return ModelResponse(parts=[ToolCallPart("brief", BRIEF_ARGS, tool_call_id="c1")])
            if names == ["brief"] and not retried:
                menu = self.menu_names()
                good["names"] = menu[:2]
                return ModelResponse(parts=[ToolCallPart(
                    "show_plan", self.plan([menu[0], "Barbell Back Squat Off The Moon"]), tool_call_id="c2")])
            if len(retried) == 1:
                retries.append(retried[0].content)
                return ModelResponse(parts=[ToolCallPart(
                    "show_plan", self.plan(good["names"], seconds=(300, 600, 200)), tool_call_id="c3")])
            if len(retried) == 2 and "show_plan" not in names:
                retries.append(retried[1].content)
                return ModelResponse(parts=[ToolCallPart(
                    "show_plan", self.plan(good["names"]), tool_call_id="c4")])
            return ModelResponse(parts=[TextPart("The plan is ready.\nThe script and audio come later.")])

        out = agent.run_turn(FunctionModel(script), self.deps, None, "go", None)
        self.assertIn("Barbell Back Squat Off The Moon", str(retries[0]))
        self.assertIn("1100", str(retries[1]))
        self.assertEqual(out.stem, STEM)
        self.assertEqual(out.plan["rows"][1]["movements"], good["names"])
        self.assertEqual(out.plan["total_seconds"], 1200)
        self.assertEqual(out.reply.splitlines()[0], "The plan is ready.")

    def test_show_plan_refuses_wrong_total(self):
        self.assertEqual(tools.brief(self.deps, **BRIEF_ARGS).code, 0)
        names = self.menu_names()[:1]
        problems = agent.plan_problems(self.deps, agent.Plan(**self.plan(names, (300, 300, 300), 900)["plan"]))
        self.assertTrue(any("1200" in p for p in problems), problems)
        self.assertEqual(agent.plan_problems(self.deps, agent.Plan(**self.plan(names)["plan"])), [])


class Sides(AgentCase):
    def test_one_sided_movement_needs_its_side(self):
        r = tools.brief(self.deps, **dict(BRIEF_ARGS, limits=["knee=off-limits:left"]))
        self.assertEqual(r.code, 0, r.error)
        with open(os.path.join(self.home, "workouts", STEM, f"{STEM}.menu.json"), encoding="utf-8") as f:
            entry = next(e for e in json.load(f)["movements"] if e.get("side") == "right")
        name = entry["name"]

        def problems(movement):
            rows = [{"block": "Main", "movements": [movement], "dose": "3 x 10", "seconds": 1200}]
            return agent.plan_problems(self.deps, agent.Plan(format="Sets", equipment="none", rows=rows,
                                                             left_out="", total_seconds=1200))
        self.assertEqual(problems(f"right {name}"), [])
        self.assertTrue(any("left" in p for p in problems(f"left {name}")), problems(f"left {name}"))
        self.assertTrue(any("right side only" in p for p in problems(name)), problems(name))
        self.assertTrue(problems(f"both sides {name}"))


    def test_one_sided_movement_in_words(self):
        r = tools.brief(self.deps, **dict(BRIEF_ARGS, limits=["knee=delicate:left"]))
        self.assertEqual(r.code, 0, r.error)
        with open(os.path.join(self.home, "workouts", STEM, f"{STEM}.menu.json"), encoding="utf-8") as f:
            menu = json.load(f)["movements"]
        entry = next(e for e in menu if e.get("side") == "right")
        name = entry["name"]
        both = next(e["name"] for e in menu if "side" not in e)

        def problems(movement, dose, block="Main", left_out=""):
            rows = [{"block": block, "movements": [movement], "dose": dose, "seconds": 1200}]
            return agent.plan_problems(self.deps, agent.Plan(format="Sets", equipment="none", rows=rows,
                                                             left_out=left_out, total_seconds=1200))
        for dose in ("3 x 10 each side", f"3 x 10, then left {name}", f"3 x 10, then {name} on both legs",
                     "3 x 10 per-side", "3 x 10, Alternating", "3 x 10, left and right", "3 x 10 each leg"):
            with self.subTest(dose=dose):
                p = problems(f"right {name}", dose)
                self.assertTrue(p, dose)
                self.assertTrue(any(name in x and "right side only" in x for x in p), p)
        self.assertTrue(problems(f"right {name}", "3 x 10", block="Main, both sides"))
        # a mention of the one-sided movement elsewhere in the plan is side-checked too
        self.assertTrue(problems(both, "3 x 10", left_out=f"{name} on the left side"))
        self.assertEqual(problems(f"right {name}", "3 x 10, right side only"), [])
        self.assertEqual(problems(both, "3 x 10 each side"), [])


class Rebrief(AgentCase):
    def plan(self, movements=("squat",)):
        rows = [{"block": "Main", "movements": list(movements), "dose": "3 x 10", "seconds": 1200}]
        return agent.Plan(format="Sets", equipment="none", rows=rows, left_out="", total_seconds=1200)

    def test_refused_brief_drops_the_older_menu(self):
        self.assertEqual(tools.brief(self.deps, **BRIEF_ARGS).code, 0)
        self.deps.plan = {"shown": True}
        self.assertEqual(tools.brief(self.deps, **dict(BRIEF_ARGS, goal="nap")).code, 64)
        self.assertIsNone(self.deps.stem)
        self.assertIsNone(self.deps.plan)
        self.assertEqual(agent.plan_problems(self.deps, self.plan()), ["run brief first"])

    def test_failed_engine_brief_drops_the_older_menu(self):
        self.assertEqual(tools.brief(self.deps, **BRIEF_ARGS).code, 0)
        self.deps.plan = {"shown": True}
        r = tools.brief(self.deps, **dict(BRIEF_ARGS, kit="no-such-kit", preset=None))
        self.assertNotEqual(r.code, 0)
        self.assertNotEqual(r.code, 64 if not r.error else -1)   # the engine ran and said why
        self.assertIsNone(self.deps.stem)
        self.assertIsNone(self.deps.plan)
        self.assertEqual(agent.plan_problems(self.deps, self.plan()), ["run brief first"])

    def test_unreadable_menu_is_a_problem_not_a_crash(self):
        self.assertEqual(tools.brief(self.deps, **BRIEF_ARGS).code, 0)
        path = os.path.join(self.home, "workouts", STEM, f"{STEM}.menu.json")
        os.remove(path)
        os.mkdir(path)   # reading a folder is an OSError
        rows = [{"block": "Main", "movements": ["squat"], "dose": "3 x 10", "seconds": 1200}]
        plan = agent.Plan(format="Sets", equipment="none", rows=rows, left_out="", total_seconds=1200)
        self.assertIn("run brief again", agent.plan_problems(self.deps, plan)[0])
        with open(os.path.join(self.home, "health.md"), "a", encoding="utf-8") as f:
            f.write("\nchanged\n")
        os.rmdir(path)
        self.assertEqual(tools.brief(self.deps, **BRIEF_ARGS).code, 0)
        with open(os.path.join(self.home, "health.md"), "a", encoding="utf-8") as f:
            f.write("\nchanged again\n")
        stale = agent.plan_problems(self.deps, plan)
        self.assertIn("health.md changed", stale[0])


class TextScan(AgentCase):
    """Every free-text field of the plan is scanned for movements, as the build scans a draft's text."""

    def setUp(self):
        super().setUp()
        r = tools.brief(self.deps, **dict(BRIEF_ARGS, limits=["knee=off-limits"]))
        self.assertEqual(r.code, 0, r.error)
        with open(os.path.join(self.home, "workouts", STEM, f"{STEM}.menu.json"), encoding="utf-8") as f:
            self.menu = json.load(f)["movements"]
        ids = {e["id"] for e in self.menu}
        self.assertNotIn("jump-squat", ids)
        self.assertNotIn("box-jump", ids)
        self.ok = next(e["name"] for e in self.menu if "side" not in e)
        self.other = next(e["name"] for e in self.menu if "side" not in e and e["name"] != self.ok)

    def problems(self, block="Main", dose="3 x 10", left_out="", fmt="circuit", equipment="bodyweight"):
        rows = [{"block": block, "movements": [self.ok], "dose": dose, "seconds": 1200}]
        return agent.plan_problems(self.deps, agent.Plan(format=fmt, equipment=equipment, rows=rows,
                                                         left_out=left_out, total_seconds=1200))

    def test_reviewers_case_is_refused(self):
        p = self.problems(block="Finisher: jump squats", dose="3 x 10, then 20 jump squats and box jumps")
        self.assertTrue(any("jump squats" in x for x in p), p)
        self.assertTrue(any("box jumps" in x for x in p), p)

    def test_every_field_is_scanned(self):
        for field in ("block", "dose", "fmt", "equipment", "left_out"):
            with self.subTest(field=field):
                p = self.problems(**{field: "then burpees and box jumps"})
                self.assertTrue(any("box jumps" in x for x in p), p)

    def test_menu_movements_in_the_dose_are_fine(self):
        self.assertEqual(self.problems(dose=f"3 x 10, then 10 {self.other}"), [])

    def test_left_out_may_name_movements_negated(self):
        self.assertEqual(self.problems(left_out="no jumping today"), [])
        self.assertEqual(self.problems(left_out="no jump squats, no box jumps: your knee"), [])
        p = self.problems(left_out="jump squats, for your knee")
        self.assertTrue(any("jump squats" in x for x in p), p)


class Race(AgentCase):
    """brief and show_plan in one model response never run together, and a plan checked against the menu
    from before today's tighter limit is never kept."""

    def test_show_plan_and_brief_in_one_response(self):
        self.assertEqual(tools.brief(self.deps, **BRIEF_ARGS).code, 0)
        old = self.deps.stem
        with open(os.path.join(self.home, "workouts", old, f"{old}.menu.json"), encoding="utf-8") as f:
            before = {e["id"]: e["name"] for e in json.load(f)["movements"]}
        probe = tools.Deps(engine_root=ROOT, home=self.home, keys={}, today=TODAY, now=self.deps.now)
        self.assertEqual(tools.brief(probe, **dict(BRIEF_ARGS, limits=["knee=off-limits"])).code, 0)
        with open(os.path.join(self.home, "workouts", probe.stem, f"{probe.stem}.menu.json"), encoding="utf-8") as f:
            after = {e["id"] for e in json.load(f)["movements"]}
        shutil.rmtree(os.path.join(self.home, "workouts", probe.stem))
        gone = sorted(set(before) - after)
        self.assertTrue(gone)
        bad = before[gone[0]]   # on today's menu until the knee is off-limits
        plan = {"format": "circuit", "equipment": "bodyweight", "left_out": "", "total_seconds": 1200,
                "rows": [{"block": "Main", "movements": [bad], "dose": "3x10", "seconds": 1200}]}
        knee = dict(BRIEF_ARGS, limits=["knee=off-limits"])
        for order in (("show_plan", "brief"), ("brief", "show_plan")):
            with self.subTest(order=order):
                self.deps.stem, self.deps.plan = old, None

                def script(messages, info):
                    if not parts(messages, (ToolReturnPart, RetryPromptPart)):
                        calls = {"show_plan": ToolCallPart("show_plan", {"plan": plan}, tool_call_id="a"),
                                 "brief": ToolCallPart("brief", knee, tool_call_id="b")}
                        return ModelResponse(parts=[calls[n] for n in order])
                    return ModelResponse(parts=[TextPart("done")])

                out = agent.run_turn(FunctionModel(script), self.deps, None, "my knee hurts today", None)
                self.assertNotEqual(out.stem, old)
                with open(os.path.join(self.home, "workouts", out.stem, f"{out.stem}.menu.json"),
                          encoding="utf-8") as f:
                    self.assertNotIn(gone[0], {e["id"] for e in json.load(f)["movements"]})
                self.assertIsNone(out.plan)


class Instructions(unittest.TestCase):
    def test_instructions_cover_the_check_in(self):
        with open(os.path.join(os.path.dirname(agent.__file__), "instructions.md"), encoding="utf-8") as f:
            text = f.read()
        for tool in ("read_file", "check", "get_coach", "get_route", "coaches", "content_plan",
                     "coverage", "brief", "ask_user", "show_plan"):
            self.assertIn(f"`{tool}`", text)
        for slot in ("Limits", "Readiness", "Goal", "Length", "Kit", "Coach"):
            self.assertIn(f"| {slot} |", text)
        self.assertIn("red flag", text.lower())
        self.assertIn("stop", text.lower())
        self.assertNotIn("./harmonicfitness", text)
        self.assertIn("Never ask the listener for a key or a password", text)
        for later in ("privacy line", "new coach", "too long", "one side only"):
            self.assertIn(later, text)

    def test_every_tool_is_registered(self):
        names = set(agent.AGENT._function_toolset.tools)
        self.assertEqual(names, {"read_file", "check", "get_coach", "get_route", "coaches", "content_plan",
                                 "coverage", "brief", "ask_user", "show_plan"})


if __name__ == "__main__":
    unittest.main()
