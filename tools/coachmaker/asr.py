"""Transcribe WAVs for the coach tools with the take checker's recognizer: Parakeet TDT 0.6B v3 through ONNX, on
the processor, the same on a Mac and a PC (engines.listener, in the engine's own environment).

Not the 110M Parakeet: on the ten coaches' Pocket takes (2026-10-26) it heard about twice as many lines wrong
as the 0.6B, and reported cues as dropped that the 0.6B heard said."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402


def transcribe(wavs, work=None):
    """{wav path: what was heard}. `work` is kept for the callers' sake; nothing is written there now."""
    return common.transcribe(list(wavs))
