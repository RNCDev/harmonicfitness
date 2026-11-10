"""The app's public media bucket on Fly (Tigris, S3's API): the stock coaches' 45-second samples and the home page's
demo clips, uploaded by the maintainer, read by anyone over plain https.

    coaches/<slug>/sample.mp3     a stock coach's sample (coaches/samples.json lists them)
    demos/v<version>/<slug>.mp3   a demo clip (docs/demos/demos.toml)

Reading needs nothing: public_url(key). Writing (put) needs the bucket's keys in the environment, as Fly sets them
on the app: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, BUCKET_NAME and AWS_ENDPOINT_URL_S3 (default Tigris's). Each
request is signed with AWS Signature Version 4 here, with the standard library, so the engine needs no S3 package.
The secret never leaves this module and is never printed. Library only.
"""
import datetime
import hashlib
import hmac
import os
import urllib.error
import urllib.parse
import urllib.request

import errors
import net

ENDPOINT = "https://fly.storage.tigris.dev"
REGION = "auto"
PUBLIC = "https://{bucket}.fly.storage.tigris.dev/{key}"


def public_url(key, bucket):
    return PUBLIC.format(bucket=bucket, key=urllib.parse.quote(key))


def _credentials(env=os.environ):
    missing = [v for v in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "BUCKET_NAME") if not env.get(v)]
    if missing:
        raise errors.UsageError("The bucket's keys aren't set here (" + ", ".join(missing) + "): they are the app's "
                                "Fly secrets; set them in your own shell to upload.")
    endpoint = (env.get("AWS_ENDPOINT_URL_S3") or ENDPOINT).rstrip("/")
    if not endpoint.startswith("https://"):
        raise errors.UsageError("AWS_ENDPOINT_URL_S3 isn't an https:// address, so nothing was sent.")
    return env["AWS_ACCESS_KEY_ID"], env["AWS_SECRET_ACCESS_KEY"], env["BUCKET_NAME"], endpoint


def _sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def signed_headers(method, url, body, access, secret, content_type, now=None):
    """The headers for one S3 request, signed with Signature Version 4 (path-style, region auto)."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    stamp, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    parts = urllib.parse.urlsplit(url)
    payload = hashlib.sha256(body).hexdigest()
    headers = {"content-type": content_type, "host": parts.netloc, "x-amz-content-sha256": payload,
               "x-amz-date": stamp}
    names = ";".join(sorted(headers))
    canonical = "\n".join([method, parts.path or "/", parts.query,
                           "".join(f"{k}:{headers[k]}\n" for k in sorted(headers)), names, payload])
    scope = f"{day}/{REGION}/s3/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    k = _sign(_sign(_sign(_sign(("AWS4" + secret).encode(), day), REGION), "s3"), "aws4_request")
    signature = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    headers["authorization"] = (f"AWS4-HMAC-SHA256 Credential={access}/{scope}, SignedHeaders={names}, "
                                f"Signature={signature}")
    return headers


def put(key, body, content_type="audio/mpeg", env=os.environ, opener=None):
    """Upload `body` to `key` in the bucket; returns its public URL. HarmonicFitnessError names a refusal."""
    access, secret, bucket, endpoint = _credentials(env)
    url = f"{endpoint}/{bucket}/{urllib.parse.quote(key)}"
    headers = signed_headers("PUT", url, body, access, secret, content_type)
    req = urllib.request.Request(url, data=body, method="PUT", headers=headers)
    opener = opener or net.opener("never")   # a redirect is never followed, so signed headers go nowhere else
    try:
        with opener.open(req, timeout=120) as r:
            r.read()
    except urllib.error.HTTPError as e:
        raise errors.HarmonicFitnessError(f"The bucket refused {key}: HTTP {e.code}.") from None
    except net.Redirected as e:   # a redirect is a refusal, as the bucket's other answers are
        raise errors.HarmonicFitnessError(f"The bucket refused {key}: HTTP {e.status}.") from None
    except (urllib.error.URLError, OSError) as e:
        raise errors.HarmonicFitnessError(f"The bucket couldn't be reached for {key}: {e}.") from None
    return public_url(key, bucket)
