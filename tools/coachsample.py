"""A web coach's 45-second sample.mp3: the script every stock coach's sample speaks, said through the coach's own
service and mastered as a build is (./harmonicfitness coaches sample, and after keep and make).

The design line a voice is made from is only a few seconds; this is the sample the Coaches page plays and the
setup's choose-by-ear step compares, so a coach of the listener's own sounds as long as a stock one. It sends
about 500 characters, once a line, to the coach's service (about a cent).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cloud  # noqa: E402
import draft  # noqa: E402
import errors  # noqa: E402
import voices  # noqa: E402
from paths import show  # noqa: E402

# Every stock coach's sample says this (tools/coachmaker/sample.py and web_coaches.py read it from here).
DRAFT = """@@ 45 | Sample
Hi, I'm {name}. Let's see how this feels. Stand tall, feet about hip width apart, and let your arms hang loose.

We'll start with a few easy squats. Sit back like there's a chair behind you, chest up, and drive through your heels on the way up. [pause 1s]

Find your stance, and get ready. [count 3 go] [chime] Down slow, and up strong. That's the pace. Keep breathing, nice and steady. [hold]

Great work. That's how we'll train together. Shake it out, and when you're ready, we'll start your first workout.
"""


def draft_text(name, counts_in_words=True):
    """The sample's draft for coach `name`; a web coach has no recorded counts, so its count is said in words."""
    text = DRAFT.format(name=name)
    return text.replace("[count 3 go]", "Three, two, one, go.") if counts_in_words else text


def lines(name):
    """The sample's spoken lines, each once, in order."""
    segs = draft.parse(draft_text(name))
    return segs, list(dict.fromkeys(t for seg in segs for para in draft.plan(seg) for t, _ in para if draft.spoken(t)))


def characters(name):
    return sum(len(t) for t in lines(name)[1])


def speak(p, report=print):
    """Speak the sample with web coach `p` and write its sample.mp3 (a failure leaves the old one).
    Records a pace estimate from it only while the coach's pace isn't measured. Returns the MP3's path."""
    import render
    if not p.is_web:
        raise errors.CoachError(f"{p.name} is a local coach: its sample ships with it.")
    if p.shipped:
        raise errors.CoachError(f"{p.name} ships with its sample: only a coach of your own gets a new one.")
    v = cloud.voice_for(p, p.service)
    segs, said = lines(p.name)
    usd = cloud.estimate(p.service, v["model"], said)[1]
    report(f"Speaking {p.name}'s 45-second sample at {cloud.service_name(p.service)} "
           f"({sum(len(t) for t in said)} characters, about ${usd:.2f}).")
    say = cloud.speaker(v)
    clips = {t: render.level(say(t, 0)) for t in said}
    pcm, _, _ = render.assemble(segs, lambda t: clips[t], bell=render.chime(), tail=render.end_tone())
    out = p.sample
    render.encode(bytes(pcm), out, f"{p.name} sample")   # encoded beside it, then renamed: the old one is never half-written
    if not voices.pace(v)[1]:   # a measured pace (from real renders) is never replaced by an estimate
        seconds = sum(len(cloud.trim(clips[t])) for t in said) / 2 / cloud.SR
        if seconds > 0:
            voices.record_estimate(v, sum(voices.weight(t) for t in said), round(seconds, 3))
    report(f"Wrote {show(out)} ({len(pcm) / 2 / cloud.SR:.0f} seconds).")
    return out


def after_making(p, report=print):
    """The full sample right after a coach is kept or made; a failure keeps the design line's short sample
    (the coach is already saved) and says how to try again."""
    try:
        speak(p, report)
    except (cloud.ServiceError, *errors.PROBLEMS) as e:
        report(f"(The 45-second sample didn't come ({e}); the short one from the design stays. Try again with: "
               f"./harmonicfitness coaches sample \"{p.name}\")")
