"""Routes: how this computer turns a script into audio. "local" renders on this computer's own engine;
a web service (each one in knowledge/services.toml: cloud.SERVICES) renders with the listener's key.

The profile's `render` setting is an ordered preference list, say ["local", "fish"], and one synced
profile works on every computer: each build takes the first route that works where it runs. Local
needs hardware the readiness check approves and the local engine installed; a service needs its key
in this computer's me/.env (never synced).

The coach decides first. A web coach (kind = "web") speaks only through the service that designed its
voice, whatever the render list says, and stops with WebCoachUnavailable when that service has no key
here. A local coach renders only on the local route. This module says what works here; coachpick.pick
makes the choice.

    ./harmonicfitness get route [--coach "Coach Julius"]    # the route a build would take here
"""
import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import errors  # noqa: E402
import cloud  # noqa: E402
import keys  # noqa: E402
import machine  # noqa: E402
import paths  # noqa: E402

ROUTES, SERVICES = cloud.ROUTES, cloud.SERVICES   # knowledge/services.toml, plus "local"


class WebCoachUnavailable(errors.UsageError):
    """A web coach can't speak here: its service has no key on this computer, or --engine names another
    service. `get route` and `build` exit 64 on it."""


def missing_key(persona):
    """Why web coach `persona` can't speak here, and the one thing to do: its service's key."""
    var = keys.SERVICE_VARS[persona.service]
    name = cloud.service_name(persona.service)
    if paths.WEB:
        fix = f"add your {name} key in {keys.APP_SETTINGS}"
    elif paths.REMOTE:
        fix = (f"set {var}=<your key> in the cloud environment's settings, under Environment variables "
               "(a new session picks it up)")
    else:
        fix = (f"./harmonicfitness keys init {persona.service}, then paste the key after {var}= "
               "(keys open opens the file)")
    return f"{persona.name} speaks through {name}, and there's no {name} key on this computer: {fix}."


def local_installed():
    """Whether the local engine for this system is installed in the environment (not imported)."""
    if os.environ.get("HARMONICFITNESS_FAKE_LOCAL_ENGINE"):   # test-only: as if the local engine were installed
        return os.environ["HARMONICFITNESS_FAKE_LOCAL_ENGINE"] == "1"
    try:
        return importlib.util.find_spec("pocket_tts") is not None
    except (ImportError, ValueError):
        return False


def computer(facts=None):
    """`facts` when given (the tests), else this computer's (machine.facts, the readiness check's)."""
    return facts if facts is not None else machine.facts()


def usable(route, persona=None, facts=None):
    """(True, "") when `route` can render here, else (False, the reason and the one thing that would change it)."""
    if route not in ROUTES:
        return False, f"'{route}' isn't a route; the routes are {', '.join(ROUTES)}."
    if route == "local":
        if persona is not None and persona.is_web:
            return False, f"local: {persona.name} is a web coach, which speaks only through {persona.service}."
        f = computer(facts)
        installed = local_installed()
        if f.get("local") == "no" and not (installed and f.get("local_hw") in ("fast", "experimental")):
            return False, f"local: {f.get('local_reason') or 'local voices do not run on this computer.'}"
        if not installed:
            return False, "local: the local engine isn't installed yet: ./harmonicfitness setup --local"
        if persona is not None and not persona.has_clip:
            return False, f"local: {persona.name} has no clip of their own."
        return True, ""
    if persona is not None and not persona.is_web:
        return False, (f"{route}: {persona.name} is a local coach, and a local coach renders only locally "
                       "(a web coach speaks through a web service).")
    if persona is not None and persona.is_web and persona.service != route:
        return False, f"{route}: {persona.name} speaks through {persona.service}, not {route}."
    try:
        have = keys.get(route)
    except keys.BadKey as e:
        return False, f"{route}: {e}"
    if not have:
        return False, (f"{route}: no key on this computer ({keys.SERVICE_VARS[route]} in me/.env): "
                       f"./harmonicfitness keys init {route}, then paste the key into the file")
    return True, ""


def pick(preferences, persona=None, override=None, facts=None):
    """The route a build takes: coachpick.pick, kept here until the next minor release."""
    import coachpick
    return coachpick.pick(preferences, persona, override, facts)


def stand_ins():
    """{service: the stock web coach that ships for it in coaches/}."""
    import personas
    return {p.service: p for p in personas.all() if p.is_web and p.shipped and p.service in SERVICES}


def way_out(folder=None):
    """How to get a coach that speaks here when local voices don't: make a web coach, or use the stock web coach
    of a service with a key here."""
    shipped = stand_ins()
    make = 'make a web coach (the coach skill: "I want a new coach")'
    keyed = [s for s in SERVICES if keys.is_set(s) and s in shipped]
    if keyed:
        uses = [f"{shipped[s].name} ({cloud.service_name(s)}): build with --coach \"{shipped[s].name}\"" for s in keyed]
        return f"{make}, or use the stock coach for a service with a key here: " + "; ".join(uses) + "."
    add = (f"add its key in {keys.APP_SETTINGS}" if paths.WEB else
           "set its key in the cloud environment's settings, under Environment variables" if paths.REMOTE
           else "./harmonicfitness keys init <service>, then paste the key into the file")
    names = ", ".join(f"{shipped[s].name} ({cloud.service_name(s)})" for s in SERVICES if s in shipped)
    return f"{make}, or add a service's key ({add}) and use its stock coach: {names}."


FEED_HOSTS = ("site.api.espn.com", "api.open-meteo.com", "en.wikipedia.org", "www.youtube.com")


def hosts(route):
    """The hosts a cloud route sends to, for a network allowlist (Claude Code on the web)."""
    if route not in SERVICES:
        return []
    from urllib.parse import urlparse
    return [urlparse(cloud.services()[route]["url"]).hostname]


def feed_hosts(profile=None):
    """The hosts ./harmonicfitness feeds and ./harmonicfitness youtube fetch from: the fixed ones, plus each RSS feed's."""
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
