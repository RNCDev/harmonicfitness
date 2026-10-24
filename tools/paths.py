"""Where everything lives: the engine (this repo) and the listener's own context.

The engine is the repo: tools, skills and shared knowledge. Everything about one
listener (profile, health, log, coaches, workouts, research, rendered clips, API keys)
lives in one context folder, `me/` at the repo root by default.
Set SWEATCAST_HOME to keep it somewhere else. `me/` is ignored by the engine's git,
so pulling engine updates never touches it; `me.example/` is the template that
`./sweatcast setup` copies to start one.

Every tool takes its paths from here, so a different context folder needs no edits.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.abspath(os.path.expanduser(os.environ.get("SWEATCAST_HOME") or os.path.join(ROOT, "me")))

PROFILE = os.path.join(HOME, "profile.md")
HEALTH = os.path.join(HOME, "health.md")
LOG = os.path.join(HOME, "log.md")
MY_MOVEMENTS = os.path.join(HOME, "movements.toml")   # the listener's private movements
ENV_FILE = os.path.join(HOME, ".env")                  # cloud voice API keys: read only by tools/keys.py
WORKOUTS = os.path.join(HOME, "workouts")
RESEARCH = os.path.join(WORKOUTS, "research")
VIDEOS = os.path.join(RESEARCH, "videos")
PUZZLES = os.path.join(RESEARCH, "puzzles")
TOLD = os.path.join(RESEARCH, "told.jsonl")       # every filler item a session told
PANTRY = os.path.join(RESEARCH, "pantry")         # evergreen filler researched ahead of time
CACHE = os.path.join(WORKOUTS, ".audio-cache")
PACE_FILE = os.path.join(CACHE, "voice-pace.json")
LOGS = os.path.join(WORKOUTS, ".logs")                # each build's render log, and builds.jsonl
BUILDS = os.path.join(LOGS, "builds.jsonl")           # one record per rendered MP3

PERSONAS = os.path.join(HOME, "personas")   # each coach: personas/<slug>/ (persona.md, clip, pace, service voices)

OLD_VOICES = os.path.join(HOME, "voices")      # sweatcast 8's private voices; ./sweatcast migrate makes them coaches
V8_VOICES = os.path.join(ROOT, "tools", "migrate-assets", "v8-voices")   # the clips sweatcast 8 shipped
SMOKE_DRAFT = os.path.join(ROOT, "knowledge", "smoke-test.draft.txt")   # one minute, which measures a coach's pace
EXAMPLE = os.path.join(ROOT, "me.example")
VERSION_FILE = os.path.join(ROOT, "VERSION")
MOVEMENTS = os.path.join(ROOT, "knowledge", "movements.toml")           # the shared movement catalog
SESSIONS = os.path.join(ROOT, "knowledge", "sessions.toml")             # session methods and dose rules
CONTENT = os.path.join(ROOT, "knowledge", "content.toml")               # the filler plan


def require(path, what="file"):
    """Exit with a setup hint when a context file is missing."""
    if not os.path.exists(path):
        raise SystemExit(f"No {what} at {show(path)}. A new copy of sweatcast starts its context "
                         "folder with ./sweatcast setup, which copies me.example/ to me/.")
    return path


def show(path):
    """A path as short as it can be said: relative to the repo when inside it."""
    rel = os.path.relpath(path, ROOT)
    return path if rel.startswith("..") else rel
