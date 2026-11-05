"""Upload the stock coaches' samples to the media bucket and list them in coaches/samples.json (maintainer only; not a
listener command). The samples aren't kept in git: sample.py and web_coaches.py write each one into its coach's
folder (git-ignored there), this uploads every one it finds and records its bytes and SHA-256, and a listed sample
with no file here is kept as listed.

  .venv/bin/python tools/coachmaker/upload_samples.py            # every coaches/*/sample.mp3 on disk
  .venv/bin/python tools/coachmaker/upload_samples.py andy maya   # only those

The bucket's keys come from the environment (tools/bucket.py): AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, BUCKET_NAME.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bucket  # noqa: E402
import media  # noqa: E402
import paths  # noqa: E402


def main(argv):
    m = media.manifest()
    name = os.environ.get("BUCKET_NAME", "harmonicfitness-media")
    url = bucket.PUBLIC.format(bucket=name, key="").rstrip("/")
    samples = dict(m["samples"])
    for slug in sorted(os.listdir(paths.SHIPPED)):
        path = os.path.join(paths.SHIPPED, slug, "sample.mp3")
        if not os.path.isfile(path) or (argv and not any(slug == f"coach-{a}" or slug.startswith(f"coach-{a}-")
                                                         or slug == a for a in argv)):
            continue
        with open(path, "rb") as f:
            body = f.read()
        bucket.put(media.sample_key(slug), body)
        samples[slug] = media.entry(path)
        print(f"{slug}: {len(body):,} bytes")
    media.write_manifest(url, samples)
    print(f"{len(samples)} samples listed in {paths.show(media.manifest_path())}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
