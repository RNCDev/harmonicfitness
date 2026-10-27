"""Each shipped coach's persona.md, from coaches/roster.toml (maintainer only; not a listener command).

  .venv/bin/python tools/coachmaker/persona.py            (all ten)

The roster is the one source: name, gender, [voice] (who, sound, energy) and [character] (how the coach talks,
what the script writer follows). Edit the roster, then run this again; tests check the two agree.
"""
import os
import sys
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import context  # noqa: E402
import fileio  # noqa: E402

ROSTER = os.path.join(ROOT, "coaches", "roster.toml")
ALIASES = {"andy": ["Coach Demo"]}   # Andy's name before 10.3.0


def q(v):
    if isinstance(v, list):
        return "[" + ", ".join(q(x) for x in v) + "]"
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def text(c):
    description = f"{c['who']}. {c['sound']}. {c['energy']}."
    lines = ["+++", f"schema = {context.PERSONA_SCHEMA}", 'kind = "local"', f"name = {q(c['name'])}",
             f"aliases = {q(ALIASES.get(c['slug'], []))}", f"gender = {q(c['gender'])}",
             f"description = {q(description)}", "",
             "# One of the ten coaches sweatcast ships (coaches/roster.toml makes this file: edit there).",
             "[local]", 'engine = "pocket"', "",
             "[voice]", *(f"{k} = {q(c[k])}" for k in ("who", "sound", "energy")), "",
             "[character]", *(f"{k} = {q(v)}" for k, v in c["character"].items()), "+++", ""]
    return "\n".join(lines)


def main(argv):
    with open(ROSTER, "rb") as f:
        roster = tomllib.load(f)
    for c in roster["coach"]:
        if argv and c["slug"] not in argv:
            continue
        path = os.path.join(ROOT, "coaches", f"coach-{c['slug']}-local", "persona.md")
        fileio.atomic_write(path, text(c))
        print(path)


if __name__ == "__main__":
    main(sys.argv[1:])
