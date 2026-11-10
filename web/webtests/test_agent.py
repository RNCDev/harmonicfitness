import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from unittest import mock

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
# the Record card's notes, read beside the price (tools._offer_notes): left out where a test counts the build's calls
NOTE_CALLS = (["get", "plan"], ["get", "web-builds"])


def counted(calls):
    """The engine calls a build made, without the Record card's notes."""
    return [a for a in calls if a[:2] not in NOTE_CALLS]


def parts(messages, kind):
    return [p for m in messages for p in m.parts if isinstance(p, kind)]


class AgentCase(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="hf-agent-")
        self.addCleanup(shutil.rmtree, self.home, True)
        folder.materialize(folder.seed(ROOT), self.home)
        self.deps = tools.Deps(engine_root=ROOT, home=self.home, keys={}, today=TODAY,
                               now=f"{TODAY} Wednesday 08:00", writers="three")   # as the worker sets it


class AddMissingGo(AgentCase):
    """A skeleton set's [reps N] with no go before it gets its go from code, as the lint names the fix."""
    DRAFT = "me/workouts/a/a.draft.txt"

    def test_a_bare_reps_gets_its_go(self):
        self.assertEqual(tools.add_missing_go("@@ 45 | Push-up set 1, 10 reps\n[reps 10]\n"),
                         ("@@ 45 | Push-up set 1, 10 reps\n[count 3 go] [reps 10]\n", 1))

    def test_a_set_with_its_go_is_left_alone(self):
        text = "@@ 45 | Set 1\n[count 3 go] [reps 10]\n\n@@ 45 | Set 2\n[count 5 go] [reps 8]\n"
        self.assertEqual(tools.add_missing_go(text), (text, 0))

    def test_a_full_draft_is_never_touched(self):
        text = "@@ 45 | Set 1\nKeep it steady now.\n[reps 10]\n"
        self.assertEqual(tools.add_missing_go(text), (text, 0))

    def test_a_three_writer_write_adds_it_and_says_so(self):
        r = tools.write_file(self.deps, self.DRAFT, "movements: push-up\n\n@@ 45 | Push-up set 1, 10 reps\n[reps 10]\n")
        with open(os.path.join(self.home, "workouts", "a", "a.draft.txt"), encoding="utf-8") as f:
            self.assertIn("[count 3 go] [reps 10]", f.read())
        self.assertIn("Added the go before 1 sets' reps", r.output)

    def test_a_one_writer_skeleton_is_not_normalized(self):
        self.deps.writers = "one"
        r = tools.write_file(self.deps, self.DRAFT, "movements: push-up\n\n@@ 45 | Push-up set 1, 10 reps\n[reps 10]\n")
        with open(os.path.join(self.home, "workouts", "a", "a.draft.txt"), encoding="utf-8") as f:
            self.assertNotIn("count 3 go", f.read())
        self.assertNotIn("Added the go", r.output)


class ShowPlan(AgentCase):
    """A clean skeleton's plan goes to the chat while the writers' room fills it (tools.show_plan)."""
    PLAN = {"rows": [{"what": "Air squat", "kind": "movement", "segments": 2, "seconds": 100}], "seconds": 100}
    DRAFT = "me/workouts/a/a.draft.txt"

    def shown(self, result):
        events = []
        self.deps.event = lambda stage, **fields: events.append((stage, fields))
        with mock.patch.object(tools.engine, "run", return_value=result) as run:
            tools.show_plan(self.deps, self.DRAFT)
        return events, run

    def test_the_engine_s_plan_is_sent_as_an_event(self):
        events, run = self.shown(tools.engine.Result(0, json.dumps(self.PLAN), ""))
        self.assertEqual(events, [("plan", {"plan": self.PLAN})])
        argv = run.call_args.args[2]
        self.assertEqual(argv[:3], ["get", "plan", "--draft"])
        self.assertEqual(os.path.realpath(argv[3]), os.path.realpath(os.path.join(self.home, "workouts", "a", "a.draft.txt")))

    def test_nothing_is_shown_when_the_plan_cant_be_worked_out(self):
        for result in (tools.engine.Result(1, "", "No draft"), tools.engine.Result(0, "not json", ""),
                       tools.engine.Result(0, '{"rows": [], "seconds": 0}', "")):
            self.assertEqual(self.shown(result)[0], [])

    def test_without_an_event_sink_or_outside_the_folder_the_engine_isnt_asked(self):
        with mock.patch.object(tools.engine, "run") as run:
            tools.show_plan(self.deps, self.DRAFT)   # no event sink (tests, and the agent run by hand)
            self.deps.event = lambda *a, **k: None
            tools.show_plan(self.deps, "me/../../etc/passwd")
        run.assert_not_called()


class Run(AgentCase):
    def test_runs_the_engine_with_me_paths(self):
        draft = f"me/workouts/{STEM}/{STEM}.draft.txt"
        r = tools.run(self.deps, ["brief", "--goal", "strength", "--minutes", "20", "--preset", "bodyweight",
                                  "--today", TODAY, "--save", draft])
        self.assertEqual(r.code, 0, r.error)
        self.assertTrue(os.path.isfile(os.path.join(self.home, "workouts", STEM, f"{STEM}.menu.json")))
        self.assertNotIn(self.home, r.output + r.error)
        self.assertNotIn(os.path.realpath(self.home), r.output + r.error)

    def test_a_command_that_fetches_pages_gets_no_key(self):
        self.deps.keys = {"FISH_AUDIO_API_KEY": "k" * 20, "TZ": "LCL-5"}
        with mock.patch.object(tools.engine, "run", return_value=tools.engine.Result(0, "", "")) as run:
            for args in (["topics", "add", "F1", "--feed", "https://example.org/feed"], ["youtube", "abc"],
                         ["content", "plan"], ["check"]):
                tools.run(self.deps, args)
        envs = {c.args[2][0]: c.kwargs["extra_env"] for c in run.call_args_list}
        self.assertEqual((envs["topics"], envs["youtube"], envs["content"]), ({"TZ": "LCL-5"},) * 3)   # the clock only
        self.assertEqual(envs["check"], {"FISH_AUDIO_API_KEY": "k" * 20, "TZ": "LCL-5"})

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

    def test_three_writer_turns_carry_only_the_drafts_guides(self):
        """The agent writes only the skeleton: of tts-rules.md it keeps the draft's format and the markers; the
        voice rules are the writers'. A one-writer turn carries the whole file."""
        three = agent.skill_text(ROOT, writers="three")
        one = agent.skill_text(ROOT, writers="one")
        for kept in ("# What a voice can read", "## The draft", "## Markers"):
            self.assertIn(kept, three)
        for cut in ("## Characters", "## Numbers and abbreviations", "## Local and web voices",
                    "## Words that trip a voice"):
            self.assertNotIn(cut, three)
            self.assertIn(cut, one)
        self.assertLess(len(three), len(one))

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

    def test_one_recording_at_a_time_in_a_worker(self):
        """Two turns recording at once (worker slots, 0.77.0) render one after the other: rendering is the memory
        a worker has least of. A Stop while waiting ends it without sending anything."""
        import copy
        import threading
        import time
        from unittest import mock
        live, most, started = [0], [0], []

        def run(root, home, argv, extra_env={}, timeout=120, cancel=None):
            if "--max-chars" in argv:
                live[0] += 1
                most[0] = max(most[0], live[0])
                started.append(argv)
                time.sleep(0.3)
                live[0] -= 1
            return tools.engine.Result(0, "recorded", "")
        approved = {"draft": "me/workouts/a/a.draft.txt", "coach": "Coach Reed", "chars": 3000}
        mine, theirs = copy.copy(self.deps), copy.copy(self.deps)
        mine.approved, theirs.approved = dict(approved), dict(approved)
        with mock.patch.object(tools.engine, "run", side_effect=run):
            both = [threading.Thread(target=tools.run, args=(d, list(self.BUILD))) for d in (mine, theirs)]
            for t in both:
                t.start()
            for t in both:
                t.join()
            self.assertEqual((len(started), most[0]), (2, 1))
            with tools.RECORDING:   # another turn is recording: this one waits, and the listener presses Stop
                stopped = copy.copy(self.deps)
                stopped.approved, stopped.cancel = dict(approved), threading.Event()
                threading.Timer(0.2, stopped.cancel.set).start()
                r = tools.run(stopped, list(self.BUILD))
        self.assertEqual(r.code, tools.engine.STOPPED)
        self.assertEqual(len(started), 2)

    def write_draft(self, *seconds):
        path = os.path.join(self.home, "workouts", "a", "a.draft.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("movements: march in place\n" + "".join(f"@@ {s} | Part\nEasy now.\n\n" for s in seconds))
        return path

    def test_a_recording_may_take_the_workout_s_length_and_the_turn_waits_for_it(self):
        self.write_draft(1200, 600)   # thirty minutes
        self.deps.approved = {"draft": "me/workouts/a/a.draft.txt", "coach": "Coach Reed", "chars": 3000}
        extended = []
        self.deps.extend_turn = extended.append
        patch, calls = self.fake_engine()
        with patch:
            tools.run(self.deps, list(self.BUILD))
        self.assertEqual(calls[-1][1], 1800)   # thirty minutes to record
        self.assertEqual(extended, [1800 + tools.TURN_FINISH])

    def test_a_short_workout_s_recording_keeps_the_least_build_time(self):
        self.assertEqual(tools.build_timeout(self.write_draft(300, 300)), tools.BUILD_TIMEOUT)
        self.assertEqual(tools.build_timeout(os.path.join(self.home, "nowhere.draft.txt")), tools.BUILD_TIMEOUT)

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
        with open(os.path.join(self.home, ".env"), "w", encoding="utf-8") as f:
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
        for bad in ("me/.env", "me/a.mp3", "tools/x.py", "me/../x.md", "knowledge/x.md", "me/",
                    "me/coaches/coach-dana-fish/sample.mp3"):   # kept, but the engine's to make
            self.assertEqual(tools.write_file(self.deps, bad, "x").code, 64, bad)
        self.assertEqual(tools.write_file(self.deps, "me/big.md", "x" * (tools.WRITE_LIMIT + 1)).code, 64)

    def test_the_check_in_may_change_health(self):
        self.assertEqual(tools.write_file(self.deps, "me/health.md", "+++\nschema = 6\n+++\n").code, 0)

    def test_list_hides_skipped_files(self):
        with open(os.path.join(self.home, ".env"), "w", encoding="utf-8") as f:
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
        # the first request reads the message; after the brief, the next plans the script (its skeleton)
        self.assertEqual(thinking, [("Reading your message", None), ("Reading your message", 0),
                                    ("Planning your script", None), ("Planning your script", 0)])
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

    def test_two_turns_prefetching_run_at_most_the_workers_cap_of_engine_commands(self):
        """Worker slots (0.77.0) can start two turns at once: their step-one commands share one cap."""
        import copy
        import threading
        import time
        from unittest import mock
        live, most = [0], [0]
        lock = threading.Lock()
        real = agent.tools.run

        def run(deps, args):
            with lock:
                live[0] += 1
                most[0] = max(most[0], live[0])
            time.sleep(0.1)
            with lock:
                live[0] -= 1
            return real(deps, args)
        with mock.patch.object(agent.tools, "run", side_effect=run):
            both = [threading.Thread(target=agent.prefetch, args=(copy.copy(self.deps),)) for _ in range(2)]
            for t in both:
                t.start()
            for t in both:
                t.join()
        self.assertEqual(most[0], agent.PREFETCH_AT_ONCE)

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
        said.clear()
        agent.prefetch(self.deps, "I'd like to update my interests.")   # one job: no limits to read
        self.assertEqual(said, ["Reading your profile"] * 2)
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


class DraftCase(AgentCase):
    """A turn over one draft, me/workouts/a/a.draft.txt, with the engine faked."""
    DRAFT = "me/workouts/a/a.draft.txt"
    TEXT = "movements: air-squat\n\n@@ 30 | Welcome\nHello there.\n\n@@ 60 | Squats\nSquat now.\n[hold]\n\n@@ 30 | Close\nDone.\n"

    def draft(self, text=None):
        tools.write_file(self.deps, self.DRAFT, text or self.TEXT)
        return self.draft_text()

    def draft_text(self):
        with open(os.path.join(self.home, "workouts", "a", "a.draft.txt"), encoding="utf-8") as f:
            return f.read()

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


class Faster(DraftCase):
    """0.48.0: fewer round trips and smaller fixes on the way to a priced script."""

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

    def test_a_skeleton_is_linted_for_its_budgets_not_built(self):
        """A draft with its segments but no words yet is the skeleton: its write runs a lint-only build, whose
        report is each segment's word budget, and the turn goes on to the draft, not to a fix."""
        patch, calls = self.fake()
        skeleton = "movements: air-squat\n\n@@ 30 | Welcome\n\n@@ 60 | Squats\n[count 3 go]\n[hold 4s]\n\n@@ 30 | Close\n"
        self.assertTrue(tools.is_skeleton(skeleton))
        self.assertFalse(tools.is_skeleton(self.TEXT))
        said = []
        self.deps.say = lambda text, tool, code, step, think=False: said.append(text) if not think else None

        def script(messages, info):
            if not parts(messages, ToolReturnPart):
                return ModelResponse(parts=[ToolCallPart("write_file", {
                    "path": self.DRAFT, "content": skeleton, "build_name": "Workout A", "coach": "Coach Reed"},
                    tool_call_id="w1")])
            return ModelResponse(parts=[TextPart("budgets read")])
        with patch:
            agent.run_turn(FunctionModel(script), self.deps, None, "go")
        self.assertEqual([a[0] for a in calls], ["build"])
        self.assertIn("--lint-only", calls[0])   # never priced, nothing recorded
        self.assertIsNone(self.deps.offer)
        self.assertEqual(self.deps.phase, "rests")   # the next request writes the rests, thinking hardest
        self.assertFalse(self.deps.lint_failed)
        self.assertFalse(self.deps.skeleton)
        self.assertEqual(said[:2], ["Planning the script's timing", "Planning the script's timing"])
        self.assertIn("no words yet (a skeleton)", self.draft_text() and tools.write_file(self.deps, self.DRAFT, skeleton).output)

    def menu(self, seconds=120):
        os.makedirs(os.path.join(self.home, "workouts", "a"), exist_ok=True)
        with open(os.path.join(self.home, "workouts", "a", "a.menu.json"), "w", encoding="utf-8") as f:
            json.dump({"seconds": seconds}, f)

    def test_a_draft_written_in_passes_is_linted_until_every_segment_has_words(self):
        """After the skeleton, the rests are written to their budgets in one edit and the coaching in another: each
        pass with segments still empty runs a lint-only build (the budgets and what's left), and the pass that
        fills the last segment builds for real."""
        self.menu(120)
        patch, calls = self.fake()
        skeleton = "movements: air-squat\n\n@@ 30 | Welcome\n\n@@ 60 | Squats\n[hold]\n\n@@ 30 | Close\n"
        said = []
        self.deps.say = lambda text, tool, code, step, think=False: said.append(text) if not think else None
        plan = [ToolCallPart("write_file", {"path": self.DRAFT, "content": skeleton, "build_name": "Workout A",
                                            "coach": "Coach Reed"}, tool_call_id="w1"),
                ToolCallPart("edit_segments", {"path": self.DRAFT, "edits": [
                    {"number": 3, "text": "@@ 30 | Close\n[story] The Flyers won. [/story] Good work today."}],
                    "build_name": "Workout A", "coach": "Coach Reed"}, tool_call_id="e1"),
                ToolCallPart("edit_segments", {"path": self.DRAFT, "edits": [
                    {"number": 1, "text": "@@ 30 | Welcome\nHello there."},
                    {"number": 2, "text": "@@ 60 | Squats\nSquat now.\n[hold]"}],
                    "build_name": "Workout A", "coach": "Coach Reed"}, tool_call_id="e2")]
        phases = []

        def script(messages, info):
            n = len(parts(messages, ToolReturnPart))
            phases.append(self.deps.phase)
            return ModelResponse(parts=[plan[n]] if n < len(plan) else [TextPart("ready")])
        with patch:
            agent.run_turn(FunctionModel(script), self.deps, None, "go")
        # two lints for the budgets, then the last pass's own lint and its price (an unapproved build)
        self.assertEqual([a[0] for a in counted(calls)], ["build", "build", "build", "get"])
        self.assertEqual(self.deps.offer["name"], "Workout A")
        self.assertEqual(phases[1:3], ["rests", "skeleton"])   # the rests after the whole skeleton, then the rest
        self.assertIn("Checking the script so far", said)
        self.assertEqual(self.deps.skeleton, "")

    def test_a_skeleton_close_to_the_request_is_settled_over_its_rests(self):
        """Within ten percent, the tool spreads the difference over the rests and says so; further off, the
        writer is told how far, as before."""
        self.menu(600)
        close = ("movements: air-squat\n\n@@ 60 | Welcome\n\n@@ 100 | Squats\n[hold]\n\n@@ 120 | Rest after squats\n\n"
                 "@@ 100 | Lunges\n[hold]\n\n@@ 80 | Rest after lunges\n\n@@ 125 | Close\n")   # 585 s
        r = tools.write_file(self.deps, self.DRAFT, close)
        self.assertIn("adding up to 600 s", r.output)
        self.assertIn("The segments added up to 585 s: 15 s given to the rests (Rest after squats 120 to 130; "
                      "Rest after lunges 80 to 85), so they add up to the request's 600 s", r.output)
        self.assertEqual([s for s, _ in tools.segments_of(self.draft_text())], [60, 100, 130, 100, 85, 125])
        self.assertEqual(self.deps.skeletons[f"workouts/a/a.draft.txt"][2], (130, "Rest after squats"))
        off = close.replace("@@ 125 | Close", "@@ 95 | Close")   # 555 s: 7.5 percent short, settled too
        r = tools.write_file(self.deps, self.DRAFT, off)
        self.assertIn("The segments added up to 555 s: 45 s given to the rests", r.output)
        far = close.replace("@@ 125 | Close", "@@ 40 | Close")   # 500 s: 17 percent short
        r = tools.write_file(self.deps, self.DRAFT, far)
        self.assertIn("adding up to 500 s", r.output)
        self.assertNotIn("given to the rests", r.output)
        lopsided = ("movements: air-squat\n\n@@ 60 | Welcome\n\n@@ 200 | Squats\n[hold]\n\n@@ 20 | Rest after squats\n\n"
                    "@@ 200 | Lunges\n[hold]\n\n@@ 20 | Rest after lunges\n\n@@ 70 | Close\n")   # 570 s, short rests
        r = tools.write_file(self.deps, self.DRAFT, lopsided)   # 30 s over 40 s of rest would grow each by three quarters
        self.assertNotIn("given to the rests", r.output)
        padded = close.replace("@@ 120 | Rest after squats", "@@ 135 | Rest after squats")   # 600 s, a rest too long
        r = tools.write_file(self.deps, self.DRAFT, padded)
        self.assertIn("Rests over two minutes: Rest after squats (135 s)", r.output)

    def test_a_draft_off_the_clock_is_not_built_until_one_edit_lands_it(self):
        """A full draft whose @@ seconds don't add up to the request isn't built: the write says how far off it is
        and which of the skeleton's segments it dropped, for one edit; the edit that lands the clock builds."""
        self.menu(120)
        patch, calls = self.fake()
        skeleton = "movements: air-squat\n\n@@ 30 | Welcome\n\n@@ 60 | Squats\n[hold]\n\n@@ 30 | Close\n"
        short = "movements: air-squat\n\n@@ 30 | Welcome\nHello there.\n\n@@ 30 | Close\nDone now.\n"
        with patch:
            tools.write_file(self.deps, self.DRAFT, skeleton)
            r = tools.write_file(self.deps, self.DRAFT, short)
            self.assertFalse(r.build)
            self.assertIn("Not built: the segments add up to 60 s, but the request is 120 s: add 60 s", r.output)
            self.assertIn("dropped Squats (60 s)", r.output)
            self.assertIn("one edit_segments", r.output)
            r = tools.edit_segments(self.deps, self.DRAFT, [{"number": 2, "text": "@@ 90 | Close\nDone now, slowly."}])
            self.assertTrue(r.build, r.output)
            self.assertNotIn("Not built", r.output)
            r = tools.edit_segments(self.deps, self.DRAFT, [{"number": 2, "text": "@@ 80 | Close\nDone now."}])
            self.assertFalse(r.build)
            self.assertIn("Not built: the segments add up to 110 s, but the request is 120 s: add 10 s", r.output)

    def test_a_draft_keeping_its_skeleton_s_segments_gets_their_seconds_back(self):
        self.menu(120)
        skeleton = "movements: air-squat\n\n@@ 30 | Welcome\n\n@@ 60 | Squats\n[hold]\n\n@@ 30 | Close\n"
        drifted = self.TEXT.replace("@@ 60 | Squats", "@@ 45 | Squats")   # 105 s: the words were written to 60
        tools.write_file(self.deps, self.DRAFT, skeleton)
        r = tools.write_file(self.deps, self.DRAFT, drifted)
        self.assertTrue(r.build)
        self.assertIn("The @@ seconds came to 105 s; the skeleton's (120 s, the request) are restored", r.output)
        self.assertIn("@@ 60 | Squats", self.draft_text())
        self.assertIn("adding up to 120 s", r.output)

    def test_an_edit_keeping_the_skeleton_s_segments_gets_their_seconds_back_too(self):
        """An edit_segments that changes a segment's seconds off the clock gets the skeleton's back, as a write does:
        a writer told "add 30 s" ran check, read the draft and rebuilt twice (0.50.2's loop)."""
        self.menu(120)
        skeleton = "movements: air-squat\n\n@@ 30 | Welcome\n\n@@ 60 | Squats\n[hold]\n\n@@ 30 | Close\n"
        tools.write_file(self.deps, self.DRAFT, skeleton)
        tools.write_file(self.deps, self.DRAFT, self.TEXT)
        r = tools.edit_segments(self.deps, self.DRAFT, [{"number": 2, "text": "@@ 45 | Squats\nSquat now, slowly.\n[hold]"}])
        self.assertTrue(r.build, r.output)
        self.assertIn("the skeleton's (120 s, the request) are restored", r.output)
        self.assertIn("@@ 60 | Squats", self.draft_text())

    def test_a_draft_is_written_with_its_stiff_forms_contracted(self):
        """"Let us go, that is one" reads like a letter aloud: the site contracts the forms that read one way only,
        in the spoken lines, and leaves one before a pause, the markers and the labels as they are."""
        text = ("movements: air-squat\n\n@@ 120 | Let us begin\nLet us go. That is one, and do not rush. We are "
                "done, that is, nearly. Here you are. Let us know. [count 3 go]\n[story] Who is first? They cannot "
                "lose. [/story]\n")
        tools.write_file(self.deps, self.DRAFT, text)
        got = self.draft_text()
        self.assertIn("@@ 120 | Let us begin", got)
        self.assertIn("Let's go. That's one, and don't rush. We're done, that is, nearly. Here you are. Let us know. "
                      "[count 3 go]", got)
        self.assertIn("[story] Who's first? They can't lose. [/story]", got)
        tools.edit_segments(self.deps, self.DRAFT, [{"number": 1, "text": "@@ 120 | Let us begin\nIt is not far."}])
        self.assertIn("It isn't far.", self.draft_text())

    def test_a_verb_that_ends_its_clause_stays_whole(self):
        """"Stay where you're or drop a plate" can't be said: after where, how, what, who, as or than the verb ends
        its clause, so it isn't contracted (a negative still is)."""
        self.assertEqual(tools.contract("Stay right where you are or drop a plate.")[0],
                         "Stay right where you are or drop a plate.")
        self.assertEqual(tools.contract("You are close, and that is it. Where you do not rush.")[0],
                         "You're close, and that's it. Where you don't rush.")

    def test_the_build_s_ask_for_words_is_scaled_to_what_the_writer_delivers(self):
        """A writer asked for 600 words added a third of that: the first ask is doubled, the next scaled by what the
        last one brought (at most three times), and a build that asks nothing forgets it."""
        out = "Predicted length 25 min\nTo land on plan, add about 300 words in one edit: #7 +120, #9 +100, #2 +80\nok"
        got = tools.scale_ask(self.deps, "d", out, 2000)
        self.assertIn("add about 600 words in one edit: #7 +240, #9 +200, #2 +160\nok", got)
        got = tools.scale_ask(self.deps, "d", out.replace("300", "200"), 2200)   # 200 of the 600 shown: times three
        self.assertIn("add about 600 words", got)
        got = tools.scale_ask(self.deps, "d", out, 2800)                          # all 600: as asked
        self.assertIn("add about 300 words", got)
        self.assertEqual(tools.scale_ask(self.deps, "d", "Predicted length 30 min", 3100), "Predicted length 30 min")
        self.assertNotIn("d", self.deps.asks)

    def test_a_long_paragraph_is_never_split_after_initials(self):
        """"U.S. / Soccer" was heard as a pause mid-name (0.50.2's loop): a split comes at a sentence's end only."""
        line = ("He came up through the U.S. Soccer academy and the Union's second team, and last month he played "
                "every minute of three straight games for a club in Spain. That is the part worth knowing. The "
                "squad meets in Florida next week for two qualifiers against Haiti, and the coach has said he starts.")
        self.assertTrue(all(not p.rstrip().endswith("U.S.") for p in tools._split_line(line)))

    def test_a_write_off_the_clock_runs_no_build_in_the_turn(self):
        self.menu(120)
        patch, calls = self.fake()
        short = "movements: air-squat\n\n@@ 30 | Welcome\nHello there.\n\n@@ 30 | Close\nDone now.\n"

        def script(messages, info):
            if not parts(messages, ToolReturnPart):
                return ModelResponse(parts=[ToolCallPart("write_file", {
                    "path": self.DRAFT, "content": short, "build_name": "Workout A", "coach": "Coach Reed"},
                    tool_call_id="w1")])
            return ModelResponse(parts=[TextPart("fixing")])
        with patch:
            agent.run_turn(FunctionModel(script), self.deps, None, "go")
        self.assertEqual(calls, [])
        self.assertIsNone(self.deps.offer)

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

    BUILD = ["build", "me/workouts/a/a.draft.txt", "Workout A", "--coach", "Coach Ruby"]

    def test_the_offer_carries_the_engine_s_plan_and_says_when_it_s_the_first(self):
        """The Record card's plan comes from the engine (get plan), never the model; `first` before the first web
        build, so the card says where the script goes."""
        self.draft()
        patch, calls = self.fake()
        plan = {"rows": [{"what": "Air squat", "kind": "movement", "segments": 2, "seconds": 100}], "seconds": 100}

        asked = []

        def run(root, home, argv, extra_env={}, timeout=120, cancel=None):
            if argv[:2] == ["get", "plan"]:
                asked.append(argv[3])
                return tools.engine.Result(0, json.dumps(plan), "")
            if argv[:2] == ["get", "web-builds"]:
                return tools.engine.Result(0, '{"web_builds": 0}', "")
            return patch.kwargs["side_effect"](root, home, argv, extra_env, timeout, cancel)
        with mock.patch.object(tools.engine, "run", side_effect=run):
            tools.run(self.deps, list(self.BUILD))
        self.assertEqual((self.deps.offer["plan"], self.deps.offer["first"]), (plan, True))
        # the engine is given the draft's own path, as the build is: it can't read the agent's me/...
        self.assertEqual([os.path.realpath(a) for a in asked], [os.path.realpath(os.path.join(self.home, "workouts", "a", "a.draft.txt"))])
        self.assertIn("| Air squat | 2 | 1:40 |", tools.plan_table(self.deps.offer))

    def test_the_lint_s_own_count_prices_the_script(self):
        self.draft()
        patch, calls = self.fake()
        with patch:
            r = tools.run(self.deps, list(self.BUILD))
        self.assertIn("Not recorded yet", r.output)
        self.assertEqual(self.deps.offer["chars"], 3000)
        self.assertFalse(any("--max-chars" in a for a in calls))   # one lint, then the price, nothing more
        self.assertEqual(len(counted(calls)), 2)

    def test_a_script_just_linted_clean_is_priced_without_linting_again(self):
        self.draft()
        patch, calls = self.fake()
        with patch:
            self.assertEqual(tools.run(self.deps, self.BUILD + ["--lint-only"]).code, 0)
            tools.run(self.deps, list(self.BUILD))
            self.assertEqual([a[0] for a in counted(calls)], ["build", "get"])
            self.draft(self.TEXT.replace("Hello there.", "Hello again."))   # changed since: linted again
            tools.run(self.deps, list(self.BUILD))
        self.assertEqual([a[0] for a in counted(calls)], ["build", "get", "build", "get"])

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

    LOG = ["log-session", "--draft", "me/workouts/a/a.draft.txt", "--format", "circuit", "--topics", "Formula 1",
           "--loads", "goblet squat = 20 lb, 2s"]
    TOLD = ["Formula 1 | explainer | The Undercut | me/workouts/research/reserve/the-undercut.md"]

    def logging_fake(self):
        """The engine, where log-session refuses a draft until it's recorded, as the real one does."""
        from unittest import mock
        calls, made = [], []

        def run(root, home, argv, extra_env={}, timeout=120, cancel=None):
            calls.append(argv)
            if argv[:2] == ["get", "cost"]:
                return tools.engine.Result(0, '{"service": "gemini", "chars": 3000, "usd": 0.05}', "")
            if "--lint-only" in argv:
                return tools.engine.Result(0, "lint ok\nSends 3,000 characters to the voice service", "")
            if argv[0] == "log-session" and not made:
                return tools.engine.Result(1, "", "Not logged: no build of me/workouts/a/a.draft.txt as it stands")
            if argv[0] == "build":
                made.append(argv)
            return tools.engine.Result(0, "done", "")
        return mock.patch.object(tools.engine, "run", side_effect=run), calls

    def test_the_site_logs_the_room_s_stories_once_recorded(self):
        self.draft()
        self.deps.auto_record, self.deps.reserve = True, (lambda chars: True)
        self.deps.told = {"draft": self.DRAFT, "items": list(self.TOLD)}
        patch, calls = self.logging_fake()
        with patch:
            out = agent.run_turn(FunctionModel(self.turn_that_builds()), self.deps, None, "go")
        logged = [a for a in calls if a[:2] == ["content", "log"]]
        self.assertEqual(len(logged), 1)   # the engine's own path for the draft: tools.run maps me/ to the folder
        self.assertEqual(logged[0][:5] + logged[0][6:], ["content", "log", "--date", TODAY, "--draft", "--item", self.TOLD[0]])
        self.assertTrue(logged[0][5].endswith("/workouts/a/a.draft.txt"))
        self.assertIn("The site logged the 1 stories", out.history_json)
        made = next(i for i, a in enumerate(calls) if a[0] == "build" and "--max-chars" in a)
        self.assertGreater(calls.index(logged[0]), made)   # after the recording, never before

    def test_a_log_session_sent_ahead_is_kept_with_the_offer_and_run_once_recorded(self):
        self.draft()
        patch, calls = self.logging_fake()

        def ahead(messages, info):
            if not parts(messages, ToolReturnPart):
                return ModelResponse(parts=[ToolCallPart("run", {"args": list(self.BUILD)}, tool_call_id="b1"),
                                            ToolCallPart("run", {"args": list(self.LOG)}, tool_call_id="l1")])
            return ModelResponse(parts=[TextPart("ready")])
        self.deps.told = {"draft": self.DRAFT, "items": list(self.TOLD)}
        said = []
        self.deps.say = lambda text, tool, code, step, think=False: said.append((text, tool, code))
        with patch:
            out = agent.run_turn(FunctionModel(ahead), self.deps, None, "go")
        self.assertIn("Kept: this draft isn't recorded yet", out.history_json)
        self.assertEqual((self.deps.offer["log"], self.deps.offer["told"]), (self.LOG, self.TOLD))
        # kept, not logged yet: a success on the listener's steps and in the worker's log, under its own words
        self.assertIn((agent.NOTING_LOG, "run log-session", 0), said)
        self.assertIsNone(self.deps.logged)

        # the Record button's turn: a fresh turn, with only the offer to go on
        offer = self.deps.offer
        self.deps = tools.Deps(engine_root=ROOT, home=self.home, keys={}, today=TODAY, now=f"{TODAY} Wednesday 08:00",
                               writers="three")
        self.deps.approved = offer
        before = len(calls)
        with patch:
            out = agent.run_turn(FunctionModel(self.turn_that_builds()), self.deps, None, "Yes, record it.")
        after = calls[before:]
        self.assertEqual([a[0] for a in after], ["build", "content", "log-session"])
        self.assertEqual(self.deps.logged, self.DRAFT)
        self.assertIn("The site logged the session", out.history_json)

    SKELETON = "movements: air-squat\n\n@@ 30 | Welcome\n\n@@ 60 | Squats\n[hold]\n\n@@ 30 | Close\n"
    FIELDS = tools.LogFields(format="circuit", topics="Jazz", loads="push-up = bodyweight")

    def skeleton_turn(self, **extra):
        def script(messages, info):
            if not parts(messages, ToolReturnPart):
                return ModelResponse(parts=[ToolCallPart("write_file", {
                    "path": self.DRAFT, "content": self.SKELETON, "build_name": "Workout A",
                    "coach": "Coach Freya", **extra}, tool_call_id="w1")])
            return ModelResponse(parts=[TextPart("ok")])
        return script

    def test_a_skeleton_written_with_log_fields_keeps_the_log(self):
        patch, calls = self.logging_fake()
        fields = self.FIELDS
        with patch:
            out = agent.run_turn(FunctionModel(self.skeleton_turn(log=fields.model_dump())), self.deps, None, "go")
        want = tools.log_argv(self.DRAFT, "Coach Freya", fields)
        self.assertEqual(want, ["log-session", "--draft", self.DRAFT, "--coach", "Coach Freya", "--format", "circuit",
                                "--topics", "Jazz", "--loads", "push-up = bodyweight"])
        self.assertEqual(self.deps.pending_log, want)
        self.assertIn("The session's log is kept", out.history_json)
        self.draft()   # the words written, the build priced: the offer carries the log
        with patch:
            tools.run(self.deps, ["build", self.DRAFT, "Workout A", "--coach", "Coach Freya"])
        self.assertEqual(self.deps.offer["log"], want)

    def test_without_log_fields_nothing_changes(self):
        patch, calls = self.logging_fake()
        with patch:
            out = agent.run_turn(FunctionModel(self.skeleton_turn()), self.deps, None, "go")
        self.assertIsNone(self.deps.pending_log)
        self.assertNotIn("The session's log is kept", out.history_json)

    def test_log_fields_are_ignored_when_one_writer_writes(self):
        self.deps.writers = "one"
        patch, calls = self.logging_fake()
        with patch:
            out = agent.run_turn(FunctionModel(self.skeleton_turn(log=self.FIELDS.model_dump())), self.deps, None, "go")
        self.assertIsNone(self.deps.pending_log)
        self.assertNotIn("The session's log is kept", out.history_json)

    def test_the_instructions_ask_for_log_fields_with_the_skeleton_only_in_three_writer_mode(self):
        three, one = agent.preamble("three"), agent.preamble("one")
        self.assertIn("Pass `log` with that `write_file`", three)
        self.assertNotIn("run `log-session` for the draft", three)
        self.assertNotIn("Pass `log`", one)

    def test_a_log_session_after_the_site_logged_it_runs_nothing(self):
        self.deps.logged = self.DRAFT
        patch, calls = self.logging_fake()

        def again(messages, info):
            if not parts(messages, ToolReturnPart):
                return ModelResponse(parts=[ToolCallPart("run", {"args": list(self.LOG)}, tool_call_id="l1")])
            return ModelResponse(parts=[TextPart("ok")])
        with patch:
            out = agent.run_turn(FunctionModel(again), self.deps, None, "go")
        self.assertEqual(calls, [])
        self.assertIn("Already logged", out.history_json)

    LATER = {"at": "2026-11-04T12:00:00+00:00", "local": "2026-11-04 Wednesday 07:00", "offset": -300}

    def test_a_workout_for_later_is_checked_in_now_and_written_then(self):
        self.deps.later = dict(self.LATER)
        patch, calls = self.fake()
        seen = []

        def script(messages, info):
            seen.append({t.name for t in info.function_tools})
            if not parts(messages, ToolReturnPart):
                return ModelResponse(parts=[
                    ToolCallPart("run", {"args": ["brief", "--goal", "strength", "--minutes", "15"]}, tool_call_id="b"),
                    ToolCallPart("schedule_workout", {"minutes": 15, "coach": "Coach Reed"}, tool_call_id="s")])
            return ModelResponse(parts=[TextPart("A 15-minute strength workout for Wednesday at 07:00.")])
        with patch:
            out = agent.run_turn(FunctionModel(script), self.deps, None, "go")
        self.assertIn("schedule_workout", seen[0])
        self.assertFalse(any(a[0] == "brief" for a in calls))   # the brief waits for its own turn
        self.assertIn("Wednesday 07:00", out.history_json)
        self.assertEqual(self.deps.schedule, {"minutes": 15, "coach": "Coach Reed", "chars": 15 * agent.CHARS_A_MINUTE,
                                              "usd": 0.05, "ceiling_chars": 15 * agent.CEILING_A_MINUTE,
                                              "ceiling_usd": 0.05})
        self.assertIn(["get", "cost", "--coach", "Coach Reed", "--chars", str(15 * agent.CEILING_A_MINUTE), "--json"],
                      calls)

    def test_schedule_workout_is_offered_only_for_later_and_not_in_its_own_turn(self):
        for later, run_, offered in ((None, False, False), (self.LATER, False, True), (self.LATER, True, False)):
            seen = []

            def script(messages, info):
                seen.append({t.name for t in info.function_tools})
                return ModelResponse(parts=[TextPart("ok")])
            self.deps.later, self.deps.scheduled_run = later, run_
            agent.run_turn(FunctionModel(script), self.deps, None, "go")
            self.assertEqual("schedule_workout" in seen[0], offered, (later, run_))

    def test_a_workout_for_later_records_on_its_own_within_its_ceiling(self):
        self.draft()
        reserved = []
        self.deps.later, self.deps.scheduled_run = dict(self.LATER), True
        self.deps.auto_record, self.deps.ceiling = True, 4000
        self.deps.reserve = lambda chars: reserved.append(chars) or True
        patch, calls = self.fake()
        with patch:
            out = agent.run_turn(FunctionModel(self.turn_that_builds()), self.deps, None, "go")
        self.assertEqual((reserved, self.deps.recorded), ([3000], self.DRAFT))
        self.assertIn(agent.SCHEDULED_RECORDED, out.history_json.replace("\\n", "\n"))

    def test_a_workout_for_later_over_its_ceiling_waits_for_record(self):
        self.draft()
        reserved = []
        self.deps.later, self.deps.scheduled_run = dict(self.LATER), True
        self.deps.auto_record, self.deps.ceiling = True, 2500
        self.deps.reserve = lambda chars: reserved.append(chars) or True
        patch, calls = self.fake()
        with patch:
            out = agent.run_turn(FunctionModel(self.turn_that_builds()), self.deps, None, "go")
        self.assertEqual((reserved, self.deps.recorded), ([], None))
        self.assertEqual(self.deps.offer["chars"], 3000)   # the Record button, with its real price
        self.assertIn("over the 2,500 the listener approved", out.history_json)

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


class Closes(DraftCase):
    """The turn closes at the price in code: the page shows the plan and the price, so no model request is spent
    only to say the script is ready."""
    SKELETON = "movements: air-squat\n\n@@ 30 | Welcome\n\n@@ 60 | Squats\n[hold]\n\n@@ 30 | Close\n"
    FIELDS = tools.LogFields(format="circuit", topics="Jazz", loads="push-up = bodyweight")
    COACH = "Coach Freya"

    def write(self, tid, content, **extra):
        return ModelResponse(parts=[ToolCallPart("write_file", {
            "path": self.DRAFT, "content": content, "build_name": "Workout A", "coach": self.COACH, **extra},
            tool_call_id=tid)])

    def turn(self, log=True, after=None):
        """The skeleton (with the log's fields when `log`), then the words, built and priced. A request after the
        price fails the test, unless `after` gives its reply."""
        def script(messages, info):
            returns = parts(messages, ToolReturnPart)
            if not returns:
                return self.write("w1", self.SKELETON, **({"log": self.FIELDS.model_dump()} if log else {}))
            if len(returns) == 1:
                return self.write("w2", self.TEXT)
            if after is None:
                raise AssertionError("a model request after the price")
            return ModelResponse(parts=[TextPart(after)])
        return script

    def test_a_clean_price_closes_the_turn_without_another_request(self):
        patch, calls = self.fake()
        with patch:
            out = agent.run_turn(FunctionModel(self.turn()), self.deps, None, "go")
        self.assertEqual(self.deps.offer["log"], tools.log_argv(self.DRAFT, self.COACH, self.FIELDS))
        self.assertTrue(agent.closed(self.deps))
        self.assertEqual(out.reply, "Your script is written and checked. Press Record when you're ready.")
        self.assertEqual(out.reply, agent.closing_reply(self.deps))
        self.assertEqual(out.usage["requests"], 2)   # the skeleton's, then the one that called the build
        saved = ModelMessagesTypeAdapter.validate_json(out.history_json)
        self.assertIsInstance(saved[-1], ModelResponse)
        self.assertEqual([p.content for p in saved[-1].parts if isinstance(p, TextPart)], [out.reply])
        self.assertIn("Not recorded yet", out.history_json)

    def test_record_without_asking_records_before_the_turn_closes(self):
        self.deps.auto_record, self.deps.reserve = True, (lambda chars: True)
        patch, calls = self.fake()
        with patch:
            out = agent.run_turn(FunctionModel(self.turn(after="Recorded: it's in your workouts.")), self.deps,
                                 None, "go")
        self.assertEqual(self.deps.recorded, self.DRAFT)
        self.assertFalse(agent.closed(self.deps))
        self.assertEqual(out.reply, "Recorded: it's in your workouts.")
        self.assertEqual(out.usage["requests"], 3)

    def test_a_scheduled_price_over_the_ceiling_says_it_waits(self):
        self.deps.later = {"at": "2026-11-04T12:00:00+00:00", "local": "2026-11-04 Wednesday 07:00", "offset": -300}
        self.deps.scheduled_run, self.deps.auto_record, self.deps.ceiling = True, True, 2500
        self.deps.reserve = lambda chars: True
        patch, calls = self.fake()
        with patch:
            out = agent.run_turn(FunctionModel(self.turn()), self.deps, None, "go")
        self.assertIsNone(self.deps.recorded)
        self.assertEqual(out.reply, "Your script is written and checked, but it came out longer than planned, so it "
                                    "waits for your Record.")
        self.assertEqual(out.usage["requests"], 2)

    def test_the_next_turn_reads_a_closed_turns_history(self):
        patch, calls = self.fake()
        with patch:
            out = agent.run_turn(FunctionModel(self.turn()), self.deps, None, "go")
        seen = []

        def second(messages, info):
            seen.append(messages)
            return ModelResponse(parts=[TextPart("It's ready when you are.")])
        deps = tools.Deps(engine_root=ROOT, home=self.home, keys={}, today=TODAY, now=f"{TODAY} Wednesday 08:05",
                          writers="three")   # a fresh turn, as the worker makes one
        out2 = agent.run_turn(FunctionModel(second), deps, out.history_json, "what's in it?")
        self.assertEqual(out2.reply, "It's ready when you are.")
        first = seen[0]
        self.assertTrue(any("Not recorded yet" in str(p.content) for p in parts(first, ToolReturnPart)))
        self.assertIn(agent.closing_reply(self.deps), [p.content for p in parts(first, TextPart)])

    def test_without_a_kept_log_the_model_closes_as_now(self):
        patch, calls = self.fake()
        with patch:
            out = agent.run_turn(FunctionModel(self.turn(log=False, after="ready")), self.deps, None, "go")
        self.assertNotIn("log", self.deps.offer)
        self.assertFalse(agent.closed(self.deps))
        self.assertEqual(out.reply, "ready")

    def test_a_one_writer_turn_with_a_kept_log_is_not_closed_by_code(self):
        self.deps.writers = "one"
        self.deps.pending_log = tools.log_argv(self.DRAFT, self.COACH, self.FIELDS)
        patch, calls = self.fake()
        with patch:
            out = agent.run_turn(FunctionModel(self.turn(after="ready")), self.deps, None, "go")
        self.assertEqual(self.deps.offer["log"], tools.log_argv(self.DRAFT, self.COACH, self.FIELDS))
        self.assertFalse(agent.closed(self.deps))
        self.assertEqual(out.reply, "ready")

    def test_a_session_already_logged_closes_too(self):
        self.deps.phase, self.deps.offer = "priced", {"draft": self.DRAFT, "chars": 3000}
        self.assertFalse(agent.closed(self.deps))
        self.deps.logged = self.DRAFT
        self.assertTrue(agent.closed(self.deps))
        self.deps.recorded = self.DRAFT
        self.assertFalse(agent.closed(self.deps))


class ThirtyMinuteScripts(DraftCase):
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
        self.assertEqual([a[0] for a in counted(calls)], ["build", "get"])   # linted and priced, no `run build` turn
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
        self.assertEqual(agent.thinking_level(GoogleModel(), "rests"), "HIGH")
        self.assertEqual(agent.thinking_level(GoogleModel(), "rests", "three"), "MEDIUM")   # the room writes them
        self.assertEqual(agent.thinking_level(GoogleModel(), "draft"), "MEDIUM")
        self.assertEqual(agent.thinking_level(GoogleModel(), "brief"), "MEDIUM")
        self.assertEqual(agent.thinking_level(GoogleModel(), ""), "LOW")
        self.assertEqual(agent.thinking_level(GoogleModel(), "priced"), "LOW")
        self.assertIsNone(agent.thinking_level(object(), "draft"))   # other providers keep their default

    def test_gemini_through_openrouter_thinks_at_the_same_levels(self):
        class OpenRouterModel:   # named as pydantic-ai's
            def __init__(self, name):
                self.model_name = name
        from webapp.agent import writers
        gemini, claude = OpenRouterModel("google/gemini-3.8-flash"), OpenRouterModel("anthropic/claude-opus-5.5")
        self.assertEqual(agent.thinking_level(gemini, "brief"), "MEDIUM")
        self.assertEqual(writers.thinking_settings(gemini, "MEDIUM"), {"openrouter_reasoning": {"effort": "medium"}})
        self.assertIsNone(agent.thinking_level(claude, "brief"))   # any other model: its provider's default
        self.assertIsNone(writers.thinking_settings(claude, "LOW"))

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


class Topics(AgentCase):
    """A topics job (0.63.0): the bare ask answered at once, then `topics add` on a light turn."""

    def test_the_bare_ask_is_answered_without_a_model(self):
        for line in ("I'd like to update my interests.", "update my topics", "Add a topic", "add a new topic please"):
            self.assertTrue(agent.BARE_TOPICS.search(line), line)
        for line in ("add F1 to my topics", "Can you add the Sunday Puzzle podcast?", "I like reading example.com",
                     "update my interests and give me a workout"):
            self.assertFalse(agent.BARE_TOPICS.search(line), line)
        out = agent.opener_turn("I'd like to update my interests.")
        self.assertEqual(out.reply, agent.TOPICS_OPENER)
        self.assertIn("trending topics", out.reply)
        self.assertTrue(agent.only_opener(out.history_json))
        self.assertFalse(agent.only_opener(None))

    def test_a_topics_job_goes_on_from_the_opener_and_stops_for_a_workout(self):
        first = "I'd like to update my interests."
        self.assertTrue(agent.topics_job(first, "I like reading https://www.example.com/"))
        self.assertFalse(agent.topics_job(first, "actually, a 20 minute workout"))
        self.assertFalse(agent.topics_job(first, "Lately I enjoyed a show at the Example Room"))
        self.assertFalse(agent.topics_job("a 20 minute workout", "sounds good"))
        self.assertFalse(agent.topics_job("a 20 minute workout", "add a topic about F1 for the rests"))   # mid check-in
        self.assertFalse(agent.only_opener("x" * (agent.OPENER_MOST + 1)))

    def test_a_topics_turn_is_light_with_no_search(self):
        self.assertEqual(agent.skill_text(ROOT, topics=True), "")
        self.assertIn(".claude/skills/setup/SKILL.md", agent.skill_text(ROOT, True, topics=True))
        self.assertIn("topics", tools.COMMANDS)
        sent = []

        class Spy(FunctionModel):
            async def request(self, messages, model_settings, params):
                sent.append(list(params.native_tools))
                return await super().request(messages, model_settings, params)
        self.deps.topics = True
        agent.run_turn(Spy(lambda m, i: ModelResponse(parts=[TextPart("added")])), self.deps, None, "add F1")
        self.assertEqual(sent, [[]])   # a FunctionModel offers search otherwise (the test above)

    def test_the_topics_context_holds_the_topics_and_never_bring_up(self):
        text = agent.topics_context(self.home)
        self.assertIn("## Topics", text)
        self.assertIn("## Never bring up", text)
        self.assertNotIn("[[feeds]]", text)


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
            self.assertIn(agent.web_copy(f.read())[-300:].strip(), text)   # the whole skill, to its last line
        self.assertNotIn("web: skip", text)          # less what's marked for a computer only
        self.assertNotIn("SendUserFile", text)
        self.assertNotIn("./harmonicfitness backup", text)
        self.assertIn(".claude/skills/workout/SKILL.md", text)
        self.assertNotIn(".claude/skills/workout/research.md", text)   # a computer's research agents only
        self.assertIn("Never ask the listener for a key or a password", text)
        self.assertIn("--lint-only", text)
        self.assertIn("kept until three newer workouts replace it", text)
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
        self.assertTrue(agent.about_me("Nothing's bothering me today. About me: call me Sam. I'm new to this."))
        self.assertFalse(agent.about_me("Tell me about meditation"))
        self.assertTrue(agent.wants_setup("Finish setting me up"))
        self.assertFalse(agent.wants_setup("a 20 minute workout"))
        for line in ("I'd like to update my interests.", "add a topic", "Suggest some topics", "new topics please"):
            self.assertFalse(agent.wants_setup(line), line)   # a topics job, on a light turn (0.63.0)
            self.assertTrue(agent.topics_job(line, line), line)
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
        with open(os.path.join(self.home, "coaches", ".auditions", "2026-10-28-1", "candidates.json"), "w", encoding="utf-8") as f:
            f.write("[]")
        self.assertTrue(agent.audition_open(self.home))   # the listener picks next turn: the skill stays
        self.assertEqual(agent._write_step("me/coaches/.auditions/coach-dana.md"), "Describing your coach")

    def test_every_tool_is_registered(self):
        self.assertEqual(set(agent.AGENT._function_toolset.tools), {"run", "read_file", "write_file", "edit_segments", "list_files",
                                                                   "write_script", "schedule_workout"})


class TurnClock(AgentCase):
    def test_past_its_time_the_turn_stops_the_engine_command_in_it_too(self):
        import asyncio
        self.deps.cancel = threading.Event()

        async def slow(messages, info):
            await asyncio.sleep(1.0)
            return ModelResponse(parts=[TextPart("Hello.")])
        with mock.patch.object(agent, "TURN_SECONDS", 0.2):
            with self.assertRaises(agent.TurnError) as caught:
                agent.run_turn(FunctionModel(slow), self.deps, None, "go")
        self.assertEqual(caught.exception.reason, agent.TIMED_OUT)   # not "stopped", though the stop is set
        self.assertTrue(self.deps.cancel.is_set())                   # a running build is killed, not left sending

    def test_a_recording_s_limit_holds_the_turn_open(self):
        import asyncio

        async def recording(messages, info):
            self.deps.extend_turn(3.0)   # as an approved build does before it starts
            await asyncio.sleep(0.8)
            return ModelResponse(parts=[TextPart("Recorded.")])
        with mock.patch.object(agent, "TURN_SECONDS", 0.2):
            out = agent.run_turn(FunctionModel(recording), self.deps, None, "go")
        self.assertEqual(out.reply, "Recorded.")
        self.assertIsNone(self.deps.extend_turn)   # the clock ends with its turn

    def test_stop_during_a_request_stops_the_turn(self):
        import asyncio
        self.deps.cancel = threading.Event()

        async def slow(messages, info):
            self.deps.cancel.set()   # the listener presses Stop while the model thinks
            await asyncio.sleep(2.0)
            return ModelResponse(parts=[TextPart("Hello.")])
        with self.assertRaises(agent.TurnError) as caught:
            agent.run_turn(FunctionModel(slow), self.deps, None, "go")
        self.assertEqual(caught.exception.reason, agent.STOPPED)

    def test_a_turn_ends_without_waiting_for_the_researcher_s_engine_command(self):
        """A turn that saved the brief (the researcher's engine command still running in a thread) and ends on a
        question replies at once: the command's thread is left to finish on its own."""
        import asyncio
        import time
        release = threading.Event()
        self.addCleanup(release.set)

        async def stories(*args, **kwargs):   # the researcher's `content plan`, slow
            await asyncio.to_thread(release.wait, 5.0)
            return []

        def script(messages, info):
            if not parts(messages, ToolReturnPart):
                return ModelResponse(parts=[ToolCallPart("run", {"args": [
                    "brief", "--goal", "strength", "--minutes", "15", "--save", "me/workouts/a/a.draft.txt"]},
                    tool_call_id="b1")])
            return ModelResponse(parts=[TextPart("Which kit do you have today?")])
        began = time.monotonic()
        with mock.patch.object(agent.writers, "stories", stories), \
                mock.patch.object(tools.engine, "run", return_value=tools.engine.Result(0, "brief saved", "")):
            out = agent.run_turn(FunctionModel(script), self.deps, None, "go")
        self.assertIsNotNone(self.deps.content_job)   # the researcher had started
        self.assertEqual(out.reply, "Which kit do you have today?")
        self.assertLess(time.monotonic() - began, 2.0)



class StepTimes(unittest.TestCase):
    """The worker's log times a step from when it began: a recording's progress ("18 of 40") says the running
    step again, and once restarted its clock (a 503 s recording logged as 383 s, 2026-11-03)."""

    def test_a_running_step_said_again_keeps_its_start(self):
        import io
        import types
        from webapp import worker
        ctx = types.SimpleNamespace(started={}, job_id=7, say=lambda *a, **k: None)
        err = io.StringIO()
        with mock.patch.object(worker.time, "monotonic", side_effect=[0.0, 120.0, 503.0]), \
                mock.patch.object(sys, "stderr", err):
            worker._step(ctx, "Recording your workout", "run build", None, 3)
            worker._step(ctx, "Recording your workout: 18 of 40", "run build", None, 3)
            worker._step(ctx, "Recording your workout", "run build", 0, 3)
        self.assertIn("run build exit 0 503.0s", err.getvalue())


if __name__ == "__main__":
    unittest.main()

class History(unittest.TestCase):
    """What a turn saves of the model's side (0.76.0): no instructions, and a long conversation's old results short."""

    def messages(self, results: int, size: int):
        from pydantic_ai.messages import (ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart,
                                          UserPromptPart)
        out = []
        for i in range(results):
            out += [ModelRequest(parts=[UserPromptPart(content=f"turn {i}")], instructions="I" * 50_000),
                    ModelResponse(parts=[ToolCallPart("run", {"args": ["brief"]}, tool_call_id=f"c{i}")]),
                    ModelRequest(parts=[ToolReturnPart("run", "B" * size, tool_call_id=f"c{i}")],
                                 instructions="I" * 50_000),
                    ModelResponse(parts=[TextPart(f"done {i}")])]
        return out

    def test_the_instructions_are_never_saved(self):
        from webapp import agent as agent_mod
        kept = agent_mod.compact(self.messages(2, 100), earlier=4)
        dumped = agent_mod.ModelMessagesTypeAdapter.dump_json(kept)
        self.assertNotIn(b"IIIII", dumped)
        self.assertEqual(len(kept), 8)
        self.assertEqual(agent_mod._usable(agent_mod.ModelMessagesTypeAdapter.validate_json(dumped)), kept)

    def test_a_long_conversation_keeps_this_turn_whole_and_shortens_earlier_results(self):
        from pydantic_ai.messages import ToolReturnPart
        from webapp import agent as agent_mod
        messages = self.messages(6, 90_000)
        kept = agent_mod.compact(messages, earlier=20)   # five earlier turns, and this one
        returns = [p for m in kept for p in getattr(m, "parts", []) if isinstance(p, ToolReturnPart)]
        self.assertEqual(len(returns), 6)                                # every call still has its result
        self.assertTrue(all(r.content.startswith("(an earlier result of 90,000") for r in returns[:5]))
        self.assertEqual(returns[5].content, "B" * 90_000)              # this turn's, whole
        self.assertLess(len(agent_mod.ModelMessagesTypeAdapter.dump_json(kept)), 110_000)   # this turn and little else

    def test_a_short_conversation_keeps_every_result(self):
        from pydantic_ai.messages import ToolReturnPart
        from webapp import agent as agent_mod
        kept = agent_mod.compact(self.messages(3, 5_000), earlier=8)
        self.assertTrue(all(p.content == "B" * 5_000 for m in kept for p in getattr(m, "parts", [])
                            if isinstance(p, ToolReturnPart)))


class HealthGate(AgentCase):
    """No page talks the agent out of a limit (0.76.0)."""
    OLD = ('+++\nschema = 6\n\n[[limits]]\narea = "knee"\nside = "left"\nlevel = "off-limits"\n+++\n\n'
           "## Clinician rules\n\n- No deep knee bends until March.\n")

    def setUp(self):
        super().setUp()
        with open(os.path.join(self.home, "health.md"), "w", encoding="utf-8") as f:
            f.write(self.OLD)

    def write(self, text):
        return tools.write_file(self.deps, "me/health.md", text)

    def test_the_check_in_may_loosen_before_the_turn_reads_any_page(self):
        r = self.write(self.OLD.replace('level = "off-limits"', 'level = "delicate"'))
        self.assertEqual(r.code, 0, r.error)

    def test_after_a_feed_or_a_search_a_limit_is_never_loosened(self):
        with mock.patch.object(tools.engine, "run", return_value=tools.engine.Result(0, "", "")):
            tools.run(self.deps, ["topics", "add", "F1"])
        self.assertTrue(self.deps.untrusted)
        for text, what in ((self.OLD.replace('level = "off-limits"', 'level = "delicate"'), "eased to delicate"),
                           (self.OLD.replace('level = "off-limits"', 'level = "off-limits"\ncleared = 2026-11-01'),
                            "lifted"),
                           (self.OLD.replace("- No deep knee bends until March.\n", ""), "clinician"),
                           ("no settings at all\n", "couldn't be read")):
            with self.subTest(what=what):
                r = self.write(text)
                self.assertNotEqual(r.code, 0)
                self.assertIn(what, r.error)
        with open(os.path.join(self.home, "health.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), self.OLD)

    def test_tightening_always_goes_through(self):
        self.deps.untrusted = True
        tighter = self.OLD.replace("+++\n\n## Clinician", '\n[[limits]]\narea = "shoulder"\nside = "right"\n'
                                   'level = "delicate"\n+++\n\n## Clinician')
        self.assertEqual(self.write(tighter).code, 0)

    def test_research_notes_count_as_pages(self):
        os.makedirs(os.path.join(self.home, "workouts", "research", "daily"), exist_ok=True)
        with open(os.path.join(self.home, "workouts", "research", "daily", "x.md"), "w", encoding="utf-8") as f:
            f.write("a page said the knee is fine")
        tools.read_file(self.deps, "me/workouts/research/daily/x.md")
        self.assertTrue(self.deps.untrusted)

    def test_the_writers_room_counts_as_pages(self):
        import asyncio
        import types
        from webapp import agent as agent_mod
        ctx = types.SimpleNamespace(deps=self.deps, model=None, usage=None)
        with mock.patch.object(agent_mod.writers, "write", side_effect=agent_mod.writers.NotReady("no brief")):
            asyncio.run(agent_mod._fill(ctx, "me/workouts/a/a.draft.txt", None, None))
        self.assertTrue(self.deps.untrusted)

    def test_a_scheduled_turn_never_changes_health(self):
        self.deps.scheduled_run = True
        r = self.write(self.OLD + "\nMore care today.\n")
        self.assertNotEqual(r.code, 0)
        self.assertIn("scheduled", r.error)
