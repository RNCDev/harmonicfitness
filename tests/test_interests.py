"""What the listener has shown they like: evidence, strength, fading, the Learned sections (tools/interests.py)."""
import datetime
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import content  # noqa: E402
import context  # noqa: E402
import helpers  # noqa: E402
import interests  # noqa: E402
import paths  # noqa: E402

TODAY = datetime.date(2026, 11, 1)
T = interests.Tuning()


def sig(kind, name, weight, days_ago=0, **extra):
    return dict({"kind": kind, "name": name, "weight": weight,
                 "date": (TODAY - datetime.timedelta(days=days_ago)).isoformat(), "source": "mention"}, **extra)


def prof(body=""):
    return context.Profile({}, body, None)


class Strength(unittest.TestCase):
    def test_a_signal_halves_every_half_life(self):
        for days, want in ((0, 1.0), (90, 0.5), (180, 0.25)):
            s = interests.strengths([sig("topic", "Jazz", 1, days)], TODAY, T)
            self.assertAlmostEqual(s[("topic", "jazz")].strength, want, places=6)

    def test_signals_add_up_and_a_child_feeds_its_parent(self):
        s = interests.strengths([sig("topic", "Atsuko Okatsuka", 1, parent="stand-up comedy"),
                                 sig("topic", "Ali Wong", 1, parent="Stand-up comedy"),
                                 sig("topic", "Ali Wong", 1, 0)], TODAY, T)
        self.assertAlmostEqual(s[("topic", "ali wong")].strength, 2.0)
        self.assertAlmostEqual(s[("topic", "stand-up comedy")].strength, T.parent_share * 3)   # one parent, either case

    def test_a_one_off_fades_out_in_about_five_months_and_a_regular_stays(self):
        once = [sig("topic", "Lilia", 1, 150)]
        self.assertTrue(interests.learned(prof(), TODAY, once, T).topics)
        self.assertFalse(interests.learned(prof(), TODAY, [sig("topic", "Lilia", 1, 160)], T).topics)
        monthly = [sig("topic", "Comedy", 1, d) for d in range(0, 365, 30)]
        self.assertGreater(interests.learned(prof(), TODAY, monthly, T).topics[0].strength, 3)

    def test_pinned_topics_are_never_learned_twice_and_never_drop(self):
        p = prof("## Topics\n- Jazz: new records\n")
        lr = interests.learned(p, TODAY, [sig("topic", "jazz", 1), sig("topic", "Blues", 1)], T)
        self.assertEqual([x.name for x in lr.topics], ["Blues"])
        self.assertAlmostEqual(lr.strength["jazz"], 2.0)
        lr = interests.learned(p, TODAY, [sig("topic", "Jazz", -2)], T)
        self.assertEqual(lr.strength["jazz"], 0.25)   # weakened, never gone
        self.assertEqual(interests.learned(p, TODAY, [], T).strength["jazz"], 1.0)

    def test_never_bring_up_beats_anything_learned(self):
        p = prof("## Never bring up\n- crypto\n- [a hint]\n")
        lr = interests.learned(p, TODAY, [sig("topic", "Crypto markets", 2), sig("venue", "Crypto.com Arena", 2),
                                          sig("topic", "Jazz", 1)], T)
        self.assertEqual([x.name for x in lr.topics], ["Jazz"])
        self.assertEqual(lr.venues, [])

    def test_a_dislike_needs_firmer_evidence_than_a_like(self):
        lr = interests.learned(prof(), TODAY, [sig("movement", "burpee", -1, 60), sig("movement", "goblet squat", 1, 60)], T)
        self.assertEqual(lr.likes, ["goblet squat"])   # 0.63: a like
        self.assertEqual(lr.dislikes, [])               # -0.63: not yet a dislike
        lr = interests.learned(prof(), TODAY, [sig("movement", "burpee", -2, 60)], T)
        self.assertEqual(lr.dislikes, ["burpee"])

    def test_effort_leans_and_fades(self):
        self.assertEqual(interests.lean(interests.learned(prof(), TODAY, [sig("effort", "effort", 1)], T)), "harder")
        self.assertIsNone(interests.lean(interests.learned(prof(), TODAY, [sig("effort", "effort", 1, 60)], T)))
        self.assertEqual(interests.lean(interests.learned(prof(), TODAY, [sig("effort", "effort", -1),
                                                                          sig("effort", "effort", -1, 90)], T)), "easier")


class Signals(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(interests.parse_signal("topic | Ali Wong | 1 | stand-up comedy | saw her special"),
                         {"kind": "topic", "name": "Ali Wong", "weight": 1.0, "parent": "stand-up comedy",
                          "note": "saw her special"})
        self.assertEqual(interests.parse_signal("Effort | too easy | 1")["name"], "effort")
        for bad in ("topic | Jazz", "mood | Jazz | 1", "topic | Jazz | 3", "topic | Jazz | 0", "topic |  | 1",
                    "topic | Jazz | lots"):
            with self.assertRaises(ValueError, msg=bad):
                interests.parse_signal(bad)


class Record(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="hf-interests-")
        self.addCleanup(shutil.rmtree, self.root, True)
        shutil.copytree(paths.EXAMPLE, self.root, dirs_exist_ok=True)
        self.ctx = helpers.home(self.root)
        self.ctx.__enter__()
        self.addCleanup(self.ctx.__exit__, None, None, None)

    def test_add_caps_one_event_and_a_key_replaces(self):
        many = [interests.parse_signal(f"topic | T{i} | 1") for i in range(T.per_event_max + 1)]
        with self.assertRaises(ValueError):
            interests.add(many, "feedback")
        interests.rating("b1", "positive", ["Jazz", "Jazz", "-", "Comedy"])
        interests.rating("b1", "negative", ["Jazz"])
        rows = interests.evidence()
        self.assertEqual([(r["name"], r["weight"], r["key"]) for r in rows], [("Jazz", -T.rating_weight, "rating:b1")])
        interests.rating("b1", "none", ["Jazz"])
        self.assertEqual(interests.evidence(), [])

    def test_a_rating_is_a_small_signal_on_the_topics_its_workout_told(self):
        import types
        import fileio
        import workoutlog
        fileio.append_jsonl(paths.TOLD, [{"date": "2026-10-31", "topic": "Jazz", "format": "quick_hit", "title": "a",
                                          "build": "b9"},
                                         {"date": "2026-10-31", "topic": "Comedy", "format": "quick_hit", "title": "b",
                                          "build": "other"}])
        workoutlog._rating_signals(types.SimpleNamespace(build_id="b9"), "positive")
        self.assertEqual([(r["name"], r["weight"]) for r in interests.evidence()], [("Jazz", T.rating_weight)])
        workoutlog._rating_signals(types.SimpleNamespace(build_id=None), "positive")   # no build: nothing to tie it to
        self.assertEqual(len(interests.evidence()), 1)

    def test_forget_and_a_deleted_workout_take_their_evidence_back(self):
        interests.add([interests.parse_signal("topic | Jazz | 1"), interests.parse_signal("venue | Bell House | 1")],
                      "feedback", build="b2")
        interests.add([interests.parse_signal("topic | Jazz | 1")], "mention")
        self.assertEqual(interests.forget_builds(["b2"]), 2)
        self.assertEqual(interests.forget("JAZZ"), 1)
        self.assertEqual(interests.evidence(), [])

    def test_apply_writes_its_own_section_and_leaves_theirs(self):
        with open(paths.CONTENT_MD, encoding="utf-8") as f:
            before = f.read()
        interests.add([interests.parse_signal("topic | Atsuko Okatsuka | 1 | stand-up comedy | saw her at the Bell House"),
                       interests.parse_signal("venue | The Bell House | 1"),
                       interests.parse_signal("movement | goblet squat | 1"),
                       interests.parse_signal("effort | x | 1")], "mention")
        interests.apply()
        with open(paths.CONTENT_MD, encoding="utf-8") as f:
            after = f.read()
        self.assertTrue(after.startswith(before.rstrip("\n")))   # theirs untouched, ours after it
        self.assertIn("## Learned from you", after)
        self.assertIn("- Atsuko Okatsuka (part of stand-up comedy): strength 1.0", after)
        self.assertIn("- stand-up comedy: strength 0.5, from what's under it", after)
        self.assertIn("The Bell House", after)
        with open(paths.TRAINING, encoding="utf-8") as f:
            training = f.read()
        self.assertIn("- Liked lately: goblet squat", training)
        self.assertIn("aiming a little harder", training)
        interests.apply()   # again: the same, not a second section
        with open(paths.CONTENT_MD, encoding="utf-8") as f:
            self.assertEqual(f.read(), after)
        interests.forget("Atsuko Okatsuka")
        interests.forget("The Bell House")
        interests.forget("stand-up comedy")
        interests.apply()
        with open(paths.CONTENT_MD, encoding="utf-8") as f:
            self.assertEqual(f.read().rstrip("\n"), before.rstrip("\n"))   # nothing learned: the section goes

    def test_learned_topics_join_the_plan_and_can_be_logged(self):
        interests.add([interests.parse_signal("topic | Missy Robbins | 2 | Italian cooking")], "mention",
                      date=TODAY.isoformat())
        p = context.profile()
        f = content.plan_facts(25, TODAY, content.recipe(), p, [], [])
        self.assertIn("Missy Robbins", [d["topic"] for d in f["due"]])
        topic, _, _ = content.parse_thread("missy robbins | follow-up | her new place", p)
        self.assertEqual(topic, "Missy Robbins")


class Rotation(unittest.TestCase):
    TOPICS = [context.Topic("Weak", ""), context.Topic("Strong", "")]
    ITEMS = [{"date": "2026-10-01", "topic": "Weak", "title": "a"}, {"date": "2026-10-25", "topic": "Strong", "title": "b"}]

    def test_equal_strengths_keep_the_old_order(self):
        self.assertEqual([t.name for t, _ in content.due(self.TOPICS, self.ITEMS, 2, today=TODAY)], ["Weak", "Strong"])

    def test_a_strong_interest_comes_round_sooner(self):
        got = content.due(self.TOPICS, self.ITEMS, 2, {"weak": 0.3, "strong": 6.0}, TODAY)
        self.assertEqual([t.name for t, _ in got], ["Strong", "Weak"])   # 6 x 8 days beats 0.3 x 32

    def test_never_told_still_comes_first(self):
        tops = self.TOPICS + [context.Topic("New", "")]
        got = content.due(tops, self.ITEMS, 3, {"weak": 9.0, "strong": 9.0, "new": 0.3}, TODAY)
        self.assertEqual(got[0][0].name, "New")


if __name__ == "__main__":
    unittest.main()
