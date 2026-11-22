"""The hosted site (HARMONICFITNESS_HOSTED): one account of the site's own, on OpenRouter, writes and speaks
every workout, and listeners pay in minutes (webapp.minutes). What that fixes is here: the service, the voice
model whose price the minute packs were set against, and which coaches speak with it. A coach on a dearer model
would cost the site more than a minute sells for, so it never records here (agent.tools._record refuses it)."""

SERVICE = "openrouter"             # the one provider that writes, and the one service that speaks
KEY_VAR = "OPENROUTER_API_KEY"     # how the engine is handed the site's key (never a listener's)
VOICE_MODEL = "google/gemini-3.8-flash-lite-tts"   # about 0.9 of a cent a minute spoken, as billed (0.85.1)
CHARS_A_MINUTE = 650               # about what a minute of a workout speaks: a length, when no plan gives one

# what a listener reads when the site's own account is what failed: nothing they can fix, so no key talk
DOWN = "The service that writes and speaks your workouts isn't answering just now. Try again in a little while."
NO_KEYS = "This site runs on minutes: there are no keys to add or check here."


def speaks(coach: dict) -> bool:
    """Whether a coach (a row of the engine's `coaches list --json`) records on the hosted site: a ready-made one
    on the site's service whose voice is the hosted model."""
    return bool(coach.get("shipped")) and coach.get("service") == SERVICE and coach.get("model") == VOICE_MODEL \
        and not coach.get("placeholder")


def coaches(listed: list) -> list[dict]:
    """The hosted site's coaches, of a listing's: each marked as speaking here (the site holds the key)."""
    return [{**c, "speaks_here": True, "default": False} for c in listed if isinstance(c, dict) and speaks(c)]


def find(listed: list, name: str | None) -> dict | None:
    """The hosted coach called `name` (its name, folder or first name, any case), or None."""
    want = (name or "").strip().casefold()
    if not want:
        return None
    for c in coaches(listed):
        full = str(c.get("name") or "")
        first = full.removeprefix("Coach ").split(" ")[0] if full else ""
        if want in (full.casefold(), str(c.get("slug") or "").casefold(), first.casefold(),
                    f"coach {first}".casefold()):
            return c
    return None
