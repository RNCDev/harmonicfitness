#!/usr/bin/env python3
# Copyright    2026  Xiaomi Corp.        (authors:  Han Zhu)
#
# OmniVoice: https://github.com/k2-fsa/OmniVoice (see its LICENSE for the authors)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Vendored into sweatcast from OmniVoice's omnivoice/utils/duration.py
# (RuleDurationEstimator: the weights table, the Unicode ranges and the per-character
# rule, unchanged), so the lint predicts Chatterbox and Qwen3 voices without
# VoiceStudio's files. tests/test_tools.py checks it still matches OmniVoice's copy
# whenever VoiceStudio is installed.

"""Weighted character count: relative speaking time of text, 1.0 per Latin letter."""
import bisect
import unicodedata
from functools import lru_cache

WEIGHTS = {
    # --- Logographic (1 char = full syllable/word) ---
    "cjk": 3.0,  # Chinese, Japanese Kanji, etc.
    # --- Syllabic / Blocks
    "hangul": 2.5,  # Korean Hangul
    "kana": 2.2,  # Japanese Hiragana/Katakana
    "ethiopic": 3.0,  # Amharic/Ge'ez
    "yi": 3.0,  # Yi script
    # --- Abugida (Consonant-Vowel complexes) ---
    "indic": 1.8,  # Hindi, Bengali, Tamil, etc.
    "thai_lao": 1.5,  # Thai, Lao
    "khmer_myanmar": 1.8,  # Khmer, Myanmar
    # --- Abjad (Consonant-heavy) ---
    "arabic": 1.5,  # Arabic, Persian, Urdu
    "hebrew": 1.5,  # Hebrew
    # --- Alphabet (Segmental) ---
    "latin": 1.0,  # English, Spanish, French, Vietnamese, etc. (Baseline)
    "cyrillic": 1.0,  # Russian, Ukrainian
    "greek": 1.0,  # Greek
    "armenian": 1.0,  # Armenian
    "georgian": 1.0,  # Georgian
    # --- Symbols & Misc ---
    "punctuation": 0.5,  # Pause capability
    "space": 0.2,  # Word boundary/Breath (0.05 / 0.22)
    "digit": 3.5,  # Numbers
    "mark": 0.0,  # Diacritics/Accents (Silent modifiers)
    "default": 1.0,  # Fallback for unknown scripts
}

RANGES = [
    (0x02AF, "latin"),  # Latin (Basic, Supplement, Ext, IPA)
    (0x03FF, "greek"),  # Greek & Coptic
    (0x052F, "cyrillic"),  # Cyrillic
    (0x058F, "armenian"),  # Armenian
    (0x05FF, "hebrew"),  # Hebrew
    (0x077F, "arabic"),  # Arabic, Syriac, Arabic Supplement
    (0x089F, "arabic"),  # Arabic Extended-B (+ Syriac Supp)
    (0x08FF, "arabic"),  # Arabic Extended-A
    (0x097F, "indic"),  # Devanagari
    (0x09FF, "indic"),  # Bengali
    (0x0A7F, "indic"),  # Gurmukhi
    (0x0AFF, "indic"),  # Gujarati
    (0x0B7F, "indic"),  # Oriya
    (0x0BFF, "indic"),  # Tamil
    (0x0C7F, "indic"),  # Telugu
    (0x0CFF, "indic"),  # Kannada
    (0x0D7F, "indic"),  # Malayalam
    (0x0DFF, "indic"),  # Sinhala
    (0x0EFF, "thai_lao"),  # Thai & Lao
    (0x0FFF, "indic"),  # Tibetan (Abugida)
    (0x109F, "khmer_myanmar"),  # Myanmar
    (0x10FF, "georgian"),  # Georgian
    (0x11FF, "hangul"),  # Hangul Jamo
    (0x137F, "ethiopic"),  # Ethiopic
    (0x139F, "ethiopic"),  # Ethiopic Supplement
    (0x13FF, "default"),  # Cherokee
    (0x167F, "default"),  # Canadian Aboriginal Syllabics
    (0x169F, "default"),  # Ogham
    (0x16FF, "default"),  # Runic
    (0x171F, "default"),  # Tagalog (Baybayin)
    (0x173F, "default"),  # Hanunoo
    (0x175F, "default"),  # Buhid
    (0x177F, "default"),  # Tagbanwa
    (0x17FF, "khmer_myanmar"),  # Khmer
    (0x18AF, "default"),  # Mongolian
    (0x18FF, "default"),  # Canadian Aboriginal Syllabics Ext
    (0x194F, "indic"),  # Limbu
    (0x19DF, "indic"),  # Tai Le & New Tai Lue
    (0x19FF, "khmer_myanmar"),  # Khmer Symbols
    (0x1A1F, "indic"),  # Buginese
    (0x1AAF, "indic"),  # Tai Tham
    (0x1B7F, "indic"),  # Balinese
    (0x1BBF, "indic"),  # Sundanese
    (0x1BFF, "indic"),  # Batak
    (0x1C4F, "indic"),  # Lepcha
    (0x1C7F, "indic"),  # Ol Chiki (Santali)
    (0x1C8F, "cyrillic"),  # Cyrillic Extended-C
    (0x1CBF, "georgian"),  # Georgian Extended
    (0x1CCF, "indic"),  # Sundanese Supplement
    (0x1CFF, "indic"),  # Vedic Extensions
    (0x1D7F, "latin"),  # Phonetic Extensions
    (0x1DBF, "latin"),  # Phonetic Extensions Supplement
    (0x1DFF, "default"),  # Combining Diacritical Marks Supplement
    (0x1EFF, "latin"),  # Latin Extended Additional (Vietnamese)
    (0x309F, "kana"),  # Hiragana
    (0x30FF, "kana"),  # Katakana
    (0x312F, "cjk"),  # Bopomofo (Pinyin)
    (0x318F, "hangul"),  # Hangul Compatibility Jamo
    (0x9FFF, "cjk"),  # CJK Unified Ideographs (Main)
    (0xA4CF, "yi"),  # Yi Syllables
    (0xA4FF, "default"),  # Lisu
    (0xA63F, "default"),  # Vai
    (0xA69F, "cyrillic"),  # Cyrillic Extended-B
    (0xA6FF, "default"),  # Bamum
    (0xA7FF, "latin"),  # Latin Extended-D
    (0xA82F, "indic"),  # Syloti Nagri
    (0xA87F, "default"),  # Phags-pa
    (0xA8DF, "indic"),  # Saurashtra
    (0xA8FF, "indic"),  # Devanagari Extended
    (0xA92F, "indic"),  # Kayah Li
    (0xA95F, "indic"),  # Rejang
    (0xA97F, "hangul"),  # Hangul Jamo Extended-A
    (0xA9DF, "indic"),  # Javanese
    (0xA9FF, "khmer_myanmar"),  # Myanmar Extended-B
    (0xAA5F, "indic"),  # Cham
    (0xAA7F, "khmer_myanmar"),  # Myanmar Extended-A
    (0xAADF, "indic"),  # Tai Viet
    (0xAAFF, "indic"),  # Meetei Mayek Extensions
    (0xAB2F, "ethiopic"),  # Ethiopic Extended-A
    (0xAB6F, "latin"),  # Latin Extended-E
    (0xABBF, "default"),  # Cherokee Supplement
    (0xABFF, "indic"),  # Meetei Mayek
    (0xD7AF, "hangul"),  # Hangul Syllables
    (0xFAFF, "cjk"),  # CJK Compatibility
    (0xFDFF, "arabic"),  # Arabic Presentation Forms-A
    (0xFE6F, "default"),  # Variation Selectors
    (0xFEFF, "arabic"),  # Arabic Presentation Forms-B
    (0xFFEF, "latin"),  # Fullwidth Latin
]
BREAKPOINTS = [r[0] for r in RANGES]


@lru_cache(maxsize=4096)
def char_weight(char):
    code = ord(char)
    if (65 <= code <= 90) or (97 <= code <= 122):
        return WEIGHTS["latin"]
    if code == 32:
        return WEIGHTS["space"]
    if code == 0x0640:   # Arabic tatweel
        return WEIGHTS["mark"]
    category = unicodedata.category(char)
    if category.startswith("M"):
        return WEIGHTS["mark"]
    if category.startswith("P") or category.startswith("S"):
        return WEIGHTS["punctuation"]
    if category.startswith("Z"):
        return WEIGHTS["space"]
    if category.startswith("N"):
        return WEIGHTS["digit"]
    idx = bisect.bisect_left(BREAKPOINTS, code)
    if idx < len(RANGES):
        return WEIGHTS.get(RANGES[idx][1], WEIGHTS["default"])
    if code > 0x20000:
        return WEIGHTS["cjk"]
    return WEIGHTS["default"]


def weight(text):
    """Sum of character weights, after NFC normalization (as OmniVoice does)."""
    return sum(char_weight(c) for c in unicodedata.normalize("NFC", text))
