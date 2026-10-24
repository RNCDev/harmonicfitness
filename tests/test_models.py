"""models/: where the local voice models live, and adopting the ones already in Hugging Face's cache.
A fake cache only: no models, no network."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import models  # noqa: E402

REV = "b2d0a13aa7cfff0a06d9acb247ae91c8f19a6d75"
REPO = "mlx-community/chatterbox-turbo-fp16"


def fake_hub(hub, repo=REPO, rev=REV, shared=True, name="model.safetensors", data=b"weights"):
    """A repo folder in Hugging Face's layout; with shared, its blob lives in the hub's shared blobs/ (as on a
    cache made with shared blobs), linked from the repo's own blobs/ and its snapshot."""
    folder = os.path.join(hub, "models--" + repo.replace("/", "--"))
    sha = f"{abs(hash((repo, name))):064x}"[:64]
    os.makedirs(os.path.join(folder, "snapshots", rev), exist_ok=True)
    os.makedirs(os.path.join(folder, "blobs"), exist_ok=True)
    if shared:
        target_dir = os.path.join(hub, "blobs", sha[:2])
        os.makedirs(target_dir, exist_ok=True)
        with open(os.path.join(target_dir, sha), "wb") as f:
            f.write(data)
        os.symlink(os.path.join("..", "..", "blobs", sha[:2], sha), os.path.join(folder, "blobs", sha))
    else:
        with open(os.path.join(folder, "blobs", sha), "wb") as f:
            f.write(data)
    os.symlink(os.path.join("..", "..", "blobs", sha), os.path.join(folder, "snapshots", rev, name))
    os.makedirs(os.path.join(folder, "refs"), exist_ok=True)
    with open(os.path.join(folder, "refs", "main"), "w") as f:
        f.write(rev)
    return os.path.join(folder, "snapshots", rev, name)


class Models(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.old, self.new = os.path.join(self.d, "hub"), os.path.join(self.d, "models")

    def test_paths_point_hugging_face_at_models(self):
        code = "import sys; sys.path.insert(0, 'tools'); import paths, os; print(os.environ['HF_HUB_CACHE'])"
        env = {k: v for k, v in os.environ.items() if k not in ("SWEATCAST_MODELS", "HF_HUB_CACHE")}
        out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), os.path.join(ROOT, "models"))
        env["SWEATCAST_MODELS"] = self.new
        env["HF_HUB_CACHE"] = "/somewhere/else"
        out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), self.new)

    def test_adopt_keeps_shared_blob_links(self):
        snapshot = fake_hub(self.old)
        fake_hub(self.old, repo="someone/else", rev="1" * 40, name="other.bin", data=b"not ours")
        moved = models.adopt(self.old, self.new)
        self.assertEqual([r for r, _ in moved], [REPO])
        new_snapshot = snapshot.replace(self.old, self.new)
        with open(new_snapshot, "rb") as f:
            self.assertEqual(f.read(), b"weights")
        self.assertFalse(os.path.exists(os.path.dirname(os.path.dirname(snapshot))))
        self.assertTrue(os.path.exists(os.path.join(self.old, "models--someone--else")))   # not ours: stays
        self.assertTrue(models.complete(self.new, REPO, REV))
        self.assertEqual(models.adopt(self.old, self.new), [])   # nothing left to move

    def test_a_blob_another_repo_uses_is_copied_not_moved(self):
        fake_hub(self.old)
        other = fake_hub(self.old, repo="someone/else", rev="1" * 40, data=b"weights")
        # point the other repo's blob at ours, as a shared cache does for identical files
        ours = [os.path.join(r, f) for r, _, fs in os.walk(os.path.join(self.old, "blobs")) for f in fs][0]
        theirs_blob = os.path.realpath(other)
        os.remove(os.path.join(self.old, "models--someone--else", "blobs", os.path.basename(theirs_blob)))
        os.symlink(os.path.relpath(ours, os.path.join(self.old, "models--someone--else", "blobs")),
                   os.path.join(self.old, "models--someone--else", "blobs", os.path.basename(theirs_blob)))
        models.adopt(self.old, self.new)
        with open(other, "rb") as f:
            self.assertEqual(f.read(), b"weights")   # still readable where it was
        self.assertTrue(models.complete(self.new, REPO, REV))

    def test_dry_run_moves_nothing(self):
        snapshot = fake_hub(self.old)
        found = models.adopt(self.old, self.new, dry_run=True)
        self.assertEqual([r for r, _ in found], [REPO])
        self.assertTrue(os.path.exists(snapshot))
        self.assertFalse(os.path.exists(self.new))

    def test_models_is_ignored_even_as_a_symlink(self):
        if not shutil.which("git"):
            self.skipTest("git not installed")
        repo = os.path.join(self.d, "repo")
        os.makedirs(repo)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        shutil.copy(os.path.join(ROOT, ".gitignore"), repo)
        os.symlink(self.d, os.path.join(repo, "models"))
        self.assertEqual(subprocess.run(["git", "check-ignore", "-q", "models"], cwd=repo).returncode, 0)


if __name__ == "__main__":
    unittest.main()
