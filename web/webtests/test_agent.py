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

    def test_every_tool_is_registered(self):
        names = set(agent.AGENT._function_toolset.tools)
        self.assertEqual(names, {"read_file", "check", "get_coach", "get_route", "coaches", "content_plan",
                                 "coverage", "brief", "ask_user", "show_plan"})


if __name__ == "__main__":
    unittest.main()
