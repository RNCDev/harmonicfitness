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
        with mock.patch.object(routes, "local_installed", return_value=False):
            self.assertEqual(routes.pick(["local", "fish"], self.coach, facts=PC_NO_GPU), "fish")
        with mock.patch.object(routes, "local_installed", return_value=True):
            self.assertEqual(routes.pick(["local", "fish"], self.coach, facts=INTEL_MAC), "fish")

    def test_override_wins_and_must_be_usable(self):
        self.key("fish")
        with mock.patch.object(routes, "local_installed", return_value=True):
            self.assertEqual(routes.pick(["local"], self.coach, override="fish", facts=MAC), "fish")
            with self.assertRaises(SystemExit) as e:
                routes.pick(["local"], self.coach, override="elevenlabs", facts=MAC)
        self.assertIn("ELEVENLABS_API_KEY", str(e.exception.code))

    def test_no_usable_route_says_what_would_fix_it(self):
        with mock.patch.object(routes, "local_installed", return_value=False):
            with self.assertRaises(SystemExit) as e:
                routes.pick(["local", "fish"], self.coach, facts=INTEL_MAC)
        message = str(e.exception.code)
        self.assertIn("Intel Mac", message)
        self.assertIn("./sweatcast keys init fish", message)

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

    def test_deepgram_needs_a_stock_voice(self):
        self.key("deepgram")
        ok, reason = routes.usable("deepgram", self.coach, facts=MAC)
        self.assertFalse(ok)
        self.assertIn("samples deepgram", reason)
        context.set_persona_setting(self.coach.path, "deepgram", "voice", "aura-2-apollo-en")
        self.assertEqual(routes.usable("deepgram", personas.lookup("Coach Test"), facts=MAC), (True, ""))

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
        self.assertRegex(lines, r"elevenlabs .*not yet tried live")
        self.assertIn("A build here would use: local", lines)

    def test_profile_defaults(self):
        p = context.Profile({}, "", "profile.md")
        self.assertEqual(context.routes(p), ["local"])
        self.assertEqual(context.cloud_max_chars(p), 30000)
        self.assertEqual(context.cloud_max_chars(context.Profile({"cloud_max_chars": 12000}, "", "")), 12000)


if __name__ == "__main__":
    unittest.main()
