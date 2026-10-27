"""One module per web voice service (fish, elevenlabs, gemini, inworld), each with design(description, line,
n, label) -> candidates, save(candidate, name, description, wav) -> voice ID, delete(voice_id) -> bool, and
speaker(voice) -> say(text, seed, previous_text=None, next_text=None) returning 16-bit mono PCM at 24 kHz,
spoken by the web coach's saved voice ID, in that argument order (tests/test_cloud.py holds every module to it).
Optional: STORES_DRAFTS = True where design() saves each candidate at the service, so one not kept is deleted;
DESIGN_NOTE, what else a design costs there, said with its price. cloud.service_module(name) is the one lookup.
The shared core (HTTP, retries, errors, audio, cost) is tools/cloud.py; settings are knowledge/services.toml,
read by settings() here, which imports nothing of the engine's, so keys.py can read it without cloud.py."""
import functools
import os
import tomllib

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                             "knowledge", "services.toml")


@functools.cache
def settings():
    """{service: settings} from knowledge/services.toml, in its order, each with the file's rates_checked."""
    with open(SETTINGS_FILE, "rb") as f:
        data = tomllib.load(f)
    return {k: dict(v, rates_checked=data.get("rates_checked")) for k, v in data.items() if isinstance(v, dict)}

REQUIRED = {"speaker": ["voice"], "design": ["description", "line", "n", "label"],
            "save": ["candidate", "name", "description", "wav"], "delete": ["voice_id"]}
