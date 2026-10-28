import os
import shutil
import sys
import tempfile
import unittest

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from pydantic_ai import ModelMessagesTypeAdapter  # noqa: E402
from pydantic_ai.messages import (ModelRequest, ModelResponse, TextPart, ToolCallPart,  # noqa: E402
                                  ToolReturnPart, UserPromptPart)
from pydantic_ai.models.function import FunctionModel  # noqa: E402

from webapp import folder  # noqa: E402
from webapp import agent  # noqa: E402
from webapp.agent import tools  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
TODAY = "2026-10-28"
STEM = f"{TODAY}-strength-20"


def parts(messages, kind):
    return [p for m in messages for p in m.parts if isinstance(p, kind)]


class AgentCase(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="hf-agent-")
        self.addCleanup(shutil.rmtree, self.home, True)
        folder.materialize(folder.seed(ROOT), self.home)
        self.deps = tools.Deps(engine_root=ROOT, home=self.home, keys={}, today=TODAY,
                               now=f"{TODAY} Wednesday 08:00")


class Run(AgentCase):
    def test_runs_the_engine_with_me_paths(self):
        draft = f"me/workouts/{STEM}/{STEM}.draft.txt"
        r = tools.run(self.deps, ["brief", "--goal", "strength", "--minutes", "20", "--preset", "bodyweight",
                                  "--today", TODAY, "--save", draft])
        self.assertEqual(r.code, 0, r.error)
        self.assertTrue(os.path.isfile(os.path.join(self.home, "workouts", STEM, f"{STEM}.menu.json")))
        self.assertNotIn(self.home, r.output + r.error)
        self.assertNotIn(os.path.realpath(self.home), r.output + r.error)

    def test_leading_wrapper_is_forgiven(self):
        self.assertIn(tools.run(self.deps, ["./harmonicfitness", "check"]).code, (0, 1))

    def test_refuses_what_the_web_cant_do(self):
        for args in (["setup"], ["keys", "init", "fish"], ["keys", "open"], ["migrate"], ["backup"],
                     ["coaches", "audition", "x.md"], ["coaches", "make"], ["cache", "prune"],
                     ["build", "me/workouts/a/a.draft.txt", "A"], [], ["rm", "-rf"]):
            r = tools.run(self.deps, args)
            self.assertEqual(r.code, 64, args)

    def test_build_lint_only_is_allowed(self):
        r = tools.run(self.deps, ["build", "me/workouts/none/none.draft.txt", "None", "--lint-only"])
        self.assertNotIn("can't make the audio", r.error)

    def test_paths_stay_in_the_folder(self):
        for bad in ("me/../../etc/passwd", "/etc/passwd", "../tools/paths.py", "--save=/tmp/x",
                    "--save=me/../x", "me/.env"):
            r = tools.run(self.deps, ["brief", "--save", bad])
            self.assertEqual(r.code, 64, bad)


class Files(AgentCase):
    def test_read_mine_and_the_engines(self):
        self.assertIn("+++", tools.read_file(self.deps, "me/profile.md").output)
        self.assertEqual(tools.read_file(self.deps, "knowledge/script.md").code, 0)
        self.assertEqual(tools.read_file(self.deps, ".claude/skills/workout/SKILL.md").code, 0)
        self.assertEqual(tools.read_file(self.deps, "me/nothing.md").code, 1)

    def test_read_refuses_the_rest(self):
        with open(os.path.join(self.home, ".env"), "w") as f:
            f.write("FISH_AUDIO_API_KEY=secret-value-here\n")
        for bad in ("me/.env", "tools/paths.py", "CLAUDE.md", "knowledge/../tools/paths.py", "me/../x",
                    "/etc/passwd", "web/webapp/config.py"):
            r = tools.read_file(self.deps, bad)
            self.assertEqual(r.code, 64, bad)
            self.assertNotIn("secret-value-here", r.output + r.error)

    def test_read_refuses_a_symlink_out(self):
        os.symlink("/etc/hosts", os.path.join(self.home, "out.md"))
        self.assertEqual(tools.read_file(self.deps, "me/out.md").code, 64)

    def test_write_and_list(self):
        r = tools.write_file(self.deps, f"me/workouts/{STEM}/{STEM}.draft.txt", "movements: none\n")
        self.assertEqual(r.code, 0, r.error)
        listing = tools.list_files(self.deps, "me/workouts").output
        self.assertIn(f"me/workouts/{STEM}/{STEM}.draft.txt", listing)
        self.assertIn("me/profile.md", tools.list_files(self.deps).output)

    def test_write_refuses(self):
        for bad in ("me/health.md", "me/.env", "me/a.mp3", "tools/x.py", "me/../x.md", "knowledge/x.md", "me/"):
            self.assertEqual(tools.write_file(self.deps, bad, "x").code, 64, bad)
        self.assertEqual(tools.write_file(self.deps, "me/big.md", "x" * (tools.WRITE_LIMIT + 1)).code, 64)

    def test_list_hides_skipped_files(self):
        with open(os.path.join(self.home, ".env"), "w") as f:
            f.write("X=1\n")
        self.assertNotIn(".env", tools.list_files(self.deps).output)


class Turns(AgentCase):
    def test_a_turn_reads_then_replies(self):
        def script(messages, info):
            if not parts(messages, ToolReturnPart):
                return ModelResponse(parts=[ToolCallPart("read_file", {"path": "me/profile.md"}, tool_call_id="c1")])
            return ModelResponse(parts=[TextPart("1. How long? a) 25 min (recommended) b) 40 min")])

        out = agent.run_turn(FunctionModel(script), self.deps, None, "a workout please")
        self.assertIn("How long", out.reply)
        self.assertIsNone(out.question)
        history = ModelMessagesTypeAdapter.validate_json(out.history_json)
        self.assertEqual([p.tool_name for p in parts(history, ToolCallPart)], ["read_file"])

        def second(messages, info):
            said = [p.content for p in parts(messages, UserPromptPart)]
            return ModelResponse(parts=[TextPart(f"got {said[-1]}")])

        out2 = agent.run_turn(FunctionModel(second), self.deps, out.history_json, "1a")
        self.assertEqual(out2.reply, "got 1a")

    def test_an_answer_is_not_open(self):
        with self.assertRaises(agent.TurnError) as e:
            agent.run_turn(FunctionModel(lambda m, i: ModelResponse(parts=[TextPart("x")])), self.deps, None,
                           None, ("c1", {"q": ["a"]}))
        self.assertEqual(e.exception.reason, agent.NOT_OPEN)

    def test_a_dangling_call_starts_the_model_fresh(self):
        old = [ModelRequest(parts=[UserPromptPart("hi")]),
               ModelResponse(parts=[ToolCallPart("ask_user", {"questions": []}, tool_call_id="old")])]
        history_json = ModelMessagesTypeAdapter.dump_json(old).decode()
        seen = []

        def script(messages, info):
            seen.append(len(messages))
            return ModelResponse(parts=[TextPart("fresh")])

        out = agent.run_turn(FunctionModel(script), self.deps, history_json, "carry on")
        self.assertEqual((out.reply, seen), ("fresh", [1]))


class Instructions(AgentCase):
    def test_instructions_hold_the_skill_and_the_web_rules(self):
        seen = {}

        def script(messages, info):
            seen["text"] = "\n".join(m.instructions or "" for m in messages if isinstance(m, ModelRequest))
            return ModelResponse(parts=[TextPart("ok")])

        agent.run_turn(FunctionModel(script), self.deps, None, "hi")
        text = seen["text"]
        with open(os.path.join(ROOT, ".claude/skills/workout/SKILL.md"), encoding="utf-8") as f:
            self.assertIn(f.read()[-300:].strip(), text)   # the whole skill, to its last line
        self.assertIn(".claude/skills/workout/SKILL.md", text)
        self.assertIn(".claude/skills/workout/research.md", text)
        self.assertIn("Never ask the listener for a key or a password", text)
        self.assertIn("--lint-only", text)
        self.assertIn("one side only", text)
        self.assertIn(f"today is {TODAY}", text)

    def test_every_tool_is_registered(self):
        self.assertEqual(set(agent.AGENT._function_toolset.tools), {"run", "read_file", "write_file", "list_files"})


if __name__ == "__main__":
    unittest.main()
