"""The command line's inputs, checked where they come in: single settings (context.SCALARS) and a coach's kind,
a build's name (workouts.safe_name), what cli.run prints (scrubbed; "Interrupted."; SWEATCAST_DEBUG), the key
scrub when me/.env can't be read, a feed declaring entities, a caption download's size and shape, the Windows
lock's errors and key, an unreadable coach in migrate, and a damaged knowledge file read as the file's fault."""
import contextlib
import errno
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402,F401  (puts tools/ on the path)
import check  # noqa: E402
import cli  # noqa: E402
import context  # noqa: E402
import errors  # noqa: E402
import paths  # noqa: E402
import personas  # noqa: E402
import workouts  # noqa: E402

KEY = "sk-test-0123456789abcdef"


def capture(fn, *args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fn(*args)
    return code, out.getvalue(), err.getvalue()


class Home(unittest.TestCase):
    """A fresh copy of the template as the context folder."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.me = os.path.join(self.tmp, "me")
        shutil.copytree(paths.EXAMPLE, self.me)
        self.home = helpers.home(self.me)
        self.home.__enter__()

    def tearDown(self):
        self.home.__exit__(None, None, None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def set_setting(self, line, old=None, name="settings.toml"):
        path = os.path.join(self.me, name)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        text = text.replace(old, line, 1) if old else text + line + "\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


class Scalars(Home):
    BAD = ('cloud_max_chars = "5000"', "cloud_max_chars = true", "cloud_max_chars = -1", "cloud_max_chars = 2.5",
           "cloud_max_chars = 0")

    def test_each_bad_value_is_refused(self):
        for value in ("5000", True, -1, 2.5, 0, [1]):
            with self.subTest(value=value):
                found = context.scalar_problems({"cloud_max_chars": value})
                self.assertEqual([k for k, _, _ in found], ["cloud_max_chars"])
                self.assertFalse(found[0][2])   # an issue, not a note
        self.assertEqual(context.scalar_problems({"cloud_max_chars": 5000, "words_per_minute": 165,
                                                  "setup": "quick", "experience": ""}), [])
        for settings in ({"words_per_minute": 59}, {"words_per_minute": 301}, {"words_per_minute": True},
                         {"setup": "halfway"}, {"setup": 1}, {"experience": "expert"}, {"experience": 3}):
            with self.subTest(settings=settings):
                self.assertEqual(len(context.scalar_problems(settings)), 1)
        for settings in ({"setup": "Full"}, {"experience": " Advanced "}, {"words_per_minute": 60}):
            self.assertEqual(context.scalar_problems(settings), [], settings)

    def test_check_reports_each(self):
        for line in self.BAD:
            with self.subTest(line=line):
                shutil.rmtree(self.me)
                shutil.copytree(paths.EXAMPLE, self.me)
                self.set_setting(line)
                issues = [i for i in check._check_profile(paths.PROFILE) if "cloud_max_chars" in i.message]
                self.assertEqual(len(issues), 1, issues)
                self.assertFalse(issues[0].note)
                self.assertTrue(issues[0].path.endswith("settings.toml"))

    def test_check_reports_a_bad_experience_once(self):
        self.set_setting('experience = "expert"', old='experience = ""', name="profile.md")
        msgs = [i.message for i in check._check_profile(paths.PROFILE)]
        self.assertEqual(len([m for m in msgs if "experience" in m]), 1, msgs)

    def test_the_readers_refuse_rather_than_fall_back(self):
        for value in ("5000", True, -1, 2.5):
            p = context.Profile({"cloud_max_chars": value}, "", "profile.md")
            with self.assertRaises(errors.ContextError) as e:
                context.cloud_max_chars(p)
            self.assertIn("cloud_max_chars", str(e.exception))
        self.assertEqual(context.cloud_max_chars(context.Profile({}, "")), context.CLOUD_MAX_CHARS)
        self.assertEqual(context.cloud_max_chars(context.Profile({"cloud_max_chars": 900}, "")), 900)
        with self.assertRaises(errors.ContextError):
            context.wpm(context.Profile({"words_per_minute": "fast"}, ""))
        self.assertIsNone(context.wpm(context.Profile({}, "")))

    def test_get_wpm_exits_1_on_a_bad_value(self):
        self.set_setting("words_per_minute = 900", old="words_per_minute = 165")
        code, _, err = capture(cli.run, context.main, ["get", "wpm"])
        self.assertEqual(code, cli.ISSUES)
        self.assertIn("words_per_minute", err)


class CoachKind(Home):
    def persona(self, kind):
        return personas.Persona("coach-x", os.path.join(self.me, "coaches", "coach-x"), {"name": "Coach X", "kind": kind}, "")

    def test_kind_reads_any_case_and_refuses_a_typo(self):
        self.assertEqual(self.persona("Web").kind, "web")
        self.assertTrue(self.persona(" WEB ").is_web)
        self.assertEqual(self.persona("local").kind, "local")
        self.assertEqual(self.persona(None).kind, "local")
        for bad in ("wbe", "cloud", 1):
            with self.assertRaises(errors.CoachError):
                self.persona(bad).kind

    def test_check_reports_a_bad_kind(self):
        folder = os.path.join(self.me, "coaches", "coach-x")
        os.makedirs(folder)
        with open(os.path.join(folder, "persona.md"), "w", encoding="utf-8") as f:
            f.write('+++\nschema = 5\nname = "Coach X"\nkind = "wbe"\n+++\n')
        issues = [i for i in check.check_coaches(os.path.join(self.me, "coaches")) if "kind" in i.message]
        self.assertEqual(len(issues), 1)
        self.assertFalse(issues[0].note)


class SafeName(unittest.TestCase):
    def test_names_a_file_can_take(self):
        for name in ("Workout 2026-10-25 Strength 25 min", "smoke-test", "a.b", "Con game", "com10", "lpt0"):
            self.assertEqual(workouts.safe_name(name), name)

    def test_names_refused_everywhere(self):
        for name in ("Workout 1: Strength", "D:foo", "a/b", "a\\b", 'say "hi"', "a|b", "why?", "a*", "<x>",
                     "tab\there", "trailing.", "trailing ", ".", "..", "", "   ", "con", "CON.mp3", "Nul",
                     "com1", "LPT9.txt", "aux"):
            with self.subTest(name=name):
                with self.assertRaises(errors.UsageError):
                    workouts.safe_name(name)

    def test_build_refuses_a_colon_before_writing_anything(self):
        import sweatcast
        with tempfile.TemporaryDirectory() as d:
            me = os.path.join(d, "me")
            shutil.copytree(paths.EXAMPLE, me)
            with helpers.home(me):
                draft = os.path.join(paths.ROOT, "knowledge", "smoke-test.draft.txt")
                saved = sys.argv
                try:
                    code, _, err = capture(sweatcast.main, ["build", draft, "Workout 1: Strength", "--lint-only"])
                finally:
                    sys.argv = saved
                self.assertEqual(code, cli.USAGE)
                self.assertIn(":", err)
                written = [n for _, _, files in os.walk(me) for n in files if n.startswith("Workout 1")]
                self.assertEqual(written, [])
                self.assertFalse(os.path.exists(paths.LOGS))


class RouteFlag(Home):
    def test_route_and_its_older_name_engine_are_one_option(self):
        import build
        for flag in ("--route", "--engine"):
            with mock.patch.object(build, "run_build", return_value=mock.Mock(code=0)) as rb:
                capture(build.main, ["d.draft.txt", "n", flag, "fish"])
            self.assertEqual(rb.call_args[0][0].engine, "fish", flag)
        code, out, _ = capture(cli.run, context.main, ["get", "--help"])
        self.assertIn("--route", out)


class RunOutput(unittest.TestCase):
    def run_main(self, exc, env=None):
        def main():
            raise exc
        with mock.patch.dict(os.environ, {"FISH_AUDIO_API_KEY": KEY, **(env or {})}):
            if not env:
                os.environ.pop("SWEATCAST_DEBUG", None)
            return capture(cli.run, main)

    def test_every_message_is_scrubbed(self):
        for exc, code in ((cli.Usage(f"bad {KEY}"), cli.USAGE), (SystemExit(f"stop {KEY}"), cli.ISSUES),
                          (errors.ContextError(f"file {KEY}"), cli.ISSUES), (errors.UsageError(f"x {KEY}"), cli.USAGE)):
            with self.subTest(exc=type(exc).__name__):
                got, _, err = self.run_main(exc)
                self.assertEqual(got, code)
                self.assertNotIn(KEY, err)
                self.assertIn("<key>", err)

    def test_interrupted_says_so(self):
        got, _, err = self.run_main(KeyboardInterrupt())
        self.assertEqual(got, 130)
        self.assertIn("Interrupted.", err)

    def test_debug_adds_the_scrubbed_chain(self):
        try:
            try:
                raise OSError(f"disk said {KEY}")
            except OSError as cause:
                raise errors.ContextError("couldn't read it") from cause
        except errors.ContextError as e:
            exc = e
        got, _, err = self.run_main(exc)
        self.assertNotIn("Traceback", err)
        got, _, err = self.run_main(exc, env={"SWEATCAST_DEBUG": "1"})
        self.assertEqual(got, cli.ISSUES)
        self.assertIn("couldn't read it", err)
        self.assertIn("Traceback", err)
        self.assertIn("OSError", err)   # the chain, cause included
        self.assertNotIn(KEY, err)


class Redact(unittest.TestCase):
    def test_an_unreadable_env_file_still_scrubs_the_environment(self):
        import keys
        import redact
        with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": KEY}), \
                mock.patch.object(keys, "_read", side_effect=UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad")):
            self.assertEqual(redact.scrub(f"said {KEY}"), "said <key>")
        with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": KEY}), \
                mock.patch.object(keys, "_read", side_effect=PermissionError("locked")):
            self.assertEqual(redact.scrub(f"said {KEY}"), "said <key>")


class Feeds(unittest.TestCase):
    def test_a_feed_declaring_entities_is_refused(self):
        import datetime as dt
        import feeds
        since = dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc)
        bomb = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa">]><rss><channel></channel></rss>'
        for body in (bomb, bomb.decode(), b"<!ENTITY x 'y'><rss/>"):
            with self.assertRaises(ValueError):
                feeds.parse_rss(body, since)
        self.assertEqual(feeds.parse_rss(b"<rss><channel></channel></rss>", since), [])


class Captions(unittest.TestCase):
    def response(self, data):
        return io.BytesIO(data)

    def test_size_cap_and_shape(self):
        import feeds
        import youtube
        self.assertEqual(youtube.caption_events(self.response(b'{"events": [{"segs": []}, 3]}'), "u"),
                         [{"segs": []}])
        for bad in (b"[1, 2]", b"not json", b'{"events": "x"}', b"null"):
            with self.subTest(bad=bad), self.assertRaises(errors.SweatcastError):
                youtube.caption_events(self.response(bad), "u")
        with mock.patch.object(feeds, "MAX_BYTES", 10), self.assertRaises(errors.SweatcastError) as e:
            youtube.caption_events(self.response(b'{"events": []}' + b" " * 20), "u")
        self.assertIn("over", str(e.exception))


class Locks(unittest.TestCase):
    def test_the_key_folds_spellings(self):
        import locks
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.txt")
            self.assertEqual(locks.lock_key(path), locks.lock_key(os.path.join(d, ".", "a.txt")))
            if os.name == "nt":
                self.assertEqual(locks.lock_key(path), locks.lock_key(path.upper()))

    @unittest.skipUnless(os.name == "nt", "msvcrt is Windows only")
    def test_windows_retries_only_while_busy(self):
        import locks
        with tempfile.TemporaryFile() as f:
            with mock.patch.object(locks.msvcrt, "locking", side_effect=OSError(errno.EBADF, "bad")):
                with self.assertRaises(OSError):
                    locks.acquire(f)
            with mock.patch.object(locks.msvcrt, "locking", side_effect=OSError(errno.EACCES, "busy")):
                self.assertFalse(locks.acquire(f, block=False))


class Migrate(Home):
    def test_an_unreadable_coach_is_reported_and_left(self):
        import migrate
        folder = os.path.join(self.me, "coaches", "coach-broken")
        os.makedirs(folder)
        with open(os.path.join(folder, "persona.md"), "w", encoding="utf-8") as f:
            f.write("+++\nschema = 5\nname = \n+++\n")   # a settings block that won't parse
        due = migrate.coaches_due(self.me)
        self.assertIn(("unreadable", "coach-broken"), due)
        self.assertEqual(migrate.acting(due), [s for s in due if s[0] != "unreadable"])
        self.assertTrue(any("coach-broken" in line and "can't be read" in line
                            for line in migrate.coaches_lines(due)))
        code, out, err = capture(cli.run, migrate.main, ["--dry-run"])
        self.assertIn("coach-broken", err)
        self.assertTrue(os.path.isdir(folder))


class DamagedKnowledge(unittest.TestCase):
    def test_a_corrupt_sessions_or_content_file_is_a_context_error(self):
        import content
        import sessions
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "bad.toml")
            with open(bad, "w", encoding="utf-8") as f:
                f.write("[slot\n")
            for load in (sessions.load, content.recipe):
                with self.subTest(load=load.__module__), self.assertRaises(errors.ContextError):
                    load(bad)

    def test_content_plan_on_a_corrupt_recipe_exits_1(self):
        import content
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "content.toml")
            with open(bad, "w", encoding="utf-8") as f:
                f.write("[slot\n")
            me = os.path.join(d, "me")
            shutil.copytree(paths.EXAMPLE, me)
            with helpers.home(me), mock.patch.object(content.recipe, "__defaults__", (bad,)):
                code, _, err = capture(cli.run, content.main, ["plan", "--minutes", "20"])
        self.assertEqual(code, cli.ISSUES, err)
        self.assertIn("isn't valid TOML", err)


if __name__ == "__main__":
    unittest.main()
