#!/usr/bin/env python3
"""The movements a kit allows, by movement pattern, for browsing the catalog.

This filter applies no health limits: every movement printed fits the equipment and level and
breaks none of the movements or flags to avoid, but the limits in the health file are not checked.
It is for browsing (such as finding a movement's name for likes and dislikes); a session's plan,
warm-up and cool-down included, comes from `./sweatcast session`, which applies the limits. Read
from the movement catalog (knowledge/movements.toml).

    ./sweatcast movements --preset hotel-room --avoid impact
    ./sweatcast movements --equipment dumbbells,mat --pattern squat --level novice
"""
import os
import sys
from collections import Counter
from typing import Dict, List, Optional, Set

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


def line(cat: catalog.Catalog, m: catalog.Movement) -> str:
    where = m.position + (", one side at a time" if m.sided else "")
    text = f"  {m.name} ({where}): {m.setup} Cues: {' '.join(m.cues)}"
    for label, ids in (("Easier", m.easier), ("Harder", m.harder)):
        if ids:
            text += f" {label}: {', '.join(cat.movements[i].name if i in cat.movements else i for i in ids)}"
    return text


def render(cat: catalog.Catalog, sel: catalog.Selection, only: Optional[str] = None) -> List[str]:
    """Allowed movements under their primary pattern in the catalog's order, then "Healthy side only",
    then the "Left out today" line. `only` limits the output to one pattern."""
    out: List[str] = []
    blocks = [(p, [line(cat, m) for m in sel.allowed if m.patterns[0] == p]) for p in cat.patterns]
    blocks.append(("Healthy side only", [line(cat, m) for m in sel.healthy_side_only
                                          if only is None or m.patterns[0] == only]))
    for heading, rows in blocks:
        if rows and (only is None or heading == only or heading == "Healthy side only"):
            out += [heading] + rows
    counts = Counter(r for reasons in sel.left_out.values() for r in reasons)
    why = ", ".join(f"{r}: {n}" for r, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
    out.append(f"Left out today: {len(sel.left_out)}" + (f" ({why})" if why else ""))
    return out


def avoid_set(cat: catalog.Catalog, words: List[str]) -> Set[str]:
    """Movement ids or flags to rule out; ValueError on an unknown one."""
    for w in words:
        if w not in cat.movements and w not in cat.flags:
            raise ValueError(f"unknown movement or flag \"{w}\" (flags: {', '.join(cat.flags)})")
    return set(words)


def main():
    ap = cli.ArgumentParser(prog="sweatcast movements", description=(
        "Browse the movements a kit allows, by pattern. This filter applies no health limits; "
        "plan sessions with ./sweatcast session, which does."))
    kit = ap.add_mutually_exclusive_group(required=True)
    kit.add_argument("--preset", help="a kit preset from the catalog, such as hotel-room")
    kit.add_argument("--equipment", help="comma-separated equipment, as keys or aliases")
    ap.add_argument("--avoid", default="", help="comma-separated movement ids or flags to rule out")
    ap.add_argument("--level", default="experienced", help="novice, experienced or advanced (default experienced)")
    ap.add_argument("--pattern", help="print only this movement pattern")
    args = ap.parse_args()

    cat = catalog.load()
    try:
        if args.preset:
            equipment = catalog.kit_equipment(cat, {"preset": args.preset})
        else:
            equipment = equipment_keys(cat, [w.strip() for w in args.equipment.split(",") if w.strip()])
        avoid = avoid_set(cat, [w.strip() for w in args.avoid.split(",") if w.strip()])
        if args.level not in catalog.LEVELS:
            raise ValueError(f"unknown level \"{args.level}\" (choose from: {', '.join(catalog.LEVELS)})")
        if args.pattern and args.pattern not in cat.patterns:
            raise ValueError(f"unknown pattern \"{args.pattern}\" (choose from: {', '.join(cat.patterns)})")
    except ValueError as e:
        print(f"sweatcast movements: {e}", file=sys.stderr)
        return cli.USAGE
    print("\n".join(render(cat, catalog.select(cat, equipment, args.level, [], avoid=avoid), args.pattern)))
    return cli.OK


if __name__ == "__main__":
    sys.exit(main())
