#!/usr/bin/env python3
"""The movements allowed today for a kit. Rewritten in the session-builder plan; for now only
`equipment_keys` is kept, because the next version reuses it."""
import os
import sys
from typing import Dict, List, Set

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import cli  # noqa: E402


def equipment_keys(cat: catalog.Catalog, words: List[str]) -> Set[str]:
    """Equipment keys for names given as keys or as a catalog alias; ValueError on an unknown one."""
    by_word: Dict[str, str] = {}
    for key, info in cat.equipment.items():
        by_word[key.lower()] = key
        for alias in info.get("aliases", []):
            by_word.setdefault(alias.lower(), key)
    out: Set[str] = set()
    for word in words:
        key = by_word.get(" ".join(word.lower().split()))
        if key is None:
            raise ValueError(f"unknown equipment \"{word}\" (choose from: {', '.join(cat.equipment)})")
        out.add(key)
    return out


def main():
    print("movements: rewritten in the next task", file=sys.stderr)
    return cli.USAGE


if __name__ == "__main__":
    sys.exit(main())
