"""The clip cache (me/workouts/.audio-cache/): where each line's rendered clip is kept, keyed on everything that
changes how it sounds, and the take check's verdict beside it."""
import contextlib
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engines  # noqa: E402
from engines import SR, TRIM_DB, TRIM_KEEP  # noqa: E402
import paths  # noqa: E402


def clip_cache(voice, seed):
    """cache_path(text): where a line's clip is cached. Everything that changes how a clip sounds goes in
    its key, so changing a setting (or upgrading pocket-tts) re-renders instead of silently reusing old
    clips; the coach's name and any API key don't, so a renamed coach keeps its clips. A web service that hears
    the neighboring paragraphs (ElevenLabs) isn't keyed on them, deliberately: an edit would re-render, and
    re-bill, both neighbors of every changed paragraph, for a slightly different join."""
    settings = (f"{voice['model']}@{voice['revision'] or 'latest'}|{json.dumps(voice['generate'], sort_keys=True)}|"
                f"trim {TRIM_DB} {TRIM_KEEP}|{engines.runtime(voice)}")

    def cache_path(text):
        key = f"{voice['key']}|{voice['engine']}|{seed}|{settings}|{text}"
        return os.path.join(paths.CACHE, hashlib.sha256(key.encode()).hexdigest()[:24] + ".pcm")
    return cache_path


def render_clip(say, text, seed, cache_path, **context):
    """Speak one line into the cache; returns its seconds of audio. `context` (previous_text, next_text)
    goes to a cloud engine that joins paragraphs."""
    pcm = say(text, seed, **context)
    _cache_write(cache_path(text), pcm)
    with contextlib.suppress(FileNotFoundError):   # a new take hasn't been checked
        os.remove(check_path(cache_path, text))
    return len(pcm) / 2 / SR


def _cache_write(path, pcm):
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(pcm)
    os.replace(tmp, path)


def check_path(cache_path, text):
    """Where the verdict on a cached clip is kept, beside it (tools/cache.py prunes the two together)."""
    return cache_path(text)[: -len(".pcm")] + ".check.json"


def _verdict(path):
    try:
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
        return v if isinstance(v, dict) and "ok" in v and "missed_cues" in v else None
    except (OSError, ValueError):
        return None
