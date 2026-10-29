"""Which MP3s a turn puts in the chat: a workout or a coach's sample (the newest two), and every candidate
of an audition made this turn, by letter."""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import folder, worker  # noqa: E402

AUD = "coaches/.auditions/2026-10-28-1"


class NewAudio(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="hf-audio-")
        self.addCleanup(shutil.rmtree, self.home, True)

    def put(self, rel, data=b"mp3"):
        path = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def audition(self, letters=("A", "B", "C")):
        cands = []
        for i, letter in enumerate(letters):
            service, k = ("fish", i + 1) if i != 2 else ("gemini", 1)
            cands.append({"letter": letter, "service": service, "k": k, "wav": f"{service}-{k}.wav",
                          "mp3": f"{service}-{k}.mp3", "usd_per_workout": 0.3 if service == "fish" else 0.27})
        for c in reversed(cands):   # written out of order: the chat still lists them by letter
            self.put(f"{AUD}/{c['mp3']}")
        self.put(f"{AUD}/candidates.json", json.dumps(cands).encode())

    def names(self, written=None):
        return [name for _, name in worker.new_audio(self.home, written or {})]

    def test_a_workout_and_a_sample_as_before(self):
        self.put("workouts/a/old.mp3")
        time.sleep(0.01)
        self.put("workouts/a/a.web-1.mp3")
        self.put("workouts/b/b.mp3")
        time.sleep(0.01)
        self.put("coaches/coach-dana-fish/sample.mp3")   # the coach made during the build: the workout is its voice
        self.assertEqual(self.names(), ["b"])

    def test_a_sample_is_named_for_its_coach(self):
        self.put("coaches/coach-nolan-gemini/persona.md", b'+++\nschema = 5\nname = "Coach Nolan"\n+++\nNotes.\n')
        self.put("coaches/coach-nolan-gemini/sample.mp3")
        self.assertEqual(self.names(), ["Coach Nolan's voice"])

    def test_an_auditions_candidates_by_letter_without_the_service(self):
        self.audition()
        names = self.names()
        self.assertEqual(names, ["Candidate A, about $0.30 a workout", "Candidate B, about $0.30 a workout",
                                 "Candidate C, about $0.27 a workout"])
        self.assertFalse(any("fish" in n or "gemini" in n for n in names))

    def test_eight_candidates_all_come(self):
        self.audition(tuple("ABCDEFGH"))
        self.assertEqual(len(self.names()), 8)

    def test_an_audition_from_an_earlier_turn_isnt_posted_again(self):
        self.audition()
        written = folder.materialize(folder.harvest(self.home, {}), os.path.join(self.home, "next"))
        self.home = os.path.join(self.home, "next")
        self.assertEqual(self.names(written), [])
        self.put("coaches/coach-dana-fish/persona.md", b'+++\nname = "Coach Dana"\n+++\n')
        self.put("coaches/coach-dana-fish/sample.mp3")   # the keep turn: only the kept coach's sample
        self.assertEqual(self.names(written), ["Coach Dana's voice"])

    def test_a_damaged_candidates_list_still_plays_unlabeled(self):
        self.put(f"{AUD}/fish-1.mp3")
        self.put(f"{AUD}/candidates.json", b"not json")
        self.assertEqual(self.names(), ["Voice candidate"])


if __name__ == "__main__":
    unittest.main()
