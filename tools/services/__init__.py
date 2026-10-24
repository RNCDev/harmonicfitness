"""One module per cloud voice service, each with speaker(voice) -> say(text, seed, previous_text=None,
next_text=None) returning 16-bit mono PCM at 24 kHz, and design() where the service designs voices.
The shared core (HTTP, retries, errors, audio, cost) is tools/cloud.py; settings are knowledge/services.toml."""
