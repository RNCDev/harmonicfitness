"""Routes: how this computer turns a script into audio. "local" renders on this computer's own engine;
a web service (each one in knowledge/services.toml: cloud.SERVICES) renders with the listener's key.

The profile's `render` setting is an ordered preference list, say ["local", "fish"], and one synced
profile works on every computer: each build takes the first route that works where it runs. Local
needs hardware the readiness check approves and the local engine installed; a service needs its key
in this computer's me/.env (never synced).

The coach decides first. A web coach (kind = "web") speaks only through the service that designed its
voice, whatever the render list says, and stops with WebCoachUnavailable when that service has no key
here. A local coach renders only on the local route.

    ./sweatcast get route [--coach "Coach Julius"]    # the route a build would take here
"""
import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import cloud  # noqa: E402
import keys  # noqa: E402
import paths  # noqa: E402

ROUTES, SERVICES = cloud.ROUTES, cloud.SERVICES   # knowledge/services.toml, plus "local"


class WebCoachUnavailable(cli.Usage):
    """A web coach can't speak here: its service has no key on this computer, or --engine names another
    service. `get route` and `build` exit 64 on it."""




def _missing_key(persona):
    var = keys.SERVICE_VARS[persona.service]
    name = cloud.service_name(persona.service)
    if paths.REMOTE:
        fix = (f"set {var}=<your key> in the cloud environment's settings, under Environment variables "
               "(a new session picks it up)")
    else:
        fix = (f"./sweatcast keys init {persona.service}, then paste the key after {var}= "
               "(keys open opens the file)")
    return f"{persona.name} speaks through {name}, and there's no {name} key on this computer: {fix}."


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
        if persona is not None and persona.is_web:
            return False, f"local: {persona.name} is a web coach, which speaks only through {persona.service}."
        f = _facts(facts)
        installed = local_installed()
        if f.get("local") == "no" and not (installed and f.get("local_hw") in ("fast", "experimental")):
            return False, f"local: {f.get('local_reason') or 'local voices do not run on this computer.'}"
        if not installed:
            return False, "local: the local engine isn't installed yet: ./sweatcast setup --local"
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
                       f"./sweatcast keys init {route}, then paste the key into the file")
    return True, ""


def pick(preferences, persona=None, override=None, facts=None):
    """The route a build takes: a web coach's own service (whatever the render list, and only if keyed here);
    else `override` (--engine) if it works here; else the first usable preference."""
    if persona is not None and persona.is_web:
        if not persona.service or persona.service not in SERVICES:
            raise WebCoachUnavailable(f"{persona.name} is a web coach with no known service "
                                      f"({persona.service or 'none'}); the services are {', '.join(SERVICES)}.")
        if override and override != persona.service:
            raise WebCoachUnavailable(
                f"{persona.name} speaks through {cloud.service_name(persona.service)} only, so --engine {override} "
                f"can't render them here.")
        if not keys.get(persona.service):   # a key that can't be read raises BadKey here: this coach needs it
            raise WebCoachUnavailable(_missing_key(persona))
        return persona.service
    if override:
        ok, reason = usable(override, persona, facts)
        if not ok:
            raise (cli.Usage if override not in ROUTES else SystemExit)(f"Can't render with {override} here: {reason}")
        return override
    known = []
    for route in preferences or ["local"]:
        if route not in ROUTES:
            print(f"Skipped '{route}' in the profile's render list: not a route ({', '.join(ROUTES)}).",
                  file=sys.stderr)
        else:
            known.append(route)
    if persona is not None and not persona.is_web:   # a local coach renders locally, whatever the list says
        ok, reason = usable("local", persona, facts)
        if ok:
            return "local"
        lines = [reason]
        if persona.has_clip and _facts(facts).get("local") == "no":   # name the way to a coach that speaks here
            lines.append(f"{persona.name} is a local coach, and local voices don't run here. The way out: "
                         + way_out())
        raise SystemExit(f"No audio route works on this computer for {persona.name}:\n  " + "\n  ".join(lines))
    reasons = []
    for route in known or ["local"]:
        ok, reason = usable(route, persona, facts)
        if ok:
            return route
        reasons.append(reason)
    raise SystemExit("No audio route works on this computer:\n  " + "\n  ".join(
        reasons + ["The way out: " + way_out()]))


def stand_ins():
    """{service: the web stand-in that ships for it in me.example/personas/}."""
    import personas
    return {p.service: p for p in personas.all(os.path.join(paths.EXAMPLE, "personas"))
            if p.is_web and p.service in SERVICES}


def way_out(folder=None):
    """How to get a coach that speaks here when local voices don't: make a web coach, or use the stand-in
    of a service with a key here (copied into the listener's coaches, `folder`, if it isn't there yet)."""
    import personas
    folder = folder or paths.PERSONAS
    shipped = stand_ins()
    have = {p.name for p in personas.all(folder)}
    make = 'make a web coach (the coach skill: "I want a new coach")'
    keyed = [s for s in SERVICES if keys.is_set(s) and s in shipped]
    if keyed:
        uses = []
        for s in keyed:
            p = shipped[s]
            uses.append(f"{p.name} ({cloud.service_name(s)}): " + (f"build with --coach \"{p.name}\"" if p.name in have
                        else f"copy {paths.show(p.path)} to {paths.show(os.path.join(folder, p.slug, 'persona.md'))}, then build with "
                             f"--coach \"{p.name}\""))
        return f"{make}, or use the stand-in for a service with a key here: " + "; ".join(uses) + "."
    add = ("set its key in the cloud environment's settings, under Environment variables" if paths.REMOTE
           else "./sweatcast keys init <service>, then paste the key into the file")
    names = ", ".join(f"{shipped[s].name} ({cloud.service_name(s)})" for s in SERVICES if s in shipped)
    return (f"{make}, or add a service's key ({add}) and use its stand-in: {names} (in "
            f"{paths.show(os.path.join(paths.EXAMPLE, 'personas'))}/; copy its persona.md to the same place in "
            f"{paths.show(folder)}/ if your coaches don't have it).")


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
        # a service line says whether its key is here; which coach speaks where shows in the last line
        ok, reason = usable(route, persona if route == "local" else None, facts)
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
