#!/usr/bin/env python3
"""The movements allowed today, by group, for a kit and the tags to avoid.

The workout skill plans from this list instead of from memory: every movement printed fits the
equipment and breaks none of the banned tags. Read from the movement catalog
(knowledge/movements.toml).

    ./sweatcast movements --preset hotel-room --avoid impact
    ./sweatcast movements --equipment dumbbells,mat --group quads
"""
import os
import sys
from collections import Counter
from typing import Dict, List, Optional, Set

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import cli  # noqa: E402

OTHER = "other strength"


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


def tag_set(cat: catalog.Catalog, words: List[str]) -> Set[str]:
    for t in words:
        if t not in cat.tags:
            raise ValueError(f"unknown tag \"{t}\" (choose from: {', '.join(cat.tags)})")
    return set(words)


def line(cat: catalog.Catalog, m: catalog.Movement) -> str:
    where = m.position + (", one side at a time" if m.sided else "")
    text = f"  {m.name} ({where}): {m.setup} Cues: {' '.join(m.cues)}"
    for label, ids in (("Easier", m.easier), ("Harder", m.harder)):
        if ids:
            text += f" {label}: {', '.join(cat.movements[i].name if i in cat.movements else i for i in ids)}"
    return text


def sections(cat: catalog.Catalog, movements: List[catalog.Movement]) -> List[tuple]:
    """[(heading, [lines])]: strength movements by group (in full under the first, a pointer under
    the rest), then the other kinds."""
    out = []
    strength = [m for m in movements if m.kind == "strength"]
    first = {m.id: next((g for g in cat.groups if g in m.groups), None) for m in strength}
    for g in cat.groups:
        rows = [line(cat, m) if first[m.id] == g else f"  {m.name} (see {first[m.id]})"
                for m in strength if g in m.groups]
        out.append((g, rows))
    out.append((OTHER, [line(cat, m) for m in strength if first[m.id] is None]))
    for kind in cat.kinds:
        if kind != "strength":
            out.append((kind, [line(cat, m) for m in movements if m.kind == kind]))
    return out


def render(cat: catalog.Catalog, sel: catalog.Selection, only: Optional[str] = None) -> List[str]:
    out: List[str] = []
    blocks = sections(cat, sel.allowed)
    if sel.healthy_side_only:
        blocks += [("Healthy side only", [line(cat, m) for m in sel.healthy_side_only])]
    for heading, rows in blocks:
        if rows and (only is None or heading == only):
            out += [heading] + rows
    counts = Counter(r for reasons in sel.left_out.values() for r in reasons)
    why = ", ".join(f"{r}: {n}" for r, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
    out.append(f"Left out today: {len(sel.left_out)}" + (f" ({why})" if why else ""))
    return out


def main():
    ap = cli.ArgumentParser(prog="sweatcast movements")
    kit = ap.add_mutually_exclusive_group(required=True)
    kit.add_argument("--preset", help="a kit preset from the catalog, such as hotel-room")
    kit.add_argument("--equipment", help="comma-separated equipment, as keys or aliases")
    ap.add_argument("--avoid", default="", help="comma-separated tags to rule out")
    ap.add_argument("--group", help="print only this group or kind")
    args = ap.parse_args()

    cat = catalog.load()
    try:
        if args.preset:
            equipment = catalog.kit_equipment(cat, {"preset": args.preset})
        else:
            equipment = equipment_keys(cat, [w.strip() for w in args.equipment.split(",") if w.strip()])
        avoid = tag_set(cat, [t.strip() for t in args.avoid.split(",") if t.strip()])
        if args.group and args.group not in cat.groups + cat.kinds + [OTHER]:
            raise ValueError(f"unknown group \"{args.group}\" (choose from: {', '.join(cat.groups + cat.kinds)})")
    except ValueError as e:
        print(f"sweatcast movements: {e}", file=sys.stderr)
        return cli.USAGE
    print("\n".join(render(cat, catalog.select(cat, equipment, avoid), args.group)))
    return cli.OK


if __name__ == "__main__":
    sys.exit(main())
