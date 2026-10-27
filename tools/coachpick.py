"""Which coach a build takes, and on which route: above personas (the coaches) and routes (what renders here),
so neither needs the other's choice.

    default()      the coach used last, else the listener's own, else a stand-in that can speak here
    pick(...)      the route a build takes for a coach
    resolve(...)   the voice dict for a named coach (or the default) on its route
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cloud  # noqa: E402
import context  # noqa: E402
import errors  # noqa: E402
import keys  # noqa: E402
import personas  # noqa: E402
import routes  # noqa: E402
import sessionlog  # noqa: E402


def _usable_here(p):
    """Whether stand-in `p` can speak on this computer: a web coach's service has a key, a local coach's
    engine runs here."""
    if p.is_web:
        return bool(p.service) and p.service in keys.SERVICE_VARS and keys.is_set(p.service)
    return routes.usable("local", p)[0]


def default(folder=None):
    """The coach a build uses when none is named: the one used last (from the log), stopping if that one
    is archived, and passing over a stand-in used last for a coach of the listener's own that can speak here; else the
    first that isn't a stand-in; else the first stand-in that can speak here (web ones whose service has a
    key, in service order, then local ones); else the first."""
    found = personas.all(folder)
    if not found:
        return None
    archived = personas.all(personas._archive(folder))
    try:
        sessions = list(reversed(sessionlog.sessions(warn=False)))
    except errors.PROBLEMS:   # no log yet, or one in an older format
        sessions = []
    for session in sessions:
        p = personas.find(session.voice, found)
        if p is not None:
            if p.placeholder:   # their own coach beats a stand-in used last, if it can speak here
                own = next((o for o in found if not o.placeholder and not o.shipped and _usable_here(o)), None)
                return own or p
            return p
        old = personas.find(session.voice, archived)
        if old is not None:
            raise errors.CoachError(f"{old.name} is archived; name a coach: {', '.join(p.name for p in found)}.")
    own = next((p for p in found if not p.placeholder and not p.shipped), None)
    if own is not None:
        return own
    order = lambda p: (not p.is_web, cloud.SERVICES.index(p.service) if p.service in cloud.SERVICES else 99)
    return next((p for p in sorted(found, key=order) if _usable_here(p)), found[0])


def coach(name=None):
    """Coach `name` (a folder name, name or alias), else the default; None when there are no coaches."""
    return personas.lookup(name) if name else default()


def resolve(coach=None, engine=None, pending=False):
    """The voice dict a build uses: `coach` (else the one used last) on `engine` (else the first route in the
    profile's render list that works on this computer). With `pending`, a web coach still to be made gets
    its estimated voice (the lint and the brief; never the render)."""
    p = personas.lookup(coach) if coach else default()
    if p is None:
        raise errors.CoachError("No coach yet: choose one (./sweatcast coaches lists them), or make a web coach (the coach skill).")
    return personas.voice_for(p, pick(context.render_preferences(), p, override=engine), pending)


def pick(preferences, persona=None, override=None, facts=None):
    """The route a build takes: a web coach's own service (whatever the render list, and only if keyed here);
    else `override` (--engine) if it works here; else the first usable preference."""
    ROUTES, SERVICES = routes.ROUTES, routes.SERVICES
    if persona is not None and persona.is_web:
        if not persona.service or persona.service not in SERVICES:
            raise routes.WebCoachUnavailable(f"{persona.name} is a web coach with no known service "
                                             f"({persona.service or 'none'}); the services are {', '.join(SERVICES)}.")
        if override and override != persona.service:
            raise routes.WebCoachUnavailable(
                f"{persona.name} speaks through {cloud.service_name(persona.service)} only, so --engine {override} "
                f"can't render them here.")
        if not keys.get(persona.service):   # a key that can't be read raises BadKey here: this coach needs it
            raise routes.WebCoachUnavailable(routes.missing_key(persona))
        return persona.service
    if override:
        ok, reason = routes.usable(override, persona, facts)
        if not ok:
            raise (errors.UsageError if override not in ROUTES else errors.RouteUnavailable)(f"Can't render with {override} here: {reason}")
        return override
    known = []
    for route in preferences or ["local"]:
        if route not in ROUTES:
            print(f"Skipped '{route}' in the profile's render list: not a route ({', '.join(ROUTES)}).",
                  file=sys.stderr)
        else:
            known.append(route)
    if persona is not None and not persona.is_web:   # a local coach renders locally, whatever the list says
        ok, reason = routes.usable("local", persona, facts)
        if ok:
            return "local"
        lines = [reason]
        if persona.has_clip and routes.computer(facts).get("local") == "no":   # name the way to a coach that speaks here
            lines.append(f"{persona.name} is a local coach, and local voices don't run here. The way out: "
                         + routes.way_out())
        raise errors.RouteUnavailable(f"No audio route works on this computer for {persona.name}:\n  " + "\n  ".join(lines))
    reasons = []
    for route in known or ["local"]:
        ok, reason = routes.usable(route, persona, facts)
        if ok:
            return route
        reasons.append(reason)
    raise errors.RouteUnavailable("No audio route works on this computer:\n  " + "\n  ".join(
        reasons + ["The way out: " + routes.way_out()]))


def report_lines(persona=None, preferences=None, facts=None):
    """The readiness check's Routes section."""
    out = []
    for route in routes.ROUTES:
        # a service line says whether its key is here; which coach speaks where shows in the last line
        ok, reason = routes.usable(route, persona if route == "local" else None, facts)
        label = "works here" if ok else reason.split(": ", 1)[-1]
        if route in routes.SERVICES and not cloud.services()[route].get("tried_live"):
            label += " (not yet tried live)"
        out.append(f"  {route:10} {label}")
    try:
        out.append(f"  A build here would use: {pick(preferences, persona, facts=facts)}"
                   + (f" (for {persona.name})" if persona else ""))
    except errors.PROBLEMS:
        out.append("  A build here would find no route that works (see above).")
    return out
