"""Make each shipped coach's Pocket voice file (maintainer only; not a listener command).

  .venv/Scripts/python tools/coachmaker/export_pocket.py andy claire ...

The public Pocket model (kyutai/pocket-tts-without-voice-cloning, what listeners download) can't turn an
audio clip into a voice, but it loads a saved voice state. The gated kyutai/pocket-tts can, so here, once per
coach, it turns coaches/coach-<slug>-local/clip.wav into pocket.safetensors beside it. That needs the
maintainer's Hugging Face login with Pocket's terms accepted; no listener ever runs this.

The state is tied to the Pocket model it was made with: POCKET and LANGUAGE below match tools/voices.py's
pin, and a new Pocket model means exporting all ten again. It runs on the processor (in the bench's
pocket-cpu environment), in full precision, so the file is the same whichever computer made it.
"""
import json
import os
import subprocess
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(TOOLS)
COACHES = os.path.join(ROOT, "coaches")
ENV = os.path.join(ROOT, ".cache", "bench", "envs", "pocket-cpu")
POCKET = "pocket-tts==4.0.1"
LANGUAGE = "english_2026-10"
GATED = ("kyutai/pocket-tts", "db04f0e653473e5c7333c69686ac92b7460b0c1d")


def worker(slugs):
    """Inside the pocket environment: clip.wav to pocket.safetensors for each coach."""
    from pathlib import Path
    import pocket_tts
    from pocket_tts import TTSModel
    from pocket_tts.models.model_state import export_model_state
    model = TTSModel.load_model(language=LANGUAGE)
    if not model.has_voice_cloning:
        raise SystemExit("The gated Pocket model didn't load (no login, or its terms not accepted), so it "
                         "can't read a clip. Run `uvx hf auth login` and accept the terms at "
                         "https://huggingface.co/kyutai/pocket-tts.")
    out = {"pocket_tts": pocket_tts.__version__ if hasattr(pocket_tts, "__version__") else None, "coaches": {}}
    for slug in slugs:
        folder = os.path.join(COACHES, f"coach-{slug}-local")
        state = model.get_state_for_audio_prompt(Path(folder) / "clip.wav")
        dest = os.path.join(folder, "pocket.safetensors")
        export_model_state(state, dest + ".part")
        os.replace(dest + ".part", dest)
        out["coaches"][slug] = os.path.getsize(dest)
        print(f"  {slug}: {os.path.getsize(dest) / 1e6:.1f} MB", flush=True)
    print(json.dumps(out))
    return 0


def main(argv):
    if argv[:1] == ["--worker"]:
        return worker(argv[1:])
    if not argv:
        raise SystemExit(__doc__)
    missing = [s for s in argv if not os.path.exists(os.path.join(COACHES, f"coach-{s}-local", "clip.wav"))]
    if missing:
        raise SystemExit(f"No clip.wav yet for: {', '.join(missing)}")
    sys.path.insert(0, TOOLS)
    import paths  # noqa: F401  (points HF_HUB_CACHE at models/)
    py = os.path.join(ENV, ".venv", "Scripts" if os.name == "nt" else "bin", "python.exe" if os.name == "nt" else "python")
    env = dict(os.environ, HF_HUB_CACHE=os.path.join(ROOT, "models"), PYTHONIOENCODING="utf-8")
    return subprocess.call([py, os.path.abspath(__file__), "--worker", *argv], cwd=ROOT, env=env)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
