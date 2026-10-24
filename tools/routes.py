"""Routes: how this computer turns a script into audio. "local" renders on this computer's own engine;
a cloud service (fish, elevenlabs, cartesia, deepgram) renders with the listener's key.

The profile's `render` setting is an ordered preference list, say ["local", "fish"], and one synced
profile works on every computer: each build takes the first route that works where it runs. Local
needs hardware the readiness check approves and the local engine installed; a service needs its key
in this computer's me/.env (never synced), and Deepgram a stock voice picked for the coach.

    ./sweatcast get route [--coach "Coach Julius"]    # the route a build would take here
"""
import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import keys  # noqa: E402

ROUTES = ("local", "fish", "elevenlabs", "cartesia", "deepgram")
SERVICES = ROUTES[1:]


def local_installed():
    """Whether the local engine for this system is installed in the environment (not imported)."""
    if os.environ.get("SWEATCAST_FAKE_LOCAL_ENGINE"):   # test-only: as if the local engine were installed
        return os.environ["SWEATCAST_FAKE_LOCAL_ENGINE"] == "1"
    import voices
    module = "mlx_audio" if voices.BACKEND == "mlx" else "chatterbox"
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def _facts(facts):
    if facts is not None:
        return facts
    import doctor
    return doctor.facts()


def usable(route, persona=None, facts=None):
    """(True, "") when `route` can render here, else (False, the reason and the one thing that would change it)."""
    if route not in ROUTES:
        return False, f"'{route}' isn't a route; the routes are {', '.join(ROUTES)}."
    if route == "local":
        f = _facts(facts)
        installed = local_installed()
        if f.get("local") == "no" and not (installed and f.get("local_hw") in ("fast", "experimental")):
            return False, f"local: {f.get('local_reason') or 'local voices do not run on this computer.'}"
        if not installed:
            return False, "local: the local engine isn't installed yet: ./sweatcast setup --local"
        if persona is not None and not persona.has_clip:
            return False, f"local: {persona.name} has no clip of their own (a Deepgram stock voice only)."
        return True, ""
    if not keys.is_set(route):
        return False, (f"{route}: no key on this computer ({keys.SERVICE_VARS[route]} in me/.env): "
                       f"./sweatcast keys init {route}, then paste the key into the file")
    if route == "deepgram" and persona is not None and not persona.table("deepgram").get("voice"):
        return False, (f"deepgram: {persona.name} has no Deepgram stock voice picked: "
                       "./sweatcast coaches samples deepgram, then ./sweatcast coaches set")
    if route != "deepgram" and persona is not None and not persona.has_clip:
        return False, f"{route}: {persona.name} has no clip of their own (a Deepgram stock voice only)."
    return True, ""


def pick(preferences, persona=None, override=None, facts=None):
    """The route a build takes: `override` (--engine) if it works here, else the first usable preference."""
    if override:
        ok, reason = usable(override, persona, facts)
        if not ok:
            raise SystemExit(f"Can't render with {override} here: {reason}")
        return override
    reasons = []
    for route in preferences or ["local"]:
        if route not in ROUTES:
            print(f"Skipped '{route}' in the profile's render list: not a route ({', '.join(ROUTES)}).",
                  file=sys.stderr)
            continue
        ok, reason = usable(route, persona, facts)
        if ok:
            return route
        reasons.append(reason)
    tried = [r for r in preferences or ["local"] if r in ROUTES]
    hints = [] if any(r in SERVICES for r in tried) else \
        ["a cloud voice: ./sweatcast keys init fish (or elevenlabs, cartesia, deepgram), then add it to the "
         "profile's render list"]
    raise SystemExit("No audio route works on this computer:\n  " + "\n  ".join(reasons + hints))


FEED_HOSTS = ("site.api.espn.com", "api.open-meteo.com", "en.wikipedia.org", "www.youtube.com")


def hosts(route):
    """The hosts a cloud route sends to, for a network allowlist (Claude Code on the web)."""
    if route not in SERVICES:
        return []
    import cloud
    from urllib.parse import urlparse
    return [urlparse(cloud.services()[route]["url"]).hostname]


def feed_hosts(profile=None):
    """The hosts ./sweatcast feeds and ./sweatcast youtube fetch from: the fixed ones, plus each RSS feed's."""
    from urllib.parse import urlparse
    out = list(FEED_HOSTS)
    if profile is not None:
        import context
        for _, kind, value in context.feed_sources(profile):
            if kind in ("rss", "weekly"):
                host = urlparse(value).hostname
                if host and host not in out:
                    out.append(host)
    return out


def report_lines(persona=None, preferences=None, facts=None):
    """The readiness check's Routes section."""
    out = []
    for route in ROUTES:
        ok, reason = usable(route, persona, facts)
        label = "works here" if ok else reason.split(": ", 1)[-1]
        if route in SERVICES:
            import cloud
            if not cloud.services()[route].get("tried_live"):
                label += " (not yet tried live)"
        out.append(f"  {route:10} {label}")
    try:
        out.append(f"  A build here would use: {pick(preferences, persona, facts=facts)}"
                   + (f" (for {persona.name})" if persona else ""))
    except SystemExit:
        out.append("  A build here would find no route that works (see above).")
    return out
