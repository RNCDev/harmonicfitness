"""Make each shipped coach's Pocket voice file (maintainer only; not a listener command).

  .venv/bin/python tools/coachmaker/export_pocket.py andy claire ...

The public Pocket model (kyutai/pocket-tts-without-voice-cloning, what listeners download) can't turn an
audio clip into a voice, but it loads a saved voice state. The gated kyutai/pocket-tts can, so here, once per
coach, it turns coaches/coach-<slug>-local/clip.wav into pocket.safetensors beside it. That needs the
maintainer's Hugging Face login with Pocket's terms accepted (https://huggingface.co/kyutai/pocket-tts, then
`uvx hf auth login`); no listener ever runs this. The gated model downloads into models/ the first time
(about 0.2 GB beyond the public one); delete models/models--kyutai--pocket-tts afterwards if you like.

The state is tied to the Pocket model it was made with: the engine's pins (tools/voices.py: POCKET_VERSION,
POCKET_LANGUAGE), and a new Pocket model means exporting all ten again. It runs in the engine's own
environment on the processor, in full precision, so the file is the same whichever computer made it.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    missing = [s for s in argv if not os.path.exists(os.path.join(common.folder(s), "clip.wav"))]
    if missing:
        raise SystemExit(f"No clip.wav yet for: {', '.join(missing)}")
    from pathlib import Path
    from pocket_tts import TTSModel
    from pocket_tts.models.model_state import export_model_state
    model = TTSModel.load_model(language=common.LANGUAGE)   # the gated model, when the login allows it
    if not model.has_voice_cloning:
        raise SystemExit("The gated Pocket model didn't load (no login, or its terms not accepted), so it can't "
                         "read a clip. Accept the terms at https://huggingface.co/kyutai/pocket-tts and run "
                         "`uvx hf auth login`.")
    for slug in argv:
        state = model.get_state_for_audio_prompt(Path(common.folder(slug)) / "clip.wav")
        dest = os.path.join(common.folder(slug), "pocket.safetensors")
        export_model_state(state, dest + ".part")
        os.replace(dest + ".part", dest)
        print(f"  {slug}: {os.path.getsize(dest) / 1e6:.1f} MB", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
