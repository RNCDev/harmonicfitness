"""Routes: which audio route a build takes on this computer, from the profile's preference list."""
import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.setdefault("SWEATCAST_BACKEND", "mlx")

import context  # noqa: E402
import keys  # noqa: E402
import personas  # noqa: E402
import routes  # noqa: E402
from test_personas import persona_home  # noqa: E402

MAC = {"local": "fast", "local_engine": "mlx", "local_reason": ""}
PC_NO_GPU = {"local": "experimental", "local_engine": "cpu", "local_reason": ""}
INTEL_MAC = {"local": "no", "local_engine": "", "local_reason": "Neither MLX nor current PyTorch runs on an Intel Mac."}


class Routes(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.env = os.path.join(self.d, ".env")
        patches = [mock.patch.object(keys.paths, "ENV_FILE", self.env),
                   mock.patch.object(personas.paths, "PERSONAS", persona_home(self.d)),
                   mock.patch.dict(os.environ, {k: v for k, v in os.environ.items()
                                                if k not in keys.SERVICE_VARS.values()}, clear=True)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.coach = personas.lookup("Coach Test")

    def key(self, service):
        keys.init(service, path=self.env)
        with open(self.env, "a") as f:
            f.write(f"{keys.SERVICE_VARS[service]}=test-key\n")

    def test_first_usable_route_wins_on_faked_computers(self):
        with mock.patch.object(routes, "local_installed", return_value=True):
            self.assertEqual(routes.pick(["local", "fish"], self.coach, facts=MAC), "local")
        self.key("fish")
        with mock.patch.object(routes, "local_installed", return_value=False):   # no coach named: the list decides
            self.assertEqual(routes.pick(["local", "fish"], None, facts=PC_NO_GPU), "fish")
        with mock.patch.object(routes, "local_installed", return_value=True):
            self.assertEqual(routes.pick(["local", "fish"], None, facts=INTEL_MAC), "fish")

    def test_override_wins_and_must_be_usable(self):
        self.key("fish")
        with mock.patch.object(routes, "local_installed", return_value=True):
            self.assertEqual(routes.pick(["local"], None, override="fish", facts=MAC), "fish")
            with self.assertRaises(SystemExit) as e:
                routes.pick(["local"], None, override="elevenlabs", facts=MAC)
        self.assertIn("ELEVENLABS_API_KEY", str(e.exception.code))

    def test_no_usable_route_says_what_would_fix_it(self):
        with mock.patch.object(routes, "local_installed", return_value=False):
            with self.assertRaises(SystemExit) as e:
                routes.pick(["local", "fish"], None, facts=INTEL_MAC)
        message = str(e.exception.code)
        self.assertIn("Intel Mac", message)
        self.assertNotIn("render list", message)   # 10.0: the render list orders local engines only
        self.assertIn("I want a new coach", message)
        for name in ("Coach Reed", "Coach Ellis", "Coach Nolan", "Coach Owen"):
            self.assertIn(name, message)
        self.assertIn("./sweatcast keys init", message)
        with mock.patch.object(routes, "local_installed", return_value=False):
            with self.assertRaises(SystemExit) as e:
                routes.pick(["local", "fish"], self.coach, facts=INTEL_MAC)
        message = str(e.exception.code)
        self.assertIn("Intel Mac", message)
        self.assertIn("I want a new coach", message)
        self.assertEqual(message.count("local coach"), 1, message)   # said once

    def test_a_local_coach_where_local_doesnt_run_names_the_keyed_stand_in(self):
        self.key("fish")
        with mock.patch.object(routes, "local_installed", return_value=False):
            with self.assertRaises(SystemExit) as e:
                routes.pick(["fish"], self.coach, facts=INTEL_MAC)
        message = str(e.exception.code)
        self.assertIn("Coach Reed", message)
        self.assertIn(os.path.join("me.example", "personas", "coach-reed"), message)
        for other in ("Coach Ellis", "Coach Nolan", "Coach Owen"):   # no key for those
            self.assertNotIn(other, message)
        self.assertIn("I want a new coach", message)
        self.assertNotIn("No audio route works on this computer:\n  fish", message)

    def test_a_floor_doesnt_switch_off_an_installed_engine(self):
        low_disk = dict(MAC, local="no", local_hw="fast", local_reason="Only 2 GB is free here")
        with mock.patch.object(routes, "local_installed", return_value=True):
            self.assertEqual(routes.usable("local", self.coach, facts=low_disk), (True, ""))
        with mock.patch.object(routes, "local_installed", return_value=False):
            self.assertFalse(routes.usable("local", self.coach, facts=low_disk)[0])

    def test_local_needs_the_engine_installed(self):
        with mock.patch.object(routes, "local_installed", return_value=False):
            ok, reason = routes.usable("local", self.coach, facts=MAC)
        self.assertFalse(ok)
        self.assertIn("./sweatcast setup --local", reason)

    def web_coach(self, service="inworld", name="Coach Owen"):
        return personas.Persona(personas.slug(name), os.path.join(self.d, "x"),
                                {"name": name, "kind": "web", "service": service, "voice_id": "v1"}, "")

    def test_web_coach_routes_to_its_service_whatever_the_render_list(self):
        self.key("inworld")
        owen = self.web_coach()
        with mock.patch.object(routes, "local_installed", return_value=True):
            self.assertEqual(routes.pick(["local"], owen, facts=MAC), "inworld")
            self.assertEqual(routes.pick(["fish", "local"], owen, facts=MAC), "inworld")
            self.assertEqual(routes.pick(["local"], owen, override="inworld", facts=MAC), "inworld")

    def test_web_coach_without_key_says_which_key(self):
        owen = self.web_coach()
        with self.assertRaises(routes.WebCoachUnavailable) as e:
            routes.pick(["local"], owen, facts=MAC)
        message = str(e.exception.code)
        self.assertIsInstance(e.exception, SystemExit)
        self.assertIn("INWORLD_API_KEY", message)
        self.assertIn("keys init inworld", message)
        self.assertIn("Coach Owen", message)
        with mock.patch.object(routes.paths, "REMOTE", True):
            with self.assertRaises(routes.WebCoachUnavailable) as e:
                routes.pick(["local"], owen, facts=MAC)
        self.assertIn("environment", str(e.exception.code).lower())
        self.assertNotIn("keys init", str(e.exception.code))

    def test_engine_override_naming_another_service_is_refused(self):
        self.key("inworld")
        self.key("fish")
        with self.assertRaises(routes.WebCoachUnavailable) as e:
            routes.pick(["local"], self.web_coach(), override="fish", facts=MAC)
        self.assertIn("Inworld", str(e.exception.code))

    def test_local_coach_renders_only_locally(self):
        self.key("fish")
        ok, reason = routes.usable("fish", self.coach, facts=MAC)
        self.assertFalse(ok)
        self.assertIn("local coach", reason)
        with mock.patch.object(routes, "local_installed", return_value=False), self.assertRaises(SystemExit) as e:
            routes.pick(["fish"], self.coach, facts=INTEL_MAC)
        self.assertIn("local coach", str(e.exception.code))

    def test_way_out_only_where_local_voices_dont_run(self):
        with mock.patch.object(routes, "local_installed", return_value=False), self.assertRaises(SystemExit) as e:
            routes.pick(["local"], self.coach, facts=MAC)   # runs here, just not installed
        self.assertIn("./sweatcast setup --local", str(e.exception.code))
        self.assertNotIn("The way out", str(e.exception.code))
        with mock.patch.object(routes, "local_installed", return_value=False), self.assertRaises(SystemExit) as e:
            routes.pick(["local"], self.coach, facts=INTEL_MAC)
        self.assertIn("The way out", str(e.exception.code))

    def test_local_coach_tries_local_when_the_render_list_names_none(self):
        self.key("fish")
        with mock.patch.object(routes, "local_installed", return_value=True):
            self.assertEqual(routes.pick(["fish"], self.coach, facts=MAC), "local")
            self.assertEqual(routes.pick([], self.coach, facts=MAC), "local")

    def test_get_route_maps_a_missing_web_key_to_usage(self):
        import cli
        owen = self.web_coach()
        profile = context.Profile({"render": ["local"]}, "", "profile.md")
        with mock.patch.object(context, "profile", return_value=profile), \
                mock.patch.object(personas, "default", return_value=owen), \
                mock.patch.object(routes, "local_installed", return_value=True), \
                redirect_stderr(io.StringIO()) as err:
            self.assertEqual(context.main(["get", "route"]), cli.USAGE)
        self.assertIn("INWORLD_API_KEY", err.getvalue())

    def test_unknown_route_is_reported_and_skipped(self):
        err = io.StringIO()
        with mock.patch.object(routes, "local_installed", return_value=True), redirect_stderr(err):
            self.assertEqual(routes.pick(["fish-audio", "local"], self.coach, facts=MAC), "local")
        self.assertIn("fish-audio", err.getvalue())
        p = context.Profile({"render": ["fish-audio", "local"]}, "", "profile.md")
        self.assertEqual(context.routes(p), ["fish-audio", "local"])
        self.assertTrue(any("fish-audio" in i.message for i in context.route_issues(p)))

    def test_report_labels_services_not_tried_live(self):
        with mock.patch.object(routes, "local_installed", return_value=True):
            lines = "\n".join(routes.report_lines(self.coach, ["local"], MAC))
        self.assertRegex(lines, r"inworld .*key")
        self.assertNotRegex(lines, r"not yet tried live")
        self.assertIn("A build here would use: local", lines)

    def test_profile_defaults(self):
        p = context.Profile({}, "", "profile.md")
        self.assertEqual(context.routes(p), ["local"])
        self.assertEqual(context.cloud_max_chars(p), 30000)
        self.assertEqual(context.cloud_max_chars(context.Profile({"cloud_max_chars": 12000}, "", "")), 12000)


class Hosts(unittest.TestCase):
    def test_hosts(self):
        self.assertEqual(routes.hosts("fish"), ["api.fish.audio"])
        self.assertEqual(routes.hosts("elevenlabs"), ["api.elevenlabs.io"])
        self.assertEqual(routes.hosts("gemini"), ["generativelanguage.googleapis.com"])
        self.assertEqual(routes.hosts("inworld"), ["api.inworld.ai"])
        self.assertEqual(routes.hosts("local"), [])
        self.assertEqual(routes.ROUTES, ("local", "fish", "elevenlabs", "gemini", "inworld"))

    def test_feed_hosts_add_each_rss_host(self):
        p = context.Profile({"feeds": [{"label": "Local, Paper", "kind": "rss", "value": "https://news.example.org/rss"},
                                       {"label": "Weather", "kind": "weather", "value": "40.1, -75.2"}]}, "", "")
        got = routes.feed_hosts(p)
        self.assertIn("news.example.org", got)
        self.assertIn("api.open-meteo.com", got)


if __name__ == "__main__":
    unittest.main()
