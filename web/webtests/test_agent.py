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
        self.assertTrue(r.output.startswith("recorded\n"))
        self.assertIn("This workout is final", r.output)
        argv, timeout = calls[-1]
        self.assertEqual((argv[-2:], timeout), (["--max-chars", "3000"], tools.BUILD_TIMEOUT))

    def test_one_approval_records_once_and_the_workout_is_then_final(self):
        draft = "me/workouts/a/a.draft.txt"
        self.deps.approved = {"draft": draft, "coach": "Coach Reed", "chars": 3000}
        patch, calls = self.fake_engine()
        with patch:
            tools.run(self.deps, list(self.BUILD))
            sent = len(calls)
            again = tools.run(self.deps, list(self.BUILD))
            lint = tools.run(self.deps, list(self.BUILD) + ["--lint-only"])
        self.assertIsNone(self.deps.approved)
        self.assertEqual(self.deps.recorded, draft)
        self.assertEqual(len(calls), sent)   # nothing ran again
        for r in (again, lint):
            self.assertEqual(r.code, 64)
            self.assertTrue(r.refused)
            self.assertIn("already recorded", r.error)
        self.assertEqual(tools.write_file(self.deps, draft, "rewritten").code, 64)
        self.assertEqual(tools.write_file(self.deps, "me/workouts/a/notes.md", "fine").code, 0)

    def test_a_failed_recording_spends_its_approval_but_leaves_the_draft_open(self):
        from unittest import mock
        self.deps.approved = {"draft": "me/workouts/a/a.draft.txt", "coach": "Coach Reed", "chars": 3000}
        with mock.patch.object(tools.engine, "run", return_value=tools.engine.Result(1, "", "lint issue")):
            r = tools.run(self.deps, list(self.BUILD))
        self.assertEqual(r.code, 1)
        self.assertIsNone(self.deps.approved)   # a retry is priced and offered again
        self.assertIsNone(self.deps.recorded)

    def test_a_refusal_is_never_sent_to_the_model_as_a_field(self):
        r = tools.run(self.deps, ["build", "me/workouts/a/a.draft.txt", "A"])
        self.assertTrue(r.refused)
        self.assertNotIn("refused", r.model_dump())

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
        # (step 1 is the model reading the message: a thinking step, said only to a say that takes think)
        self.assertEqual(said, [("Getting to know you", "read_file", None, 2), ("Getting to know you", "read_file", 0, 2),
                                ("Running a check", "run setup", None, 3), ("Running a check", "run setup", 0, 3)])
        # (the site refused `setup`: the model's to fix, so the listener isn't shown a failed step)

    def test_the_model_s_thinking_is_said_while_it_runs(self):
        said = []
        self.deps.say = lambda text, tool, code, step, think=False: said.append((text, code, think))

        def script(messages, info):
            if not parts(messages, ToolReturnPart):
                return ModelResponse(parts=[ToolCallPart("run", {"args": ["brief", "--goal", "strength"]},
                                                         tool_call_id="c1")])
            return ModelResponse(parts=[TextPart("done")])

        agent.run_turn(FunctionModel(script), self.deps, None, "go")
        thinking = [(t, c) for t, c, k in said if k]
        # the first request reads the message; after the brief, the next is the script being written
        self.assertEqual(thinking, [("Reading your message", None), ("Reading your message", 0),
                                    ("Writing your script", None), ("Writing your script", 0)])
        self.assertIn(("Working out today's safe moves", None, False), said)

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
        # step 1 is the model reading the message (a thinking step, not said to this 4-argument say)
        self.assertEqual(said, [("Designing Coach Nolan's voice", None, 2), ("Designing Coach Nolan's voice", 0, 2),
                                ("Recording your workout", None, 3), ("Recording your workout", 0, 3)])

    def test_a_recording_counts_what_it_has_sent_and_a_total_off_plan_is_done(self):
        import time
        from unittest import mock
        said = []
        self.deps.say = lambda text, tool, code, step: said.append((text, code, step))
        draft = f"me/workouts/{STEM}/{STEM}.draft.txt"
        self.deps.approved = {"draft": draft, "name": "W", "coach": "Coach Owen", "chars": 2000, "usd": 0.04,
                              "service": "inworld"}
        logs = os.path.join(self.deps.home, "workouts", ".logs")
        os.makedirs(logs, exist_ok=True)
        with open(os.path.join(logs, "W.log"), "w", encoding="utf-8") as f:
            f.write("  [39/40] 4.0s audio\n")   # an earlier build's lines are never counted

        def run(root, home, argv, extra_env={}, timeout=120, cancel=None):
            with open(os.path.join(home, "workouts", ".logs", "W.log"), "a", encoding="utf-8") as f:
                f.write("--- build W\nSending 2,000 characters\n  [1/40] 3.1s audio\n  [18/40] 4.2s audio\n")
            time.sleep(1.6)
            return tools.engine.Result(2, "", "off plan")

        def script(messages, info):
            if not parts(messages, ToolReturnPart):
                return ModelResponse(parts=[ToolCallPart("run", {"args": ["build", draft, "W", "--coach", "Coach Owen"]},
                                                         tool_call_id="r1")])
            if len(parts(messages, ToolReturnPart)) == 1:
                return ModelResponse(parts=[ToolCallPart("read_file", {"path": "me/profile.md"},
                                                         tool_call_id="r2")])
            return ModelResponse(parts=[TextPart("ready")])
        with mock.patch.object(tools.engine, "run", side_effect=run):
            agent.run_turn(FunctionModel(script), self.deps, None, "Yes, record it.")
        self.assertEqual(said[:3], [("Recording your workout", None, 2), ("Recording your workout: 18 of 40", None, 2),
                                    ("Recording your workout (a little off its planned length)", 0, 2)])
        self.assertIn(("Wrapping up", 0, 4), said)   # reading why, after the recording, is wrapping up
        self.assertNotIn("Getting to know you", [t for t, _, _ in said])

    def test_a_failed_recording_is_still_a_failure(self):
        from unittest import mock
        said = []
        self.deps.say = lambda text, tool, code, step: said.append((text, code))
        draft = f"me/workouts/{STEM}/{STEM}.draft.txt"
        self.deps.approved = {"draft": draft, "name": "W", "coach": "Coach Owen", "chars": 2000, "usd": 0.04, "service": "inworld"}

        def script(messages, info):
            if not parts(messages, ToolReturnPart):
                return ModelResponse(parts=[ToolCallPart("run", {"args": ["build", draft, "W", "--coach", "Coach Owen"]}, tool_call_id="r1")])
            return ModelResponse(parts=[TextPart("stopped")])
        with mock.patch.object(tools.engine, "run", return_value=tools.engine.Result(4, "", "quota")):
            agent.run_turn(FunctionModel(script), self.deps, None, "Yes, record it.")
        self.assertEqual(said, [("Recording your workout", None), ("Recording your workout", 4)])

    def test_progress_reads_only_what_the_build_added(self):
        logs = os.path.join(self.deps.home, "workouts", ".logs")
        os.makedirs(logs, exist_ok=True)
        path = os.path.join(logs, "W.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write("  [40/40] 4.0s audio\n")
        before = agent._log_sizes(self.deps.home)
        self.assertIsNone(agent._progress(self.deps.home, before))
        with open(path, "a", encoding="utf-8") as f:
            f.write("  [3/12] 2.0s audio\n  [5/12] 2.2s audio\n")
        self.assertEqual(agent._progress(self.deps.home, before), (5, 12))
        self.assertEqual(agent._progress(self.deps.home + "-missing", {}), None)
        with open(path, "w", encoding="utf-8") as f:   # the log started over past its limit
            f.write("  [2/9] 2.0s audio\n")
        self.assertEqual(agent._progress(self.deps.home, {"W.log": 10_000}), (2, 9))

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
    def test_a_new_listener_asking_for_a_coach_gets_the_coach_first(self):
        from unittest import mock
        said = []
        self.deps.say = lambda text, tool, code, step: said.append(text)
        self.deps.setup = True
        with mock.patch.object(agent, "needs_setup", return_value=True):
            coach = agent.prefetch(self.deps, "I want a new coach.")
            setup = agent.prefetch(self.deps, "25 minutes of strength")
        self.assertTrue(coach.startswith(agent.COACH_FIRST))
        self.assertNotIn(agent.SETUP_FIRST, coach)
        self.assertTrue(setup.startswith(agent.SETUP_FIRST))
        self.assertEqual(said, ["Looking at your coaches"] * 2 + ["Getting you set up"] * 2)

    def test_a_new_listener_asking_for_one_job_gets_that_job_alone(self):
        """"I'd like to change my equipment." from the first screen is that job, never the setup interview."""
        from unittest import mock
        self.deps.setup = True
        with mock.patch.object(agent, "needs_setup", return_value=True):
            for line in ("I'd like to change my equipment.", "I'd like to update an injury.",
                         "I'd like to update my interests.", "what does the brief do?"):
                with self.subTest(line=line):
                    text = agent.prefetch(self.deps, line)
                    self.assertTrue(text.startswith(agent.TASK_FIRST), line)
                    self.assertNotIn(agent.SETUP_FIRST, text)
            for line in ("Set me up.", "Hey, coach Graham, I'd like a 25-minute full-body workout at home. "
                         "Nothing's bothering me today.", "", None):
                self.assertTrue(agent.prefetch(self.deps, line).startswith(agent.SETUP_FIRST), line)
        # a listener already set up gets none of these openings
        with mock.patch.object(agent, "needs_setup", return_value=False):
            text = agent.prefetch(self.deps, "I'd like to change my equipment.")
            self.assertFalse(text.startswith((agent.TASK_FIRST, agent.SETUP_FIRST, agent.COACH_FIRST)))

    def test_what_a_first_message_asks_for(self):
        cases = {"Set me up": "setup", "finish setting me up": "setup", "I want a new coach": "coach",
                 "switch coach": "coach", "20 minutes of strength": "workout", "a quick HIIT session": "workout",
                 "I'd like to change my equipment.": "task", "I'd like to update an injury.": "task",
                 "I'd like to update my interests.": "task", "add a kettlebell to my home kit": "task",
                 "my knee hurts after running, can I still train?": "task", None: "workout"}
        for line, want in cases.items():
            self.assertEqual(agent.intent(line), want, line)

    def test_step_one_comes_with_the_first_message(self):
        said = []
        self.deps.say = lambda text, tool, code, step: said.append(text)
        context = agent.prefetch(self.deps)
        for title in ("./harmonicfitness check", "./harmonicfitness content plan --minutes 25",
                      "./harmonicfitness get coach", "./harmonicfitness coaches list", "read me/profile.md",
                      "read me/training.md", "read me/health.md", "read me/log.md"):
            self.assertIn(f"### {title} (exit ", context)
        self.assertNotIn(self.home, context)
        self.assertEqual(said, ["Reading your profile and today's limits"] * 2)   # started, then done
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
        for six in ("Coach Miles", "Coach Fraser", "Coach Wade", "Coach Ruby", "Coach June", "Coach Freya"):
            self.assertIn(six, offered)
        for other in ("Coach Reed", "Coach Ellis", "Coach Owen", "Coach Andy", "Coach Maya"):
            self.assertNotIn(other, offered)
        self.assertIn("Coach Reed (Fish Audio)", block)   # named only as needing a key
        self.assertIn("add a key in Settings for more voices", block)
        self.assertNotIn('"speaks_here"', context)

    def test_the_coach_chosen_on_the_page_is_named(self):
        self.deps.keys = {"GEMINI_API_KEY": "AIzaabc123def456abcd", "FISH_AUDIO_API_KEY": "fishabc123def456abcd"}
        self.assertNotIn("the coach they chose on the page", agent.prefetch(self.deps))   # none chosen
        self.deps.picked = ("coach-june-gemini", "2099-01-01")
        context = agent.prefetch(self.deps)
        self.assertIn("### the coach they chose on the page (exit 0)", context)
        self.assertIn("Use Coach June for this workout unless they name another", context)
        self.assertIn('get route --coach "Coach June"', context)
        # one that can't speak here is never named
        self.deps.picked = ("coach-ellis-elevenlabs", "2099-01-01")
        self.assertNotIn("the coach they chose on the page", agent.prefetch(self.deps))

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


class Faster(AgentCase):
    """0.48.0: fewer round trips and smaller fixes on the way to a priced script."""
    DRAFT = "me/workouts/a/a.draft.txt"
    TEXT = "movements: air-squat\n\n@@ 30 | Welcome\nHello there.\n\n@@ 60 | Squats\nSquat now.\n[hold]\n\n@@ 30 | Close\nDone.\n"

    def draft(self, text=None):
        tools.write_file(self.deps, self.DRAFT, text or self.TEXT)
        with open(os.path.join(self.home, "workouts", "a", "a.draft.txt"), encoding="utf-8") as f:
            return f.read()

    def draft_text(self):
        with open(os.path.join(self.home, "workouts", "a", "a.draft.txt"), encoding="utf-8") as f:
            return f.read()

    def test_a_turn_fixes_several_segments_in_one_call(self):
        self.draft()

        def script(messages, info):
            if not parts(messages, ToolReturnPart):
                return ModelResponse(parts=[ToolCallPart("edit_segments", {"path": self.DRAFT, "edits": [
                    {"number": 1, "text": "@@ 30 | Welcome\nHello again."},
                    {"number": 3, "text": "@@ 30 | Close\nGood work today."}]}, tool_call_id="e1")])
            return ModelResponse(parts=[TextPart("fixed")])
        agent.run_turn(FunctionModel(script), self.deps, None, "go")
        self.assertIn("Hello again.", self.draft_text())
        self.assertIn("Good work today.", self.draft_text())

    def test_step_one_names_todays_workout_folders(self):
        os.makedirs(os.path.join(self.home, "workouts", f"{TODAY}-strength-20"))
        os.makedirs(os.path.join(self.home, "workouts", "2026-01-01-strength-20"))
        text = agent.prefetch(self.deps, "a 20-minute strength workout")
        self.assertIn(f"me/workouts/{TODAY}-strength-20/", text)
        self.assertNotIn("2026-01-01-strength-20", text)

    def test_a_draft_far_from_the_brief_s_word_count_is_told(self):
        os.makedirs(os.path.join(self.home, "workouts", "a"), exist_ok=True)
        with open(os.path.join(self.home, "workouts", "a", "a.brief.md"), "w", encoding="utf-8") as f:
            f.write("- Talk to time: ... For this 2-minute session, write about 100 words in all (between 90 and 110).\n")
        r = tools.write_file(self.deps, self.DRAFT, self.TEXT)
        self.assertIn("about 5 words. That's 95% under the brief's 100 words: lengthen it", r.output)
        long = self.TEXT.replace("Hello there.", "Hello there. " + "And again, " * 60)
        self.assertIn("over the brief's 100 words: trim it", tools.write_file(self.deps, self.DRAFT, long).output)
        near = self.TEXT.replace("Hello there.", "word " * 97)
        self.assertNotIn("brief's", tools.write_file(self.deps, self.DRAFT, near).output)

    def test_a_draft_says_what_its_segments_add_up_to(self):
        r = tools.write_file(self.deps, self.DRAFT, self.TEXT)
        self.assertIn("3 segments adding up to 120 s (2 min), about 5 words", r.output)
        self.assertNotIn("adding up", tools.write_file(self.deps, "me/notes.md", "hi").output)

    def test_segments_are_replaced_by_their_places_in_one_call(self):
        self.draft()
        r = tools.edit_segments(self.deps, self.DRAFT, [
            {"number": 3, "text": "@@ 20 | Close\nGood work."},
            tools.SegmentEdit(number=2, text="@@ 70 | Squats\nSquat now, slow and low.\n[hold]")])
        self.assertEqual(r.code, 0, r.error)
        self.assertIn("replaced segments 2, 3", r.output)
        self.assertIn("adding up to 120 s", r.output)
        self.assertEqual(self.draft_text(), self.TEXT.replace("@@ 60 | Squats\nSquat now.", "@@ 70 | Squats\nSquat now, slow and low.")
                         .replace("@@ 30 | Close\nDone.", "@@ 20 | Close\nGood work."))

    def test_a_segment_edit_is_refused_when_it_cant_apply_and_nothing_is_written(self):
        self.draft()
        ok = {"number": 1, "text": "@@ 30 | Welcome\nHi again."}
        for path, edits in ((self.DRAFT, [ok, {"number": 4, "text": "@@ 30 | X\nHi there."}]),
                            (self.DRAFT, [{"number": 0, "text": "@@ 30 | X\nHi there."}]),
                            (self.DRAFT, [ok, {"number": 2, "text": "Hi there."}]),
                            (self.DRAFT, [{"number": 1, "text": "@@ 30 | X\nHi.\n@@ 30 | Y\nHo."}]),
                            (self.DRAFT, [ok, dict(ok)]), (self.DRAFT, []), (self.DRAFT, "not a list"),
                            ("me/profile.md", [ok])):
            self.assertTrue(tools.edit_segments(self.deps, path, edits).refused, (path, edits))
            self.assertEqual(self.draft_text(), self.TEXT)   # all or nothing
        self.deps.recorded = self.DRAFT
        self.assertTrue(tools.edit_segments(self.deps, self.DRAFT, [ok]).refused)

    def test_step_one_plans_the_rests_for_the_length_asked(self):
        line = "Hey, coach Ruby, I'd like a 35-minute full-body workout at home. Nothing's bothering me today."
        self.assertIn(["content", "plan", "--minutes", "35"], agent.first_runs(line))
        self.assertIn(["content", "plan", "--minutes", "25"], agent.first_runs("a workout please"))
        self.assertIn(["get", "web-builds"], agent.first_runs(line))

    def test_the_writing_guides_come_with_the_skill(self):
        text = agent.skill_text(ROOT)
        self.assertIn('<file path="knowledge/script.md">', text)
        self.assertIn('<file path="knowledge/tts-rules.md">', text)

    def fake(self, sends=True):
        from unittest import mock
        calls = []

        def run(root, home, argv, extra_env={}, timeout=120, cancel=None):
            calls.append(argv)
            if argv[:2] == ["get", "cost"]:
                return tools.engine.Result(0, '{"service": "gemini", "chars": 3000, "usd": 0.05}', "")
            if "--max-chars" in argv and argv[argv.index("--max-chars") + 1] == "1":
                return tools.engine.Result(1, "  the script speaks 3,000 characters; this build may send at most 1", "")
            if "--lint-only" in argv:
                return tools.engine.Result(0, "lint ok\nSends 3,000 characters to the voice service" if sends else "lint ok", "")
            return tools.engine.Result(0, "recorded", "")
        return mock.patch.object(tools.engine, "run", side_effect=run), calls

    BUILD = ["build", "me/workouts/a/a.draft.txt", "Workout A", "--coach", "Coach Ruby"]

    def test_the_lint_s_own_count_prices_the_script(self):
        self.draft()
        patch, calls = self.fake()
        with patch:
            r = tools.run(self.deps, list(self.BUILD))
        self.assertIn("Not recorded yet", r.output)
        self.assertEqual(self.deps.offer["chars"], 3000)
        self.assertFalse(any("--max-chars" in a for a in calls))   # one lint, then the price, nothing more
        self.assertEqual(len(calls), 2)

    def test_a_script_just_linted_clean_is_priced_without_linting_again(self):
        self.draft()
        patch, calls = self.fake()
        with patch:
            self.assertEqual(tools.run(self.deps, self.BUILD + ["--lint-only"]).code, 0)
            tools.run(self.deps, list(self.BUILD))
            self.assertEqual([a[0] for a in calls], ["build", "get"])
            self.draft(self.TEXT.replace("Hello there.", "Hello again."))   # changed since: linted again
            tools.run(self.deps, list(self.BUILD))
        self.assertEqual([a[0] for a in calls], ["build", "get", "build", "get"])

    def test_an_older_engine_is_counted_the_old_way(self):
        self.draft()
        patch, calls = self.fake(sends=False)
        with patch:
            r = tools.run(self.deps, list(self.BUILD))
        self.assertIn("Not recorded yet", r.output)
        self.assertTrue(any("--max-chars" in a for a in calls))

    def turn_that_builds(self):
        def script(messages, info):
            if not parts(messages, ToolReturnPart):
                return ModelResponse(parts=[ToolCallPart("run", {"args": list(self.BUILD)}, tool_call_id="b1")])
            return ModelResponse(parts=[TextPart("ready")])
        return script

    def test_record_without_asking_records_once_priced(self):
        self.draft()
        reserved = []
        self.deps.auto_record = True
        self.deps.reserve = lambda chars: reserved.append(chars) or True
        patch, calls = self.fake()
        with patch:
            out = agent.run_turn(FunctionModel(self.turn_that_builds()), self.deps, None, "go")
        self.assertEqual(reserved, [3000])
        self.assertEqual(self.deps.recorded, self.DRAFT)
        self.assertIsNone(self.deps.offer)   # no Record button
        self.assertEqual(calls[-1][-2:], ["--max-chars", "3000"])   # within the price
        self.assertIn(agent.AUTO_RECORDED, out.history_json.replace("\\n", "\n"))

    def test_record_without_asking_past_the_allowance_waits_for_record(self):
        self.draft()
        self.deps.auto_record = True
        self.deps.reserve = lambda chars: False
        patch, calls = self.fake()
        with patch:
            agent.run_turn(FunctionModel(self.turn_that_builds()), self.deps, None, "go")
        self.assertIsNone(self.deps.recorded)
        self.assertEqual(self.deps.offer["chars"], 3000)   # the Record button, which says why
        self.assertFalse(any(a[0] == "build" and "--lint-only" not in a for a in calls))


class ThirtyMinuteLoop1(Faster):
    """0.49.4: a write that builds, long paragraphs split by the site, the feeds sheet with `run feeds`."""

    def test_a_draft_written_with_its_build_is_built_in_the_same_call(self):
        patch, calls = self.fake()

        def script(messages, info):
            if not parts(messages, ToolReturnPart):
                return ModelResponse(parts=[ToolCallPart("write_file", {
                    "path": self.DRAFT, "content": self.TEXT, "build_name": "Workout A", "coach": "Coach Reed"},
                    tool_call_id="w1")])
            return ModelResponse(parts=[TextPart("ready")])
        with patch:
            agent.run_turn(FunctionModel(script), self.deps, None, "go")
        self.assertEqual([a[0] for a in calls], ["build", "get"])   # linted and priced, no `run build` turn
        self.assertEqual(self.deps.offer["name"], "Workout A")

    def test_a_write_without_its_build_only_writes(self):
        patch, calls = self.fake()
        with patch:
            def script(messages, info):
                if not parts(messages, ToolReturnPart):
                    return ModelResponse(parts=[ToolCallPart("write_file", {"path": self.DRAFT, "content": self.TEXT},
                                                             tool_call_id="w1")])
                return ModelResponse(parts=[TextPart("ok")])
            agent.run_turn(FunctionModel(script), self.deps, None, "go")
        self.assertEqual(calls, [])

    def test_a_long_paragraph_is_split_at_a_sentence(self):
        long = ("The Flyers won four to two last night in a game that went back and forth all evening long. "
                "Their goalie made thirty saves. The crowd stayed loud all night. The next game is Tuesday at home "
                "against the Rangers, who have won five straight and lead the division.")
        text = self.TEXT.replace("Hello there.", "[story]\n" + long + "\n[/story]")
        r = tools.write_file(self.deps, self.DRAFT, text)
        self.assertIn("split 1 long paragraph", r.output)
        body = self.draft_text()
        self.assertIn("all night.\n\nThe next game", body)
        self.assertTrue(all(len(c) <= tools.SPLIT_OVER for ln in body.split("\n") for c in tools._clips(ln)))
        self.assertEqual(tools.split_long(body), (body, 0))   # nothing left to split
        short = self.TEXT
        self.assertEqual(tools.split_long(short), (short, 0))

    def test_markers_are_never_split(self):
        line = ("Lower slowly for three, then drive up. [hold 4s] " + "Keep the ribs down and breathe out as you rise. " * 6)
        out, n = tools.split_long("@@ 60 | Set\n" + line + "\n")
        self.assertGreater(n, 0)
        self.assertIn("[hold 4s]", out)
        self.assertEqual(out.count("["), line.count("["))

    def test_run_feeds_hands_over_the_sheet(self):
        daily = os.path.join(self.home, "workouts", "research", "daily")
        os.makedirs(daily, exist_ok=True)
        with open(os.path.join(daily, f"{TODAY}-feeds.md"), "w", encoding="utf-8") as f:
            f.write("# Feeds\n## Weather\n- sunny\n## Local\n- a headline\n")
        from concurrent.futures import Future
        done = Future()
        done.set_result(tools.ToolResult(code=0, output="## Weather\n- sunny"))
        self.deps.feeds = done
        r = tools.run(self.deps, ["feeds"])
        self.assertIn("a headline", r.output)
        self.assertEqual(r.output.count("a headline"), 1)

    def test_gemini_thinks_medium_while_writing_and_low_between(self):
        class GoogleModel:   # named as pydantic-ai's
            pass
        self.assertEqual(agent.thinking_level(GoogleModel(), "draft"), "MEDIUM")
        self.assertEqual(agent.thinking_level(GoogleModel(), "brief"), "MEDIUM")
        self.assertEqual(agent.thinking_level(GoogleModel(), ""), "LOW")
        self.assertEqual(agent.thinking_level(GoogleModel(), "priced"), "LOW")
        self.assertIsNone(agent.thinking_level(object(), "draft"))   # other providers keep their default

    def test_step_one_brings_todays_research_sheet(self):
        daily = os.path.join(self.home, "workouts", "research", "daily")
        os.makedirs(daily, exist_ok=True)
        with open(os.path.join(daily, f"{TODAY}.md"), "w", encoding="utf-8") as f:
            f.write("# Research\n- the big story: 16.3 billion\n")
        self.assertIn("16.3 billion", agent.prefetch(self.deps, "a 30-minute strength workout"))


class Search(AgentCase):
    def test_every_writer_can_search_the_web(self):
        from webapp import providers
        for p in providers.PROVIDERS:
            self.assertEqual(agent.native_tools(providers.model_for(p, "sk-test-0000000000000000")), [agent.SEARCH], p)

    def test_a_model_without_search_gets_none(self):
        class Plain:
            def supported_native_tools(self):
                return frozenset()
        self.assertEqual(agent.native_tools(Plain()), [])
        self.assertEqual(agent.native_tools(object()), [])

    def test_each_request_offers_the_search_and_the_turn_counts_them(self):
        sent = []

        class Spy(FunctionModel):
            async def request(self, messages, model_settings, params):
                sent.append(list(params.native_tools))
                return await super().request(messages, model_settings, params)
        out = agent.run_turn(Spy(lambda m, i: ModelResponse(parts=[TextPart("hi")])), self.deps, None, "go")
        self.assertEqual(sent, [[agent.SEARCH]])
        self.assertEqual(out.usage["searches"], 0)

    def test_the_web_coach_is_told_it_can_search(self):
        self.assertIn("You have web search", agent.PREAMBLE)
        self.assertNotIn("no web search", agent.PREAMBLE)


class Enjoyed(AgentCase):
    def test_what_they_enjoyed_is_never_a_workout_request(self):
        for line in ("Lately I enjoyed a 5k run with friends", "We saw Atsuko Okatsuka at the Bell House",
                     "last weekend I tried a new yoga studio", "I loved dinner at Lilia"):
            self.assertEqual(agent.intent(line), "task", line)
        self.assertEqual(agent.intent("a 25-minute run workout please"), "workout")

    def test_the_web_coach_knows_how_to_record_what_they_enjoyed(self):
        for words in ("interests add --source mention", "at most twelve", "broader topic as parent", "as `taste`",
                      "as `venue`", "interests forget"):
            self.assertIn(words, agent.PREAMBLE, words)

    def test_signals_become_engine_arguments(self):
        from webapp.agent import enrich
        sig = enrich.Signal
        args = enrich.signal_args([sig(kind="topic", name="AC | DC", weight=1, parent="rock"),
                                   sig(kind="effort", name="effort", weight=-1, note="too  hard\ntoday")])
        self.assertEqual(args, ["--signal", "topic | AC / DC | 1 | rock | ", "--signal", "effort | effort | -1 |  | too hard today"])
        self.assertNotIn("health", enrich.Enrichment.model_fields)   # pain stays in the feedback line


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
        self.assertNotIn(".claude/skills/workout/research.md", text)   # a computer's research agents only
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
        for line in ("I'd like to update my interests.", "add a topic", "Suggest some topics", "new topics please"):
            self.assertTrue(agent.wants_setup(line), line)
        self.assertFalse(agent.wants_setup("a workout, any topic is fine"))

    def test_coaches_are_chosen_here_not_made(self):
        from unittest import mock
        calls = []

        def run(root, home, argv, extra_env={}, timeout=120, cancel=None):
            calls.append((argv, timeout))
            return tools.engine.Result(0, "done", "")
        with mock.patch.object(tools.engine, "run", side_effect=run):
            for args in (["coaches", "make", "Coach Reed"], ["coaches", "forget-audition", "2026-10-28-1"],
                         ["coaches", "archive", "Coach Dana"]):
                self.assertEqual(tools.run(self.deps, args).code, 0, args)
            for args in (["coaches", "audition", "me/coaches/.auditions/d.md"],
                         ["coaches", "keep", "2026-10-28-1/B", "--name", "Coach Dana"]):
                r = tools.run(self.deps, args)
                self.assertEqual(r.code, 64, args)
                self.assertIn("Coaches page", r.error)
        self.assertTrue(self.deps.coach_done)   # an old audition closed: the next turn needs no coach skill
        self.assertEqual([argv[1] for argv, _ in calls], ["make", "forget-audition", "archive"])
        self.assertEqual(calls[0][1], tools.BUILD_TIMEOUT)   # make designs a voice: the long timeout

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
        self.assertEqual(set(agent.AGENT._function_toolset.tools), {"run", "read_file", "write_file", "edit_segments", "list_files"})


if __name__ == "__main__":
    unittest.main()
