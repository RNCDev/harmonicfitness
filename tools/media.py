"""The stock coaches' 45-second samples, kept on the app's media bucket (tools/bucket.py) rather than in git:
coaches/samples.json lists each one (its bytes and SHA-256) with the bucket's public address, so the engine and the
web app know what's there without asking. A listener choosing a coach by ear gets a stock sample through
sample_file, fetched once into me/coaches/.samples/ (git-ignored) and checked against the list.
HARMONICFITNESS_MEDIA_URL points at another address (https, or this computer), as the tests' fake server does.
Library only.
"""
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request

import errors
import fileio
import net
import paths


def manifest_path():
    return os.path.join(paths.SHIPPED, "samples.json")


def manifest(path=None):
    """{"url": the bucket's public address, "samples": {slug: {"bytes", "sha256"}}}; empty when there's no list."""
    try:
        data = fileio.read_json(path or manifest_path())
    except FileNotFoundError:
        return {"url": "", "samples": {}}
    return {"url": str(data.get("url") or ""), "samples": dict(data.get("samples") or {})}


def base_url(m=None):
    override = os.environ.get("HARMONICFITNESS_MEDIA_URL")
    url = (override or (m or manifest())["url"]).rstrip("/")
    if not net.allowed_base(url):
        raise errors.UsageError(f"The media address {url!r} isn't https:// or this computer, so nothing was fetched.")
    return url


def sample_key(slug):
    return f"coaches/{slug}/sample.mp3"


def has_sample(slug, m=None):
    return slug in (m or manifest())["samples"]


def sample_url(slug, m=None):
    m = m or manifest()
    return f"{base_url(m)}/{sample_key(slug)}"


def sample_file(slug, m=None, opener=None):
    """A stock coach's sample as a local file: me/coaches/.samples/<slug>.mp3, fetched from the bucket when it isn't
    there or doesn't match the list. UsageError for a coach with no sample listed; HarmonicFitnessError when the
    fetch fails or the file doesn't match."""
    m = m or manifest()
    entry = m["samples"].get(slug)
    if not entry:
        raise errors.UsageError(f"No stock sample for {slug} in coaches/samples.json.")
    out = os.path.join(paths.PERSONAS, ".samples", f"{slug}.mp3")
    if os.path.isfile(out) and _sha256(out) == entry.get("sha256"):
        return out
    url = sample_url(slug, m)
    try:
        with (opener or net.opener("any").open)(url, timeout=60) as r:   # any redirect: the SHA-256 is checked
            body = r.read()
    except (urllib.error.URLError, OSError) as e:
        raise errors.HarmonicFitnessError(f"{slug}'s sample couldn't be fetched from {url}: {e}.") from None
    if hashlib.sha256(body).hexdigest() != entry.get("sha256"):
        raise errors.HarmonicFitnessError(f"{slug}'s sample at {url} doesn't match coaches/samples.json.")
    fileio.atomic_write(out, body)
    return out


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def entry(path):
    """The manifest entry for a sample file on disk."""
    return {"bytes": os.path.getsize(path), "sha256": _sha256(path)}


def write_manifest(url, samples, path=None):
    fileio.atomic_write(path or manifest_path(),
                        json.dumps({"url": url, "samples": dict(sorted(samples.items()))}, indent=1) + "\n")
