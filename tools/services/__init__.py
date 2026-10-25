"""One module per web voice service (fish, elevenlabs, gemini, inworld), each with design(description, line,
n, label) -> candidates, save(candidate, name, description, wav) -> voice ID, delete(voice_id) -> bool, and
speaker(voice) -> say(text, seed, previous_text=None, next_text=None) returning 16-bit mono PCM at 24 kHz,
spoken by the web coach's saved voice ID. The shared core (HTTP, retries, errors, audio, cost) is
tools/cloud.py; settings are knowledge/services.toml."""
