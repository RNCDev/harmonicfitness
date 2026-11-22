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

from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart  # noqa: E402
from pydantic_ai.models.function import FunctionModel  # noqa: E402

from webapp import folder, hosted  # noqa: E402
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
        self.deps = self.fresh_deps()

    def fresh_deps(self):
        # as the worker sets it; the site's coach listing already read, and empty, so it refuses no coach by name
        # (the price's own check, on the voice, is what these tests meet)
        return tools.Deps(engine_root=ROOT, home=self.home, keys={}, today=TODAY,
                          now=f"{TODAY} Wednesday 08:00", writers="three", hosted_rows=[])


class Run(AgentCase):
    def test_a_command_that_fetches_pages_gets_no_key(self):
        self.deps.keys = {"FISH_AUDIO_API_KEY": "k" * 20, "TZ": "LCL-5"}
        with mock.patch.object(tools.engine, "run", return_value=tools.engine.Result(0, "", "")) as run:
            for args in (["topics", "add", "F1", "--feed", "https://example.org/feed"], ["youtube", "abc"],
                         ["content", "plan"], ["check"]):
                tools.run(self.deps, args)
        envs = {c.args[2][0]: c.kwargs["extra_env"] for c in run.call_args_list}
        self.assertEqual((envs["topics"], envs["youtube"], envs["content"]), ({"TZ": "LCL-5"},) * 3)   # the clock only
        self.assertEqual(envs["check"], {"FISH_AUDIO_API_KEY": "k" * 20, "TZ": "LCL-5"})

    def test_refuses_what_the_web_cant_do(self):
        """Commands the web can't run, a build without its coach, and paths outside the folder."""
        rows = [["setup"], ["keys", "init", "fish"], ["keys", "open"], ["migrate"], ["backup"],
                ["coaches", "audition", "me/coaches/.auditions/d.md", "--play"], ["coaches", "set"],
                ["coaches", "download"], ["coaches", "make"], ["cache", "prune"],
                ["build", "me/workouts/a/a.draft.txt", "A", "--follow"], [], ["rm", "-rf"]]
        rows.append(["build", "me/workouts/a/a.draft.txt", "A"])   # a build needs its coach
        rows += [["brief", "--save", bad] for bad in ("me/../../etc/passwd", "/etc/passwd", "../tools/paths.py",
                                                      "--save=/tmp/x", "--save=me/../x", "me/.env")]
        for args in rows:
            with self.subTest(args=args):
                self.assertEqual(tools.run(self.deps, args).code, 64)

    def fake_engine(self, speaks=3000, lint=0):
        from unittest import mock
        calls = []

        def run(root, home, argv, extra_env={}, timeout=120, cancel=None):
            calls.append((argv, timeout))
            if argv[:2] == ["get", "cost"]:
                return tools.engine.Result(0, json.dumps({"service": "openrouter", "model": hosted.VOICE_MODEL,
                                                          "chars": speaks, "usd": 0.045}), "")
            if "--max-chars" in argv and argv[argv.index("--max-chars") + 1] == "1":
                return tools.engine.Result(64, f"  the script speaks {speaks:,} characters; this build may send at most 1", "")
            if "--lint-only" in argv:
                return tools.engine.Result(lint, "lint ok" if lint == 0 else "a line is too long", "")
            return tools.engine.Result(0, "recorded", "")
        return mock.patch.object(tools.engine, "run", side_effect=run), calls

    BUILD = ["build", "me/workouts/a/a.draft.txt", "Workout A", "--coach", "Coach Reed"]

    def test_a_build_without_its_approval_is_priced_and_offered_first(self):
        for approved in (None,   # an approval is for its own draft and coach
                         {"draft": "me/workouts/a/a.draft.txt", "coach": "Coach Ellis", "chars": 3000}):
            with self.subTest(approved=approved):
                self.deps = self.fresh_deps()
                self.deps.approved = approved
                patch, calls = self.fake_engine()
                with patch:
                    r = tools.run(self.deps, list(self.BUILD))
                self.assertIn("Not recorded yet", r.output)
                self.assertEqual(self.deps.offer, {"draft": "me/workouts/a/a.draft.txt", "name": "Workout A",
                                                   "coach": "Coach Reed", "chars": 3000, "usd": 0.045,
                                                   "service": "openrouter", "design": False, "minutes": 5})
                self.assertFalse(any("--lint-only" not in a and a[0] == "build" for a, _ in calls))   # nothing recorded

    def test_nothing_is_offered_after_a_lint_problem_or_over_todays_allowance(self):
        for lint, chars_left, code in ((1, None, 1), (0, 1000, 64)):
            with self.subTest(lint=lint, chars_left=chars_left):
                self.deps = self.fresh_deps()
                if chars_left is not None:
                    self.deps.chars_left = chars_left
                patch, calls = self.fake_engine(lint=lint)
                with patch:
                    r = tools.run(self.deps, list(self.BUILD))
                self.assertEqual(r.code, code)
                self.assertIsNone(self.deps.offer)
                if lint:
                    self.assertEqual(len(calls), 1)   # the lint is fixed before any price
                else:
                    self.assertIn("today's allowance", r.error)

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


class Files(AgentCase):
    def test_read_write_and_list_mine(self):
        with open(os.path.join(self.home, ".env"), "w", encoding="utf-8") as f:
            f.write("X=1\n")
        self.assertIn("+++", tools.read_file(self.deps, "me/profile.md").output)
        for path, code in (("knowledge/script.md", 0), (".claude/skills/workout/SKILL.md", 0), ("me/nothing.md", 1)):
            with self.subTest(read=path):
                self.assertEqual(tools.read_file(self.deps, path).code, code)
        r = tools.write_file(self.deps, f"me/workouts/{STEM}/{STEM}.draft.txt", "movements: none\n")
        self.assertEqual(r.code, 0, r.error)
        self.assertIn(f"me/workouts/{STEM}/{STEM}.draft.txt", tools.list_files(self.deps, "me/workouts").output)
        listing = tools.list_files(self.deps).output
        self.assertIn("me/profile.md", listing)
        self.assertNotIn(".env", listing)   # skipped files are hidden

    def test_read_refuses_the_rest(self):
        with open(os.path.join(self.home, ".env"), "w", encoding="utf-8") as f:
            f.write("FISH_AUDIO_API_KEY=secret-value-here\n")
        os.symlink("/etc/hosts", os.path.join(self.home, "out.md"))
        for bad in ("me/.env", "tools/paths.py", "CLAUDE.md", "knowledge/../tools/paths.py", "me/../x",
                    "/etc/passwd", "web/webapp/config.py", "me/out.md"):   # the last a symlink out
            with self.subTest(bad=bad):
                r = tools.read_file(self.deps, bad)
                self.assertEqual(r.code, 64)
                self.assertNotIn("secret-value-here", r.output + r.error)

    def test_write_refuses(self):
        for bad in ("me/.env", "me/a.mp3", "tools/x.py", "me/../x.md", "knowledge/x.md", "me/",
                    "me/coaches/coach-dana-fish/sample.mp3"):   # kept, but the engine's to make
            self.assertEqual(tools.write_file(self.deps, bad, "x").code, 64, bad)
        self.assertEqual(tools.write_file(self.deps, "me/big.md", "x" * (tools.WRITE_LIMIT + 1)).code, 64)


class Turns(AgentCase):
    def test_every_story_a_long_session_told_is_logged(self):
        """A 40-minute session's 36 stories went over the command's argument cap in one content log and none was
        recorded, so the next day's retold them (2026-11-22): the site logs every one, in batches under it."""
        draft = f"me/workouts/{STEM}/{STEM}.draft.txt"
        items = [f"- | quick_hit | Story {n} | https://example.org/{n}" for n in range(40)]
        self.deps.told = {"draft": draft, "items": items}
        calls = []

        def run(root, home, argv, **kw):
            calls.append(argv)
            return tools.engine.Result(0, "Recorded.", "")
        with mock.patch.object(tools.engine, "run", side_effect=run):
            out = agent.log_after(self.deps, {}, draft, tools.ToolResult(code=0, output="built"))
        logged = [a[i + 1] for a in calls if a[:2] == ["content", "log"] for i, x in enumerate(a) if x == "--item"]
        self.assertEqual(logged, items)
        self.assertIn("logged the 40 stories", out.output)

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


class Prefetch(AgentCase):
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
                return tools.engine.Result(0, json.dumps({"service": "openrouter", "model": hosted.VOICE_MODEL,
                                                          "chars": 3000, "usd": 0.05}), "")
            if "--max-chars" in argv and argv[argv.index("--max-chars") + 1] == "1":
                return tools.engine.Result(1, "  the script speaks 3,000 characters; this build may send at most 1", "")
            if "--lint-only" in argv:
                return tools.engine.Result(0, "lint ok\nSends 3,000 characters to the voice service" if sends else "lint ok", "")
            return tools.engine.Result(0, "recorded", "")
        return mock.patch.object(tools.engine, "run", side_effect=run), calls


class Research(DraftCase):
    """A failed research call never fails the turn (0.79.0): the places get coaching only."""
    SKELETON = ("movements: air-squat\n\n@@ 30 | Welcome\n\n@@ 60 | Squats\n[count 3 go]\n\n"
                "@@ 60 | Rest after squats\n\n@@ 30 | Close\n")
    REPORT = ("Skeleton: 4 segments, 180 s. Word budgets with Coach Freya (about 147 words a minute):\n"
              "  #  secs budget words to write  label\n  1    30     70     0       70  Welcome\n"
              "  2    60    140     0      140  Squats\n  3    60    140     0      140  Rest after squats\n"
              "  4    30     70     0       70  Close\n")

    def skeleton(self):
        tools.write_file(self.deps, self.DRAFT, self.SKELETON)
        tools.write_file(self.deps, "me/workouts/a/a.brief.md", "# Brief\n\n## The listener\n\nSam.\n\n## Today's limits\n\nNone.\n")
        self.deps.reports[self.DRAFT] = self.REPORT

    def room(self, researcher):
        """The room's models: `researcher` answers (or raises) for the researcher, the others reply with nothing."""
        from pydantic_ai.models.function import AgentInfo
        from webapp.agent import writers
        prompts = []

        def reply(messages, info: AgentInfo):
            props = info.output_tools[0].parameters_json_schema["properties"]
            if "stories" in props:
                return researcher()
            prompts.append(messages[-1].parts[-1].content)
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"segments": []})])
        return writers, FunctionModel(reply), prompts

    def written(self, researcher, early_failed=False):
        """The room written with `researcher`; the worker's log lines, or the error the room raised."""
        import asyncio
        from concurrent.futures import Future
        from pydantic_ai.usage import RunUsage
        self.skeleton()
        lines = []
        self.deps.log = lines.append
        if early_failed:   # the researcher started as the brief was saved, and failed
            job = Future()
            job.set_exception(RuntimeError("504"))
            self.deps.content_job, self.deps.content_for = job, self.DRAFT
        writers, model, _ = self.room(researcher)
        patch, calls = self.fake()
        with patch:
            asyncio.run(writers.write(self.deps, model, RunUsage(), self.DRAFT, name="Workout A", coach="Coach Freya"))
        return lines

    def test_a_refused_key_a_quota_or_a_usage_limit_stops_the_turn(self):
        from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded
        rows = [(ModelHTTPError, (status, "google/gemini", body))
                for status, body in ((401, {"error": "bad key"}), (403, {"error": "no"}),
                                     (429, {"error": "you exceeded your current quota"}),
                                     (400, {"error": "billing hard limit reached"}))]
        rows.append((UsageLimitExceeded, ("too many requests",)))
        for kind, args in rows:
            def refused(kind=kind, args=args):
                raise kind(*args)
            with self.subTest(error=kind.__name__, args=args), self.assertRaises(kind):
                self.written(refused)

    def test_stop_still_stops_the_room_while_research_is_written(self):
        import asyncio
        from pydantic_ai.usage import RunUsage
        self.skeleton()

        def stopped():
            raise asyncio.CancelledError()
        writers, model, _ = self.room(stopped)
        patch, _ = self.fake()
        with patch, self.assertRaises(asyncio.CancelledError):
            asyncio.run(writers.write(self.deps, model, RunUsage(), self.DRAFT, name="Workout A", coach="Coach Freya"))


class Faster(DraftCase):
    """0.48.0: fewer round trips and smaller fixes on the way to a priced script."""

    BUILD = ["build", "me/workouts/a/a.draft.txt", "Workout A", "--coach", "Coach Ruby"]

    def test_the_lint_s_own_count_prices_the_script(self):
        self.draft()
        patch, calls = self.fake()
        with patch:
            r = tools.run(self.deps, list(self.BUILD))
        self.assertIn("Not recorded yet", r.output)
        self.assertEqual(self.deps.offer["chars"], 3000)
        self.assertFalse(any("--max-chars" in a for a in calls))   # one lint, then the price, nothing more
        self.assertEqual(len(counted(calls)), 2)

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

    LATER = {"at": "2026-11-04T12:00:00+00:00", "local": "2026-11-04 Wednesday 07:00", "offset": -300}

    def test_a_workout_for_later_records_on_its_own_only_within_its_ceiling(self):
        for ceiling in (4000, 2500):
            with self.subTest(ceiling=ceiling):
                self.deps = self.fresh_deps()
                self.draft()
                reserved = []
                self.deps.later, self.deps.scheduled_run = dict(self.LATER), True
                self.deps.auto_record, self.deps.ceiling = True, ceiling
                self.deps.reserve = lambda chars: reserved.append(chars) or True
                patch, calls = self.fake()
                with patch:
                    out = agent.run_turn(FunctionModel(self.turn_that_builds()), self.deps, None, "go")
                if ceiling == 4000:
                    self.assertEqual((reserved, self.deps.recorded), ([3000], self.DRAFT))
                    self.assertIn(agent.SCHEDULED_RECORDED, out.history_json.replace("\\n", "\n"))
                else:
                    self.assertEqual((reserved, self.deps.recorded), ([], None))
                    self.assertEqual(self.deps.offer["chars"], 3000)   # the Record button, with its real price
                    self.assertIn("longer than the listener approved", out.history_json)

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


class Instructions(AgentCase):
    def test_the_web_wording_names_no_key_file(self):
        with open(os.path.join(ROOT, "web/webapp/agent/instructions.md"), encoding="utf-8") as f:
            lines = [line for line in f if ".env" in line]
        self.assertEqual(len(lines), 1)   # only the rule never to read or write it
        self.assertIn("Never read or write `me/.env`", lines[0])
        self.assertIn("stored encrypted on this site", agent.PREAMBLE)


class TurnClock(AgentCase):
    def test_past_its_time_the_turn_stops_the_engine_command_in_it_too(self):
        import asyncio
        self.deps.cancel = threading.Event()

        async def slow(messages, info):
            await asyncio.sleep(1.0)
            return ModelResponse(parts=[TextPart("Hello.")])
        with mock.patch.object(agent, "TURN_SECONDS", 0.1):
            with self.assertRaises(agent.TurnError) as caught:
                agent.run_turn(FunctionModel(slow), self.deps, None, "go")
        self.assertEqual(caught.exception.reason, agent.TIMED_OUT)   # not "stopped", though the stop is set
        self.assertTrue(self.deps.cancel.is_set())                   # a running build is killed, not left sending

    def test_stop_during_a_request_stops_the_turn(self):
        import asyncio
        self.deps.cancel = threading.Event()

        async def slow(messages, info):
            self.deps.cancel.set()   # the listener presses Stop while the model thinks
            await asyncio.sleep(1.0)
            return ModelResponse(parts=[TextPart("Hello.")])
        with self.assertRaises(agent.TurnError) as caught:
            agent.run_turn(FunctionModel(slow), self.deps, None, "go")
        self.assertEqual(caught.exception.reason, agent.STOPPED)


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

    def test_what_goes_through(self):
        """The check-in may change health and loosen before the turn reads any page; tightening always goes through."""
        tighter = self.OLD.replace("+++\n\n## Clinician", '\n[[limits]]\narea = "shoulder"\nside = "right"\n'
                                   'level = "delicate"\n+++\n\n## Clinician')
        for what, untrusted, text in (
                ("plain", False, "+++\nschema = 6\n+++\n"),
                ("loosened before any page", False, self.OLD.replace('level = "off-limits"', 'level = "delicate"')),
                ("tightened after a page", True, tighter)):
            with self.subTest(what=what):
                self.deps.untrusted = untrusted
                r = self.write(text)
                self.assertEqual(r.code, 0, r.error)
                with open(os.path.join(self.home, "health.md"), "w", encoding="utf-8") as f:
                    f.write(self.OLD)

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

    def test_research_notes_and_the_writers_room_count_as_pages(self):
        import asyncio
        import types
        from webapp import agent as agent_mod
        os.makedirs(os.path.join(self.home, "workouts", "research", "daily"), exist_ok=True)
        with open(os.path.join(self.home, "workouts", "research", "daily", "x.md"), "w", encoding="utf-8") as f:
            f.write("a page said the knee is fine")

        def notes():
            tools.read_file(self.deps, "me/workouts/research/daily/x.md")

        def room():
            ctx = types.SimpleNamespace(deps=self.deps, model=None, usage=None)
            with mock.patch.object(agent_mod.writers, "write", side_effect=agent_mod.writers.NotReady("no brief")):
                asyncio.run(agent_mod._fill(ctx, "me/workouts/a/a.draft.txt", None, None))
        for name, read in (("research notes", notes), ("writers' room", room)):
            with self.subTest(name):
                self.deps = self.fresh_deps()
                read()
                self.assertTrue(self.deps.untrusted)

    def test_a_scheduled_turn_never_changes_health(self):
        self.deps.scheduled_run = True
        r = self.write(self.OLD + "\nMore care today.\n")
        self.assertNotEqual(r.code, 0)
        self.assertIn("scheduled", r.error)


if __name__ == "__main__":
    unittest.main()
