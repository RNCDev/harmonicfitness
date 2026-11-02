"""Where one web turn's time went: each model request's seconds, tokens and tool calls, what each draft write
added up to, and each build's guide spread, from a turn's history.json (web/local_turn.py's, or a `pull`'s), with
the two writers' calls from writers.json beside it when there is one.

    .venv/bin/python docs/eval/timing.py <folder holding history.json>
"""
import datetime
import json
import os
import re
import sys

ROW = re.compile(r"\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+(\d+)%")


def when(message):
    return datetime.datetime.fromisoformat(message["timestamp"].replace("Z", "+00:00"))


def calls(message):
    out = []
    for part in message.get("parts", []):
        kind = part.get("part_kind")
        if kind in ("tool-call", "builtin-tool-call"):
            args = part.get("args")
            args = args if isinstance(args, dict) else (json.loads(args) if isinstance(args, str) and args[:1] == "{" else {})
            name = part.get("tool_name")
            if name == "run":
                name += " " + " ".join((args.get("args") or [])[:2])
            elif name == "edit_segments":
                name += f" ({len(args.get('edits') or [])} edits)"
            out.append(name)
        elif kind == "text":
            out.append("text")
    return out


def returns(history, tools):
    for message in history:
        for part in message.get("parts", []):
            if part.get("part_kind") == "tool-return" and part.get("tool_name") in tools:
                content = part.get("content")
                yield (content.get("output", "") + content.get("error", "")) if isinstance(content, dict) else str(content)


def main():
    history = json.load(open(os.path.join(sys.argv[1], "history.json"), encoding="utf-8"))["history"]
    start = when(history[0])
    last = start
    for message in history:
        if message.get("kind") != "response":
            continue
        at = when(message)
        used = message.get("usage") or {}
        print(f"{(at - start).total_seconds():6.0f}s  +{(at - last).total_seconds():5.1f}s  "
              f"out={used.get('output_tokens', 0):6}  in={used.get('input_tokens', 0):6}  {', '.join(calls(message))}")
        last = at
    tracks = os.path.join(sys.argv[1], "writers.json")   # the two writers' calls (HARMONICFITNESS_WRITERS=two)
    for call in json.load(open(tracks, encoding="utf-8")) if os.path.exists(tracks) else []:
        if call.get("deadline"):
            print(f"WRITER {call['writer']} round {call['round']}: hit the deadline after {call['seconds']}s")
            continue
        print(f"WRITER {call['writer']} round {call['round']}: {call['seconds']}s, {call['requests']} requests, "
              f"out={call['output_tokens']} in={call['input_tokens']}, {call['searches']} searches")
    for out in returns(history, ("write_file", "edit_segments", "run", "write_script")):
        if out.startswith(("wrote ", "replaced ", "Two writers")):
            print("WRITE", out.splitlines()[0][:220])
        if "secs words guide" not in out:
            continue
        rows = [ROW.match(line) for line in out.splitlines()]
        fills = [int(m.group(6)) for m in rows if m]
        summary = [line for line in out.splitlines() if line.startswith(("Predicted", "To land"))]
        print(f"BUILD fills {min(fills)}% to {max(fills)}%, {sum(f > 120 for f in fills)} over 120%, "
              f"{sum(f < 80 for f in fills)} under 80% of {len(fills)}; " + " | ".join(s[:120] for s in summary))


if __name__ == "__main__":
    main()
