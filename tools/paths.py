"""Where everything lives: the engine (this repo) and the listener's own context.

The engine is the repo: tools, skills and shared knowledge. Everything about one
listener (profile, health, log, coaches, workouts, research, rendered clips, API keys)
lives in one context folder, `me/` at the repo root by default.
Set HARMONICFITNESS_HOME to keep it somewhere else. `me/` is ignored by the engine's git,
so pulling engine updates never touches it; `me.example/` is the template that
`./harmonicfitness setup` copies to start one.

Every tool takes its paths from here, so a different context folder needs no edits.
"""
import os
import errors

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTE = os.environ.get("CLAUDE_CODE_REMOTE") == "true"   # Claude Code on the web


def find_home(root, env):
    """The context folder: HARMONICFITNESS_HOME; else me/ when it holds a profile; else, on Claude Code on the
    web, the one folder beside the engine holding a profile.md and coaches/ (personas/ before 0.15.0) (the listener's private
    harmonicfitness-me repo, attached to the session); else me/."""
    if env.get("HARMONICFITNESS_HOME"):
        return os.path.abspath(os.path.expanduser(env["HARMONICFITNESS_HOME"]))
    default = os.path.join(root, "me")
    if env.get("CLAUDE_CODE_REMOTE") == "true" and not os.path.exists(os.path.join(default, "profile.md")):
        parent = os.path.dirname(os.path.abspath(root))
        try:
            names = sorted(os.listdir(parent))
        except OSError:
            names = []
        found = [os.path.join(parent, n) for n in names
                 if os.path.join(parent, n) != os.path.abspath(root)
                 and os.path.isfile(os.path.join(parent, n, "profile.md"))
                 and any(os.path.isdir(os.path.join(parent, n, c)) for c in ("coaches", "personas"))]
        if len(found) == 1:
            return found[0]
    return default


HOME = find_home(ROOT, os.environ)

# The local voice models: models/ at the repo root (git-ignored; it may be a symlink to a shared place), or
# HARMONICFITNESS_MODELS. Every download and load goes there: Hugging Face's cache is pointed at it here, at
# import, since each tool (render.py included) runs as its own process. It has to be here: huggingface_hub
# reads HF_HUB_CACHE once, when it's first imported, and every tool imports paths before it. The cache it
# replaced is kept for ./harmonicfitness models adopt.
OLD_HF_HUB_CACHE = os.environ.get("HARMONICFITNESS_OLD_HF_HUB_CACHE") or os.environ.get("HF_HUB_CACHE") or os.path.join(
    os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface"), "hub")
MODELS = os.path.abspath(os.path.expanduser(os.environ.get("HARMONICFITNESS_MODELS") or os.path.join(ROOT, "models")))
os.environ["HF_HUB_CACHE"] = MODELS
os.environ.setdefault("HARMONICFITNESS_OLD_HF_HUB_CACHE", OLD_HF_HUB_CACHE)   # what it was before the first tool set it

PROFILE = os.path.join(HOME, "profile.md")       # who the listener is (name, experience, basics)
TRAINING = os.path.join(HOME, "training.md")     # how they train: kits, likes and dislikes, default session
CONTENT_MD = os.path.join(HOME, "content.md")    # what fills the rests: interests, feeds, channels, taste
SETTINGS = os.path.join(HOME, "settings.toml")   # the tools' settings: setup, audio route, delivery, ceilings
HEALTH = os.path.join(HOME, "health.md")
LOG = os.path.join(HOME, "log.md")
MY_MOVEMENTS = os.path.join(HOME, "movements.toml")   # the listener's private movements
ENV_FILE = os.path.join(HOME, ".env")                  # cloud voice API keys: read only by tools/keys.py
WORKOUTS = os.path.join(HOME, "workouts")
CHECKS = os.path.join(WORKOUTS, "checks")             # smoke tests and builds of drafts outside a workout folder
RESEARCH = os.path.join(WORKOUTS, "research")
DAILY = os.path.join(RESEARCH, "daily")               # each day's research sheet and feeds
VIDEOS = os.path.join(RESEARCH, "videos")
PUZZLES = os.path.join(RESEARCH, "puzzles")
TOLD = os.path.join(RESEARCH, "told.jsonl")       # every filler item a session told
RESERVE = os.path.join(RESEARCH, "reserve")       # evergreen filler researched ahead of time
CACHE = os.path.join(WORKOUTS, ".audio-cache")
PACE_FILE = os.path.join(CACHE, "voice-pace.json")
LOGS = os.path.join(WORKOUTS, ".logs")                # each build's render log, and builds.jsonl
# one record per rendered MP3, and a "failed" one per web render that sent text and then stopped
BUILDS = os.path.join(LOGS, "builds.jsonl")

# The stock coaches the engine ships: ten local, four web (coaches/<slug>/). HARMONICFITNESS_SHIPPED is test-only.
SHIPPED = os.path.abspath(os.environ.get("HARMONICFITNESS_SHIPPED") or os.path.join(ROOT, "coaches"))
PERSONAS = os.path.join(HOME, "coaches")   # the listener's own coaches, coaches/<slug>/ (personas/ before 0.15.0; migrate renames it)

SMOKE_DRAFT = os.path.join(ROOT, "knowledge", "smoke-test.draft.txt")   # one minute, which measures a coach's pace
EXAMPLE = os.path.join(ROOT, "me.example")
VERSION_FILE = os.path.join(ROOT, "VERSION")
MOVEMENTS = os.path.join(ROOT, "knowledge", "movements.toml")           # the shared movement catalog
SESSIONS = os.path.join(ROOT, "knowledge", "sessions.toml")             # session methods and dose rules
CONTENT = os.path.join(ROOT, "knowledge", "content.toml")               # the filler plan


def require(path, what="file"):
    """Exit with a setup hint when a context file is missing."""
    if not os.path.exists(path):
        raise errors.ContextError(f"No {what} at {show(path)}. A new copy of HarmonicFitness starts its context "
                         "folder with ./harmonicfitness setup, which copies me.example/ to me/.")
    return path


def show(path):
    """A path as short as it can be said: relative to the repo when inside it."""
    try:
        rel = os.path.relpath(path, ROOT)
    except ValueError:   # Windows: a path on another drive (a G:\ Google Drive folder) has no relative form
        return path
    return path if rel.startswith("..") else rel
