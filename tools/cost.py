"""What a web build would cost: `./harmonicfitness get cost --coach <coach> [--chars N] [--json]`.

The price of sending N characters to the coach's service at its default model's rate (approximate; the
service's rates are in knowledge/services.toml), against the profile's ceiling (cloud_max_chars). With no
--chars, N is the ceiling: the most a build may cost. A coach still to be made (a stock web coach with
`pending = "design"`) also says what its one-time voice design costs. A local coach costs nothing and has no
price; one that can't speak here (no key) stops as a build would (exit 64)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cloud  # noqa: E402
import coachpick  # noqa: E402
import context  # noqa: E402
import errors  # noqa: E402
import personas  # noqa: E402


def cost(coach_name=None, chars=None):
    """{"coach", "service", "model", "chars", "usd", "ceiling", "pending_design", "design_usd"} for `coach_name`
    (default: the one a build takes), sending `chars` characters (default: the profile's ceiling)."""
    persona = coachpick.coach(coach_name)
    if persona is None:
        raise errors.CoachError("No coach found: the ten local coaches ship in coaches/ (git pull), and a web coach "
                                "comes from the coach skill.")
    if not persona.is_web:
        raise errors.UsageError(f"{persona.name} is a local coach: it speaks on this computer and costs nothing "
                                "to send.")
    service = coachpick.pick(context.render_preferences(), persona)   # raises when it can't speak here
    voice = personas.voice_for(persona, service, pending=bool(persona.pending))
    ceiling = context.cloud_max_chars(context.profile())
    chars = ceiling if chars is None else chars
    _, usd = cloud.estimate(service, voice["model"], ["x" * chars])
    pending = bool(persona.pending)
    design = cloud.services()[service].get("design_usd") if pending else None
    return {"coach": persona.name, "service": service, "model": voice["model"], "chars": chars,
            "usd": round(usd, 4), "ceiling": ceiling, "pending_design": pending,
            "design_usd": float(design) if design is not None else None}


def lines(c):
    """The text form of `cost`'s answer."""
    out = [f"{c['chars']:,} characters to {cloud.service_name(c['service'])} ({c['model']}) for {c['coach']}: "
           f"about ${c['usd']:.2f} (approximate); this profile's ceiling is {c['ceiling']:,} characters a build."]
    if c["pending_design"]:
        out.append(f"{c['coach']}'s voice is made first, once: " +
                   (f"about ${c['design_usd']:.2f}." if c["design_usd"] is not None else "design cost not published."))
    return out
