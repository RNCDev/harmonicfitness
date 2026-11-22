"""Routes: which audio route a build takes on this computer, from the coach and the profile's preference list."""
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

import cli  # noqa: E402
import coachpick  # noqa: E402
import context  # noqa: E402
import errors  # noqa: E402
import keys  # noqa: E402
import personas  # noqa: E402
import routes  # noqa: E402

MAC = {"local": "fast", "local_engine": "mlx", "local_reason": ""}
PC_NO_GPU = {"local": "experimental", "local_engine": "cpu", "local_reason": ""}
INTEL_MAC = {"local": "no", "local_engine": "", "local_reason": "Neither MLX nor current PyTorch runs on an Intel Mac."}


class Routes(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.env = os.path.join(self.d, ".env")
        os.makedirs(os.path.join(self.d, "coaches"))   # none of the listener's own: the stock fixture coaches
        patches = [mock.patch.object(keys.paths, "ENV_FILE", self.env),
                   mock.patch.object(personas.paths, "PERSONAS", os.path.join(self.d, "coaches")),
                   mock.patch.dict(os.environ, {k: v for k, v in os.environ.items()
                                                if k not in keys.SERVICE_VARS.values()}, clear=True)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.coach = personas.lookup("Coach Test")

    def key(self, service):
        keys.init(service, path=self.env)
        with open(self.env, "a", encoding="utf-8") as f:
            f.write(f"{keys.SERVICE_VARS[service]}=test-key\n")

    def web_coach(self, service="inworld", name="Coach Owen"):
        return personas.Persona(personas.slug(name), os.path.join(self.d, "x"),
                                {"name": name, "kind": "web", "service": service, "voice_id": "v1"}, "")

    def test_first_usable_route_wins(self):
        with mock.patch.object(routes, "local_installed", return_value=True):
            self.assertEqual(coachpick.pick(["local", "fish"], self.coach, facts=MAC), "local")
            err = io.StringIO()
            with redirect_stderr(err):   # an unknown route is reported and skipped
                self.assertEqual(coachpick.pick(["fish-audio", "local"], self.coach, facts=MAC), "local")
            self.assertIn("fish-audio", err.getvalue())
        self.key("fish")
        with mock.patch.object(routes, "local_installed", return_value=False):   # no coach named: the list decides
            self.assertEqual(coachpick.pick(["local", "fish"], None, facts=PC_NO_GPU), "fish")
            ok, reason = routes.usable("local", self.coach, facts=MAC)   # local needs the engine installed
            self.assertFalse(ok)
            self.assertIn("./harmonicfitness setup --local", reason)
        with mock.patch.object(routes, "local_installed", return_value=True):
            self.assertEqual(coachpick.pick(["local", "fish"], None, facts=INTEL_MAC), "fish")

    def test_a_coach_speaks_only_through_its_own_route(self):
        """A web coach never renders locally, and a local coach's script is never sent to a web service."""
        self.key("inworld")
        self.key("fish")
        owen = self.web_coach()
        with mock.patch.object(routes, "local_installed", return_value=True):
            self.assertEqual(coachpick.pick(["local"], owen, facts=MAC), "inworld")
            self.assertEqual(coachpick.pick(["fish", "local"], owen, facts=MAC), "inworld")
            self.assertEqual(coachpick.pick(["fish"], self.coach, facts=MAC), "local")
        ok, reason = routes.usable("fish", self.coach, facts=MAC)
        self.assertFalse(ok)
        self.assertIn("local coach", reason)
        with mock.patch.object(routes, "local_installed", return_value=False), self.assertRaises(errors.PROBLEMS) as e:
            coachpick.pick(["fish"], self.coach, facts=INTEL_MAC)
        self.assertIn("local coach", str(e.exception.code))

    def test_an_override_cant_switch_a_coachs_service(self):
        self.key("inworld")
        self.key("fish")
        with mock.patch.object(routes, "local_installed", return_value=True):
            self.assertEqual(coachpick.pick(["local"], None, override="fish", facts=MAC), "fish")
            with self.assertRaises(errors.PROBLEMS) as e:   # an override must be usable
                coachpick.pick(["local"], None, override="elevenlabs", facts=MAC)
            self.assertIn("ELEVENLABS_API_KEY", str(e.exception.code))
            self.assertEqual(coachpick.pick(["local"], self.web_coach(), override="inworld", facts=MAC), "inworld")
        with self.assertRaises(routes.WebCoachUnavailable) as e:
            coachpick.pick(["local"], self.web_coach(), override="fish", facts=MAC)
        self.assertIn("Inworld", str(e.exception.code))

    def test_download_refused_in_the_web_client(self):
        import coaches
        with mock.patch.object(coaches.paths, "WEB", True), \
                mock.patch.object(coaches.voices, "download") as dl, redirect_stderr(io.StringIO()):
            self.assertEqual(coaches.main(["download"]), 64)
        dl.assert_not_called()

    def test_a_web_coach_without_its_key_says_which_key(self):
        owen = self.web_coach()
        with self.assertRaises(routes.WebCoachUnavailable) as e:
            coachpick.pick(["local"], owen, facts=MAC)
        message = str(e.exception.code)
        self.assertIsInstance(e.exception, errors.UsageError)   # exit 64, and caught as any engine problem
        self.assertNotIsInstance(e.exception, SystemExit)
        for words in ("INWORLD_API_KEY", "keys init inworld", "Coach Owen"):
            self.assertIn(words, message)
        with mock.patch.object(routes.paths, "REMOTE", True):
            with self.assertRaises(routes.WebCoachUnavailable) as e:
                coachpick.pick(["local"], owen, facts=MAC)
        self.assertIn("environment", str(e.exception.code).lower())
        self.assertNotIn("keys init", str(e.exception.code))
        with mock.patch.object(routes.paths, "WEB", True):
            for text in (routes.missing_key(owen), routes.way_out()):
                self.assertIn("Coaches page", text)   # the site's coaches: no key of the listener's to add
                self.assertNotIn("keys init", text)
        profile = context.Profile({"render": ["local"]}, "", "profile.md")
        with mock.patch.object(context, "profile", return_value=profile), \
                mock.patch.object(coachpick, "default", return_value=owen), \
                mock.patch.object(routes, "local_installed", return_value=True), \
                redirect_stderr(io.StringIO()) as err:
            self.assertEqual(cli.run(lambda: context.main(["get", "route"])), cli.USAGE)
        self.assertIn("INWORLD_API_KEY", err.getvalue())


if __name__ == "__main__":
    unittest.main()
