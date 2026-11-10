"""The one place the engine opens a web address (0.76.2): every module makes its requests through `opener`, which
always carries verified TLS (`tls_context`) and follows a redirect only as the caller says.

A leaf: it imports only the standard library, and certifi when it's there. Named net, not http, so it never shadows
the standard library's http package (tools/ is first on the path).
"""
import functools
import os
import ssl
import urllib.parse
import urllib.request

MACOS_ROOTS = "/etc/ssl/cert.pem"
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")
FOLLOW = ("never", "web", "same-host", "any")


class Redirected(OSError):
    """A redirect an opener wouldn't follow: `url` where it pointed, `status` its HTTP status. Each caller says it in
    its own words (a redirect never sends a key, a session or signed headers anywhere else)."""

    def __init__(self, url: str, status: int):
        super().__init__(f"redirected to {url} (HTTP {status})")
        self.url, self.status = url, status


class TooLarge(OSError):
    """An answer longer than the reader would take."""


@functools.cache
def tls_context() -> ssl.SSLContext:
    """Verified TLS, made once. A python.org Python ships without root certificates until its Install Certificates
    step runs, so certifi's bundle, else macOS's when the interpreter has none, else the default."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except (ImportError, OSError):
        pass
    paths = ssl.get_default_verify_paths()
    has_roots = paths.cafile or (paths.capath and os.path.isdir(paths.capath) and os.listdir(paths.capath))
    if not has_roots and os.path.exists(MACOS_ROOTS):
        return ssl.create_default_context(cafile=MACOS_ROOTS)
    return ssl.create_default_context()


def check_scheme(url: str) -> None:
    """ValueError unless `url` is http or https."""
    scheme = urllib.parse.urlsplit(url).scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"only http and https addresses are fetched, not {scheme or 'this'}: {url[:80]}")


class _Never(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        fp.close()
        raise Redirected(urllib.parse.urljoin(req.full_url, newurl), code)


class _Web(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to another http or https address (the default handler would follow ftp too)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_scheme(urllib.parse.urljoin(req.full_url, newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _SameHost(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to the same scheme and host: the request's headers (a token) go with it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        to = urllib.parse.urljoin(req.full_url, newurl)
        here, there = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(to)
        if (here.scheme, here.netloc.lower()) != (there.scheme, there.netloc.lower()):
            fp.close()
            raise Redirected(to, code)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_REDIRECTS = {"never": _Never, "web": _Web, "same-host": _SameHost, "any": urllib.request.HTTPRedirectHandler}


def opener(follow: str = "never", *handlers) -> urllib.request.OpenerDirector:
    """An opener that follows redirects as `follow` says ("never": raise Redirected; "web": only to http or https;
    "same-host": only to the same host; "any": as urllib does), with HTTPS on tls_context(). `handlers` are added
    after; one of them that opens https (feeds' vetted handler) is then the only one that does."""
    if follow not in _REDIRECTS:
        raise ValueError(f"follow must be one of {', '.join(FOLLOW)}, not {follow!r}")
    own_https = any(isinstance(h, urllib.request.HTTPSHandler)
                    or (isinstance(h, type) and issubclass(h, urllib.request.HTTPSHandler)) for h in handlers)
    first = [] if own_https else [urllib.request.HTTPSHandler(context=tls_context())]
    return urllib.request.build_opener(_REDIRECTS[follow], *first, *handlers)


def allowed_base(url: str) -> bool:
    """Whether a base address may be used: https, or plain http only to this computer."""
    parts = urllib.parse.urlsplit(url or "")
    scheme = parts.scheme.lower()
    return scheme == "https" or (scheme == "http" and parts.hostname in LOCAL_HOSTS)


def read_capped(resp, limit: int) -> bytes:
    """At most `limit` bytes of `resp`; TooLarge when there are more."""
    body = resp.read(limit + 1)
    if len(body) > limit:
        raise TooLarge(f"the answer is over {limit} bytes")
    return body
