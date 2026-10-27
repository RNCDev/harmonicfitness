"""The engine's shape: no two tool modules import each other (a lazy import inside a function counts), and the
voice dict every layer passes keeps its exact keys, order and cache key, so a refactor can't change a clip's key
or a build record."""
import ast
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402,F401  (puts tools/ on the path)
import paths  # noqa: E402

TOOLS = os.path.join(paths.ROOT, "tools")

# Pairs of modules that still import each other, each with why. Shrink it; never grow it.
CYCLES = {
    ("coachpick", "personas"): "personas.default and resolve re-export coachpick's until the next minor release",
    ("coachpick", "routes"): "routes.pick re-exports coachpick's until the next minor release",
    ("coachpick", "context"): "context.main is the get command (get coach, get route); the library doesn't import back",
    ("context", "logsession"): "context.main is the log-session command; the library doesn't import back",
}


def modules():
    """{module name: file} for tools/*.py and tools/services/*.py (services.<name>; the package as services)."""
    out = {f[:-3]: os.path.join(TOOLS, f) for f in os.listdir(TOOLS) if f.endswith(".py")}
    sdir = os.path.join(TOOLS, "services")
    for f in os.listdir(sdir):
        if f.endswith(".py"):
            out["services" if f == "__init__.py" else f"services.{f[:-3]}"] = os.path.join(sdir, f)
    return out


def import_graph():
    """{module: the sibling modules it imports anywhere in its file, at the top or inside a function}."""
    mods = modules()
    graph = {}
    for name, path in mods.items():
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), path)
        out = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                out |= {a.name for a in node.names if a.name in mods}
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                if node.module in mods:
                    out.add(node.module)
                out |= {f"{node.module}.{a.name}" for a in node.names if f"{node.module}.{a.name}" in mods}
        out.discard(name)
        graph[name] = out
    return graph


def two_cycles(graph):
    return {(a, b) for a in graph for b in graph[a] if a < b and a in graph.get(b, ())}


def top_level_graph():
    """{module: the sibling modules it imports when it's loaded}: the module's own statements (and those in its
    top-level if/try blocks), not a function's body, nor the `if __name__ == "__main__":` block a script runs."""
    mods = modules()

    def main_block(node):
        t = node.test
        return (isinstance(node, ast.If) and isinstance(t, ast.Compare) and isinstance(t.left, ast.Name)
                and t.left.id == "__name__")

    def walk(body, out):
        for node in body:
            if isinstance(node, ast.Import):
                out |= {a.name for a in node.names if a.name in mods}
            elif isinstance(node, ast.ImportFrom) and node.module in mods and node.level == 0:
                out.add(node.module)
            elif isinstance(node, ast.If) and not main_block(node):
                walk(node.body, out)
                walk(node.orelse, out)
            elif isinstance(node, ast.Try):
                for part in (node.body, node.orelse, node.finalbody, *(h.body for h in node.handlers)):
                    walk(part, out)
    graph = {}
    for name, path in mods.items():
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), path)
        out = set()
        walk(tree.body, out)
        out.discard(name)
        graph[name] = out
    return graph


def cycle_from(graph, start):
    """A path of imports from `start` back to itself, or None."""
    stack, seen = [(start, [start])], set()
    while stack:
        node, path = stack.pop()
        for nxt in sorted(graph.get(node, ())):
            if nxt == start:
                return path + [start]
            if nxt not in seen:
                seen.add(nxt)
                stack.append((nxt, path + [nxt]))
    return None


class ImportCycles(unittest.TestCase):
    def test_no_two_modules_import_each_other_beyond_the_allowlist(self):
        found = two_cycles(import_graph())
        self.assertEqual(sorted(found - set(CYCLES)), [], "new import cycles: break them (a module above both)")
        self.assertEqual(sorted(set(CYCLES) - found), [], "cycles gone: take them off CYCLES")

    def test_no_module_imports_itself_back_when_loaded(self):
        """Read from the top, every module's imports load without coming back to it, however long the loop
        (cli -> redact -> keys -> cli was one, hidden by imports inside functions)."""
        graph = top_level_graph()
        loops = [" -> ".join(c) for c in (cycle_from(graph, m) for m in sorted(graph)) if c]
        self.assertEqual(loops, [], "an import loop at load time: move the shared piece below both")

    def test_the_command_line_scrubs_keys_without_a_loop(self):
        """cli imports redact at its top, redact imports keys at its top, and keys reads its exit code from
        errors: only keys' own command (main) reaches for cli."""
        graph = top_level_graph()
        self.assertIn("redact", graph["cli"])
        self.assertIn("keys", graph["redact"])
        self.assertNotIn("cli", graph["keys"])
        import errors
        import keys
        self.assertTrue(issubclass(keys.BadKey, errors.SweatcastError))
        self.assertEqual(keys.BadKey("x").exit_code, errors.SERVICE)
        self.assertEqual((keys.BadKey.kind, keys.BadKey.listener_must_act), ("auth", True))


class Reexports(unittest.TestCase):
    def test_the_old_names_still_choose_through_coachpick(self):
        import coachpick
        import personas
        import routes
        with mock.patch.object(coachpick, "default", return_value="d"), \
                mock.patch.object(coachpick, "resolve", return_value="r"), \
                mock.patch.object(coachpick, "pick", return_value="p"):
            self.assertEqual((personas.default(), personas.resolve("x"), routes.pick(["local"])), ("d", "r", "p"))


# Names that live in their own modules now: callers reach them there, not through context's re-exports.
MOVED = {
    "frontmatter": "TOML_FRONT_RE front body toml_value dump_settings section placeholder unfilled",
    "store": "SCHEMA PERSONA_SCHEMA split schema_of schema_problem read_raw read write with_front_matter",
    "health": "HTML_COMMENT_RE INJURIES_HEADING CLINICIAN_HEADING Health health LIMIT_KEYS _limit_row _vocab "
              "limit_rows limits _section_lines limit_line clinician_lines UNLISTED AVOID clinician_avoids "
              "prose_injury_count prose_injuries prose_injury_gap LIMIT_SIDES LIMIT_LEVELS",
    "sessionlog": "DATE_RE LINE_BREAKS Session parse_session log sessions append_session",
    "records": "draft_hash build_records built latest_build web_builds",
    "logsession": "log_session from_draft build_coach menu_kit named_pairs declared_movements _catalog",
    "tomllib": "tomllib",
}


class ContextReexports(unittest.TestCase):
    def test_moved_names_are_reached_in_their_own_modules(self):
        import re
        home = {n: m for m, names in MOVED.items() for n in names.split()}
        found = []
        for folder in (TOOLS, os.path.join(TOOLS, "services"), os.path.join(TOOLS, "coachmaker"),
                       os.path.join(paths.ROOT, "tests")):
            for name in sorted(os.listdir(folder)):
                if not name.endswith(".py") or (folder == TOOLS and name == "context.py"):
                    continue
                with open(os.path.join(folder, name), encoding="utf-8") as f:
                    text = f.read()
                found += [f"{name}: context.{w} (use {home[w]})" for w in re.findall(r"(?<![\w.])context\.(\w+)", text)
                          if w in home]
                for m in re.finditer(r"^from context import (\([^)]*\)|.*)$", text, re.M):
                    found += [f"{name}: from context import {w} (use {home[w]})"
                              for w in re.findall(r"\w+", m.group(1)) if w in home]
        self.assertEqual(found, [])
        import context
        for private in ("_limit_row", "_vocab", "_section_lines", "_catalog"):
            self.assertFalse(hasattr(context, private), private)


def shapes(d):
    """{"local": (dict, cache key), "web": ..., "web pending": ...} for fixture coaches, with the temp home and
    the stock folder written as <home> and <shipped>."""
    import clipcache
    import context
    import engines
    import personas
    out = {}
    with helpers.home(d), mock.patch.object(engines, "_version", return_value="X"):
        coaches = os.path.join(d, "coaches")
        made = os.path.join(coaches, "coach-pin-fish")
        os.makedirs(made)
        with open(os.path.join(made, "persona.md"), "w", encoding="utf-8") as f:
            f.write(context.persona_text({"name": "Coach Pin", "kind": "web", "service": "fish",
                                          "voice_id": "voice_pin1", "settings": {"speed": 1.0}}, "Notes.\n"))
        cases = {"local": (personas.lookup("Coach Andy"), "local", False),
                 "web": (personas.lookup("Coach Pin"), "fish", False),
                 "web pending": (personas.lookup("Coach Reed"), "fish", True)}
        for kind, (p, route, pending) in cases.items():
            v = personas.voice_for(p, route, pending)
            key = os.path.basename(clipcache.clip_cache(v, 7)("Hello there."))
            out[kind] = ({k: rel(x, d) for k, x in v.items()}, key)
    return out


def rel(value, home):
    if not isinstance(value, str):
        return value
    for root, mark in ((os.path.abspath(paths.SHIPPED), "<shipped>"), (os.path.abspath(home), "<home>")):
        if value.startswith(root + os.sep):
            return mark + "/" + os.path.relpath(value, root).replace(os.sep, "/")
    return value


EXPECTED = {
    'local': ([
        ('name', 'Coach Andy'),
        ('persona', 'coach-andy-local'),
        ('engine', 'pocket'),
        ('backend', 'torch'),
        ('route', 'local'),
        ('model', 'kyutai/pocket-tts-without-voice-cloning'),
        ('revision', 'a7056f505a4a8ca72d8b5fb1440071d6f1a35739'),
        ('language', 'english_2026-10'),
        ('generate', {}),
        ('voice_state', '<shipped>/coach-andy-local/pocket.safetensors'),
        ('ref_audio', '<shipped>/coach-andy-local/clip.wav'),
        ('ref_text', "Alright, let's get to work. Set your feet about shoulder width, chest up, and breathe in. Lower down slow, two, three, and drive back up. Good. That's exactly the pace we want. Four more, stay with me. Last one, and rest. Shake it out, take a sip of water. Next we switch sides, left leg forward for thirty seconds, and we'll go again."),
        ('key', 'c2f08b6a5189'),
        ('pace_file', '<home>/workouts/.audio-cache/voice-pace.json'),
        ('pace_seed', '<shipped>/coach-andy-local/pace.json'),
        ('cues', None),
    ], '6cee77b0899219493239da02.pcm'),
    'web': ([
        ('name', 'Coach Pin'),
        ('persona', 'coach-pin-fish'),
        ('persona_dir', '<home>/coaches/coach-pin-fish'),
        ('engine', 'fish'),
        ('backend', 'cloud'),
        ('route', 'fish'),
        ('service', 'fish'),
        ('model', 's2.1-pro'),
        ('voice_id', 'voice_pin1'),
        ('style', ''),
        ('revision', None),
        ('generate', {}),
        ('pace_file', '<home>/coaches/coach-pin-fish/pace.json'),
        ('concurrency', 5),
        ('max_chars', 0),
        ('key', 'e55af8385afb'),
    ], 'cea70155e22c0519fc9003d9.pcm'),
    'web pending': ([
        ('name', 'Coach Reed'),
        ('persona', 'coach-reed-fish'),
        ('persona_dir', '<shipped>/coach-reed-fish'),
        ('engine', 'fish'),
        ('backend', 'cloud'),
        ('route', 'fish'),
        ('service', 'fish'),
        ('model', 's2.1-pro'),
        ('voice_id', None),
        ('style', ''),
        ('revision', None),
        ('generate', {}),
        ('pace_file', '<home>/coaches/coach-reed-fish/pace.json'),
        ('concurrency', 5),
        ('max_chars', 0),
        ('key', '339b21d2e7f0'),
    ], '5511bc3c538027701527bc7b.pcm'),
}


class VoiceShapes(unittest.TestCase):
    def test_each_voice_dict_keeps_its_keys_order_and_cache_key(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            got = shapes(d)
        for kind, (items, key) in EXPECTED.items():
            v, k = got[kind]
            self.assertEqual(list(v.items()), items, kind)
            self.assertEqual(k, key, kind)

    def test_a_voice_dict_reads_back_as_its_dataclass(self):
        import tempfile
        import voice
        with tempfile.TemporaryDirectory() as d:
            got = shapes(d)
        for kind, cls in (("local", voice.LocalVoice), ("web", voice.WebVoice), ("web pending", voice.WebVoice)):
            v = voice.from_dict(got[kind][0])
            self.assertIsInstance(v, cls)
            self.assertEqual(list(v.as_dict().items()), list(got[kind][0].items()))
        with self.assertRaises(ValueError):
            voice.from_dict({"backend": "cloud", "name": "x"})


if __name__ == "__main__":
    unittest.main()
