"""The ready-made web coaches, on OpenRouter and Gemini: persona.md, a 45-second sample.mp3 and a pace estimate
each, from coaches/roster.toml's [[web_coach]] tables (each one's `service`, openrouter unless named; maintainer
only; not a listener command).

  ./harmonicfitness keys            (OPENROUTER_API_KEY and GEMINI_API_KEY set)
  .venv/bin/python tools/coachmaker/web_coaches.py              (all of them)
  .venv/bin/python tools/coachmaker/web_coaches.py rowan tess   (some)
  .venv/bin/python tools/coachmaker/web_coaches.py gemini       (one service's)
  .venv/bin/python tools/coachmaker/web_coaches.py --personas   (persona.md only: nothing sent)

Each speaks the local coaches' sample script through its service once a line (about a cent a coach), its count
said in words as a web coach says it, laid out and mastered as a build is. The pace is the sample's weighted
characters over its trimmed speech, kept as an estimate until a listener's first render measures it.
"""
import json
import os
import sys
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "coachmaker")]
import cloud  # noqa: E402
import coachsample  # noqa: E402
import context  # noqa: E402
import draft  # noqa: E402
import personas  # noqa: E402
import render  # noqa: E402
import voices  # noqa: E402

ROSTER = os.path.join(ROOT, "coaches", "roster.toml")
DEFAULT = "openrouter"
# how a coach's description names its voice, by service
OWN_VOICE = {"openrouter": "one of OpenRouter's stock voices", "gemini": "one of Gemini's own voices"}


def sample_draft(name):
    """The stock sample's draft, its count in words (a web coach has no recorded counts)."""
    return coachsample.draft_text(name)


def service(c):
    return c.get("service", DEFAULT)


def folder_name(c):
    return f"coach-{c['slug']}-{service(c)}"


def settings(c):
    return {"name": c["name"], "aliases": [], "kind": "web", "placeholder": False, "service": service(c),
            "voice_id": c["voice"],
            "description": f"{c['who']}. {c['sound']}. A ready-made coach: {OWN_VOICE[service(c)]}.",
            "voice": {"who": c["who"], "sound": c["sound"], "energy": c["energy"], "pace": "Natural; brisk during work",
                      "avoid": "Hype, shouting, announcer voice"},
            "character": {"tone": c["tone"], "encouragement": c["encouragement"]}}


def persona_text(c):
    return context.persona_text(settings(c), "")


def make(c, personas_only=False):
    folder = os.path.join(ROOT, "coaches", folder_name(c))
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "persona.md"), "w", encoding="utf-8") as f:
        f.write(persona_text(c))
    if personas_only:
        return folder
    p = personas.load(folder)
    v = cloud.voice_for(p, service(c))
    say = cloud.speaker(v)
    segs = draft.parse(sample_draft(c["name"]))
    lines = list(dict.fromkeys(t for seg in segs for para in draft.plan(seg) for t, _ in para if draft.spoken(t)))
    clips = {t: render.level(say(t, 0)) for t in lines}
    pcm, rows, _ = render.assemble(segs, lambda t: clips[t], bell=render.chime(), tail=render.end_tone())
    render.encode(bytes(pcm), os.path.join(folder, "sample.mp3"), f"{c['name']} sample")
    seconds = sum(len(cloud.trim(clips[t])) for t in lines) / 2 / cloud.SR
    weight = sum(voices.weight(t) for t in lines)
    pace = {voices._rate_key(v): {"name": c["name"], "weight": weight, "seconds": round(seconds, 3), "estimate": True}}
    with open(os.path.join(folder, "pace.json"), "w", encoding="utf-8") as f:
        json.dump(pace, f, indent=1)
        f.write("\n")
    print(f"{c['name']}: {round(len(pcm) / 2 / cloud.SR, 1)} s, {weight / seconds:.1f} weighted characters a second",
          flush=True)
    return folder


def main(argv):
    only = [a for a in argv if not a.startswith("--")]   # slugs, or a service's name for all of its coaches
    with open(ROSTER, "rb") as f:
        roster = tomllib.load(f)["web_coach"]
    for c in roster:
        if not only or c["slug"] in only or service(c) in only:
            make(c, personas_only="--personas" in argv)


if __name__ == "__main__":
    main(sys.argv[1:])
