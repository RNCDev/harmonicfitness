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
                     ["coaches", "audition", "me/coaches/.auditions/d.md", "--play"], ["coaches", "set"],
                     ["coaches", "download"], ["coaches", "make"], ["cache", "prune"],
                     ["build", "me/workouts/a/a.draft.txt", "A", "--follow"], [], ["rm", "-rf"]):
            r = tools.run(self.deps, args)
            self.assertEqual(r.code, 64, args)

    def fake_engine(self, speaks=3000, lint=0):
        from unittest import mock
        calls = []

        def run(root, home, argv, extra_env={}, timeout=120, cancel=None):
            calls.append((argv, timeout))
            if argv[:2] == ["get", "cost"]:
                return tools.engine.Result(0, '{"service": "fish", "chars": %d, "usd": 0.045, "pending_design": '
                                              'true, "design_usd": 0.01}' % speaks, "")
            if "--max-chars" in argv and argv[argv.index("--max-chars") + 1] == "1":
                return tools.engine.Result(64, f"  the script speaks {speaks:,} characters; this build may send at most 1", "")
            if "--lint-only" in argv:
                return tools.engine.Result(lint, "lint ok" if lint == 0 else "a line is too long", "")
            return tools.engine.Result(0, "recorded", "")
        return mock.patch.object(tools.engine, "run", side_effect=run), calls

    BUILD = ["build", "me/workouts/a/a.draft.txt", "Workout A", "--coach", "Coach Reed"]

    def test_a_full_build_is_priced_and_offered_first(self):
        patch, calls = self.fake_engine()
        with patch:
            r = tools.run(self.deps, list(self.BUILD))
        self.assertIn("Not recorded yet", r.output)
        self.assertIn("$0.06", r.output)   # the voice design included
        self.assertEqual(self.deps.offer, {"draft": "me/workouts/a/a.draft.txt", "name": "Workout A",
                                           "coach": "Coach Reed", "chars": 3000, "usd": 0.055, "service": "fish",
                                           "design": True})
        self.assertFalse(any("--lint-only" not in a and a[0] == "build" for a, _ in calls))   # nothing recorded

    def test_a_lint_problem_is_fixed_before_any_price(self):
        patch, calls = self.fake_engine(lint=1)
        with patch:
            r = tools.run(self.deps, list(self.BUILD))
        self.assertEqual(r.code, 1)
        self.assertIsNone(self.deps.offer)
        self.assertEqual(len(calls), 1)

    def test_over_todays_allowance_is_refused(self):
        self.deps.chars_left = 1000
        patch, _ = self.fake_engine()
        with patch:
            r = tools.run(self.deps, list(self.BUILD))
        self.assertEqual(r.code, 64)
        self.assertIn("today's allowance", r.error)
        self.assertIsNone(self.deps.offer)

    def test_an_approved_build_records_within_its_price(self):
        self.deps.approved = {"draft": "me/workouts/a/a.draft.txt", "coach": "Coach Reed", "chars": 3000}
        patch, calls = self.fake_engine()
        with patch:
            r = tools.run(self.deps, list(self.BUILD))
        self.assertEqual(r.output, "recorded")
        argv, timeout = calls[-1]
        self.assertEqual((argv[-2:], timeout), (["--max-chars", "3000"], tools.BUILD_TIMEOUT))

    def test_an_approval_is_for_its_own_draft_and_coach(self):
        self.deps.approved = {"draft": "me/workouts/a/a.draft.txt", "coach": "Coach Ellis", "chars": 3000}
        patch, calls = self.fake_engine()
        with patch:
            r = tools.run(self.deps, list(self.BUILD))
        self.assertIn("Not recorded yet", r.output)

    def test_a_build_needs_its_coach(self):
        self.assertEqual(tools.run(self.deps, ["build", "me/workouts/a/a.draft.txt", "A"]).code, 64)

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
        for bad in ("me/.env", "me/a.mp3", "tools/x.py", "me/../x.md", "knowledge/x.md", "me/"):
            self.assertEqual(tools.write_file(self.deps, bad, "x").code, 64, bad)
        self.assertEqual(tools.write_file(self.deps, "me/big.md", "x" * (tools.WRITE_LIMIT + 1)).code, 64)

    def test_the_check_in_may_change_health(self):
        self.assertEqual(tools.write_file(self.deps, "me/health.md", "+++\nschema = 6\n+++\n").code, 0)

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

    def test_every_tool_call_is_a_step(self):
        said = []
        self.deps.say = lambda text, tool, code, step: said.append((text, tool, code, step))

        def script(messages, info):
            if not parts(messages, ToolReturnPart):
                return ModelResponse(parts=[ToolCallPart("read_file", {"path": "me/profile.md"}, tool_call_id="c1"),
                                            ToolCallPart("run", {"args": ["setup"]}, tool_call_id="c2")])
            return ModelResponse(parts=[TextPart("done")])

        agent.run_turn(FunctionModel(script), self.deps, None, "go")
        # each step is said as its tool starts (code None), then under the same id as it ends
        self.assertEqual(said, [("Getting to know you", "read_file", None, 1), ("Getting to know you", "read_file", 0, 1),
                                ("Working on it", "run setup", None, 2), ("Working on it", "run setup", 64, 2)])

    def test_a_failed_check_makes_the_next_draft_a_fix(self):
        from unittest import mock
        said = []
        self.deps.say = lambda text, tool, code, step: said.append(text) if code is None else None
        draft = f"me/workouts/{STEM}/{STEM}.draft.txt"
        codes = iter([1, 0])

        def run(root, home, argv, extra_env={}, timeout=120, cancel=None):
            return tools.engine.Result(next(codes), "", "")

        def script(messages, info):
            n = len(parts(messages, ToolReturnPart))
            calls = [ToolCallPart("write_file", {"path": draft, "content": "x"}, tool_call_id="w1"),
                     ToolCallPart("run", {"args": ["build", draft, "W", "--coach", "Coach Nolan", "--lint-only"]},
                                  tool_call_id="b1"),
                     ToolCallPart("write_file", {"path": draft, "content": "y"}, tool_call_id="w2"),
                     ToolCallPart("run", {"args": ["build", draft, "W", "--coach", "Coach Nolan", "--lint-only"]},
                                  tool_call_id="b2")]
            return ModelResponse(parts=[calls[n]] if n < len(calls) else [TextPart("done")])
        with mock.patch.object(tools.engine, "run", side_effect=run):
            agent.run_turn(FunctionModel(script), self.deps, None, "go")
        self.assertEqual(said, ["Writing your script", "Checking the script's safety and timing",
                                "Tightening the script's timing", "Checking the script again"])

    def test_a_recording_says_so_while_it_runs_and_designs_the_coach_first(self):
        import time
        from unittest import mock
        said = []
        self.deps.say = lambda text, tool, code, step: said.append((text, code, step))
        draft = f"me/workouts/{STEM}/{STEM}.draft.txt"
        self.deps.approved = {"draft": draft, "name": "W", "coach": "Coach Nolan", "chars": 2000, "usd": 0.04,
                              "service": "gemini", "design": True}

        def run(root, home, argv, extra_env={}, timeout=120, cancel=None):
            os.makedirs(os.path.join(home, "coaches", "coach-nolan-gemini"))   # the design is saved
            time.sleep(1.6)   # the watch sees it, then the recording runs
            return tools.engine.Result(0, "recorded", "")

        def script(messages, info):
            if not parts(messages, ToolReturnPart):
                return ModelResponse(parts=[ToolCallPart("run", {"args": ["build", draft, "W", "--coach", "Coach Nolan"]},
                                                         tool_call_id="r1")])
            return ModelResponse(parts=[TextPart("ready")])
        with mock.patch.object(tools.engine, "run", side_effect=run):
            agent.run_turn(FunctionModel(script), self.deps, None, "Yes, record it.")
        self.assertEqual(said, [("Designing Coach Nolan's voice", None, 1), ("Designing Coach Nolan's voice", 0, 1),
                                ("Recording your workout", None, 2), ("Recording your workout", 0, 2)])

    def test_steps_never_name_a_file(self):
        for path in ("me/profile.md", "me/health.md", "me/content.md", "knowledge/script.md", "me/x/y.txt", 42):
            self.assertNotIn("/", agent._read_step(path))
            self.assertNotIn(".md", agent._read_step(path))
        self.assertEqual(agent._read_step("me/health.md"), "Checking today's safety limits")
        self.assertEqual(agent._write_step("me/workouts/a/a.draft.txt"), "Writing your script")

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


class Prefetch(AgentCase):
    def test_step_one_comes_with_the_first_message(self):
        said = []
        self.deps.say = lambda text, tool, code, step: said.append(text)
        context = agent.prefetch(self.deps)
        for title in ("./harmonicfitness check", "./harmonicfitness content plan --minutes 25",
                      "./harmonicfitness get coach", "./harmonicfitness coaches list", "read me/profile.md",
                      "read me/training.md", "read me/health.md", "read me/log.md"):
            self.assertIn(f"### {title} (exit ", context)
        self.assertNotIn(self.home, context)
        self.assertEqual(said, ["Getting to know you and today's limits"] * 2)   # started, then done
        seen = {}

        def script(messages, info):
            seen["prompt"] = parts(messages, UserPromptPart)[-1].content
            return ModelResponse(parts=[TextPart("1. How long?")])

        agent.run_turn(FunctionModel(script), self.deps, None, "stretch please", context=context)
        self.assertTrue(seen["prompt"].startswith("Step 1 is done"))
        self.assertTrue(seen["prompt"].endswith("The listener says:\n\nstretch please"))

    def test_a_new_listener_is_asked_setup_and_check_in_together(self):
        self.deps.setup = True
        self.assertTrue(agent.prefetch(self.deps).startswith("This listener isn't set up yet"))
        self.deps.setup = False
        self.assertTrue(agent.prefetch(self.deps).startswith("Step 1 is done"))
        path = os.path.join(self.home, "profile.md")   # set up, and asking to change the profile
        with open(path, encoding="utf-8") as f:
            text = f.read()
        with open(path, "w", encoding="utf-8") as f:
            f.write(text.replace('experience = ""', 'experience = "novice"', 1))
        self.deps.setup = True
        self.assertTrue(agent.prefetch(self.deps).startswith("Step 1 is done"))

    def test_only_coaches_that_can_speak_are_offered(self):
        self.deps.keys = {"GEMINI_API_KEY": "AIzaabc123def456abcd"}
        context = agent.prefetch(self.deps)
        block = context.split("### ./harmonicfitness coaches list (exit 0)", 1)[1].split("###", 1)[0]
        offered = block.split("Coaches who can speak here (offer only these): ", 1)[1].split("\n", 1)[0]
        self.assertIn("Coach Nolan", offered)
        for other in ("Coach Reed", "Coach Ellis", "Coach Owen", "Coach Andy", "Coach Maya"):
            self.assertNotIn(other, offered)
        self.assertIn("Coach Reed (Fish Audio)", block)   # named only as needing a key
        self.assertIn("add a key in Settings for more voices", block)
        self.assertNotIn('"speaks_here"', context)

    def test_feeds_waits_for_the_background_run(self):
        from concurrent.futures import Future
        done = Future()
        done.set_result(tools.ToolResult(code=0, output="sunny"))
        self.deps.feeds = done
        self.assertEqual(tools.run(self.deps, ["feeds"]).output, "sunny")

    def test_a_failed_background_feeds_runs_again(self):
        from concurrent.futures import Future
        from unittest import mock
        failed = Future()
        failed.set_exception(RuntimeError("network"))
        self.deps.feeds = failed
        with mock.patch.object(tools.engine, "run", return_value=tools.engine.Result(0, "cloudy", "")) as run:
            self.assertEqual(tools.run(self.deps, ["feeds"]).output, "cloudy")
        self.assertEqual(run.call_args.args[2], ["feeds"])


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
        self.assertIn("kept 24 hours", text)
        self.assertIn("one side only", text)
        self.assertIn(f"today is {TODAY}", text)

    def test_the_web_wording_names_no_key_file(self):
        with open(os.path.join(ROOT, "web/webapp/agent/instructions.md"), encoding="utf-8") as f:
            lines = [line for line in f if ".env" in line]
        self.assertEqual(len(lines), 1)   # only the rule never to read or write it
        self.assertIn("Never read or write `me/.env`", lines[0])
        self.assertIn("stored encrypted on this site", agent.PREAMBLE)

    def test_a_new_listener_gets_the_setup_skill(self):
        self.assertTrue(agent.needs_setup(self.home))   # the starter profile: no experience yet
        self.assertIn(".claude/skills/setup/SKILL.md", agent.skill_text(ROOT, True))
        self.assertNotIn(".claude/skills/setup/SKILL.md", agent.skill_text(ROOT, False))
        path = os.path.join(self.home, "profile.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        with open(path, "w", encoding="utf-8") as f:
            f.write(text.replace('experience = ""', 'experience = "novice"', 1))
        self.assertFalse(agent.needs_setup(self.home))
        self.assertTrue(agent.wants_setup("Finish setting me up"))
        self.assertFalse(agent.wants_setup("a 20 minute workout"))

    def test_a_coach_of_their_own_can_be_made_here(self):
        from unittest import mock
        calls = []

        def run(root, home, argv, extra_env={}, timeout=120, cancel=None):
            calls.append((argv, timeout))
            return tools.engine.Result(0, "done", "")
        with mock.patch.object(tools.engine, "run", side_effect=run):
            for args in (["coaches", "make", "Coach Reed"], ["coaches", "audition", "me/coaches/.auditions/d.md"],
                         ["coaches", "keep", "2026-10-28-1/B", "--name", "Coach Dana"],
                         ["coaches", "forget-audition", "2026-10-28-1"], ["coaches", "archive", "Coach Dana"]):
                self.assertEqual(tools.run(self.deps, args).code, 0, args)
            # one audition a turn: each is paid for, and the listener hears the first before another
            again = tools.run(self.deps, ["coaches", "audition", "me/coaches/.auditions/d.md"])
        self.assertTrue(self.deps.coach_done)   # kept: the next turn needs no coach skill
        self.assertEqual(again.code, 64)
        self.assertIn("one audition a turn", again.error)
        self.assertEqual(sum(1 for argv, _ in calls if argv[:2] == ["coaches", "audition"]), 1)
        self.assertEqual(os.path.realpath(calls[1][0][2]),
                         os.path.realpath(os.path.join(self.home, "coaches", ".auditions", "d.md")))
        for argv, timeout in calls:   # a service designs or saves a voice: the long timeout
            if argv[1] in ("make", "audition", "keep"):
                self.assertEqual(timeout, tools.BUILD_TIMEOUT, argv)

    def test_the_narrative_can_be_written_but_not_the_candidates(self):
        self.assertEqual(tools.write_file(self.deps, "me/coaches/.auditions/coach-dana.md", "+++\n").code, 0)
        for path in ("me/coaches/.auditions/2026-10-28-1/candidates.json",
                     "me/coaches/.auditions/2026-10-28-1/narrative.md", "me/coaches/.auditions/x.json"):
            self.assertEqual(tools.write_file(self.deps, path, "[]").code, 64, path)

    def test_the_coach_skill_comes_when_a_coach_is_being_made(self):
        self.assertIn(".claude/skills/coach/SKILL.md", agent.skill_text(ROOT, coach=True))
        self.assertNotIn(".claude/skills/coach/SKILL.md", agent.skill_text(ROOT))
        for line in ("I want a new coach", "can I design a coach?", "a different voice please",
                     "make the coach a woman", "change how my coach sounds", "switch coach"):
            self.assertTrue(agent.wants_coach(line), line)
        self.assertFalse(agent.wants_coach("a 20 minute workout with my coach"))
        self.assertFalse(agent.audition_open(self.home))
        os.makedirs(os.path.join(self.home, "coaches", ".auditions", "2026-10-28-1"))
        self.assertFalse(agent.audition_open(self.home))
        with open(os.path.join(self.home, "coaches", ".auditions", "2026-10-28-1", "candidates.json"), "w") as f:
            f.write("[]")
        self.assertTrue(agent.audition_open(self.home))   # the listener picks next turn: the skill stays
        self.assertEqual(agent._write_step("me/coaches/.auditions/coach-dana.md"), "Describing your coach")

    def test_every_tool_is_registered(self):
        self.assertEqual(set(agent.AGENT._function_toolset.tools), {"run", "read_file", "write_file", "list_files"})


if __name__ == "__main__":
    unittest.main()
