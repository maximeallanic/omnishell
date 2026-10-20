#!/usr/bin/env python3
"""Edit org.gnome.shell enabled-extensions through gsettings.

Usage: enabled_extensions.py add|remove|list UUID...
Prints the UUIDs that were actually added/removed (one per line), so the caller can record what it changed and undo
exactly that. The key is edited directly, not through `gnome-extensions enable`, because the running Shell does not know
an extension that was just copied until the next login."""
import ast
import subprocess
import sys

SCHEMA, KEY = "org.gnome.shell", "enabled-extensions"


def read():
    out = subprocess.run(["gsettings", "get", SCHEMA, KEY], check=True, capture_output=True, text=True).stdout
    return list(ast.literal_eval(out.strip().removeprefix("@as ")))


def write(values):
    subprocess.run(["gsettings", "set", SCHEMA, KEY, str(values)], check=True)


def main(argv):
    if len(argv) < 2 or argv[1] not in ("add", "remove", "list"):
        print(__doc__, file=sys.stderr)
        return 2
    action, uuids = argv[1], argv[2:]
    current = read()
    if action == "list":
        print("\n".join(current))
        return 0
    if action == "add":
        changed = [u for u in dict.fromkeys(uuids) if u not in current]
        new = current + changed
    else:
        changed = [u for u in dict.fromkeys(uuids) if u in current]
        new = [u for u in current if u not in changed]
    if changed:
        write(new)
    print("\n".join(changed))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
