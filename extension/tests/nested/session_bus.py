#!/usr/bin/env python3
"""Configuration of the nested session bus (nested.sh): the system's session.conf with its standard service
directories replaced by a private farm that holds every activatable service of the system EXCEPT the file indexer
(localsearch, formerly tracker-miners).

Why: the bench's private bus inherits the real HOME, so an indexer activated on it (Files activates
org.freedesktop.Tracker3.Miner.Files) crawls the user's real home folder during the pass. On this bus the indexer is
simply absent, as on a system without it: activation answers ServiceUnknown.

Usage: session_bus.py OUT_DIR  -> writes OUT_DIR/session.conf and OUT_DIR/services/, prints the config path.
The environment read is the one dbus-daemon would read (XDG_RUNTIME_DIR, XDG_DATA_HOME, XDG_DATA_DIRS)."""
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SYSTEM_CONF = Path("/usr/share/dbus-1/session.conf")
DOCTYPE = ('<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"\n'
           ' "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">\n')
# Programs of the file indexer and its helpers (localsearch 3.8+; tracker-miners 3.0-3.7 names).
INDEXER_PROGRAMS = ("localsearch", "tracker-miner", "tracker-extract", "tracker-writeback")


def standard_dirs(env):
    """The session service directories of dbus-daemon's <standard_session_servicedirs/>, highest priority first
    (dbus-daemon(1): XDG_RUNTIME_DIR/dbus-1/services, XDG_DATA_HOME, each XDG_DATA_DIRS entry, then the datadir), as
    (per-user directories, shared data directories)."""
    user = []
    if env.get("XDG_RUNTIME_DIR"):
        user.append(Path(env["XDG_RUNTIME_DIR"]) / "dbus-1" / "services")
    data_home = env.get("XDG_DATA_HOME") or str(Path(env["HOME"]) / ".local" / "share")
    user.append(Path(data_home) / "dbus-1" / "services")
    shared = [Path(d) / "dbus-1" / "services"
              for d in (env.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":") if d]
    shared.append(Path("/usr/share/dbus-1/services"))
    unique = []
    for d in shared:
        if d not in unique and d not in user:
            unique.append(d)
    return user, unique


def service_entry(path):
    """(Name, Exec program basename) of a .service file, or None if it has no Name."""
    name = program = None
    in_section = False
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if line.startswith("["):
            in_section = line == "[D-BUS Service]"
        elif in_section and line.startswith("Name="):
            name = line[5:].strip()
        elif in_section and line.startswith("Exec="):
            words = line[5:].split()
            program = os.path.basename(words[0]) if words else ""
    return (name, program or "") if name else None


def is_indexer(program):
    return program.startswith(INDEXER_PROGRAMS)


def build_farm(dirs, farm):
    """Symlinks in farm to the first .service of each bus name along dirs (priority order, as dbus-daemon resolves
    them), indexer services left out. Returns (kept names, left-out names)."""
    farm.mkdir(parents=True, exist_ok=True)
    kept, left_out = {}, set()
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.service")):
            entry = service_entry(f)
            if entry is None:
                continue
            name, program = entry
            if name in kept or name in left_out:
                continue
            if is_indexer(program):
                left_out.add(name)
                continue
            kept[name] = f
            (farm / f"{name}.service").symlink_to(f.resolve())
    return sorted(kept), sorted(left_out)


def write_config(system_conf, out_conf, service_dirs):
    """system_conf with <standard_session_servicedirs/> replaced by service_dirs (priority order) and relative
    include/includedir paths made absolute (they are relative to the config file's own folder)."""
    tree = ET.parse(system_conf)
    root = tree.getroot()
    standard = root.findall("standard_session_servicedirs")
    if len(standard) != 1:
        raise ValueError(f"{system_conf}: expected one <standard_session_servicedirs/>, found {len(standard)}")
    index = list(root).index(standard[0])
    root.remove(standard[0])
    for offset, d in enumerate(service_dirs):
        el = ET.Element("servicedir")
        el.text = str(d)
        el.tail = standard[0].tail
        root.insert(index + offset, el)
    for el in root.iter():
        if el.tag in ("include", "includedir") and el.text and not os.path.isabs(el.text.strip()):
            el.text = str(system_conf.parent / el.text.strip())
    out_conf.write_text('<?xml version="1.0"?>\n' + DOCTYPE + ET.tostring(root, encoding="unicode") + "\n")


def prepare(out_dir, env, system_conf=SYSTEM_CONF):
    """Writes out_dir/session.conf and out_dir/services. The per-user directories (private runtime and data home under
    nested.sh) stay first, unfiltered; the shared data directories are replaced by the filtered farm."""
    out_dir = Path(out_dir)
    user, shared = standard_dirs(env)
    farm = out_dir / "services"
    build_farm(shared, farm)
    conf = out_dir / "session.conf"
    write_config(Path(system_conf), conf, [*user, farm])
    return conf


def main(argv):
    if len(argv) != 2:
        print("usage: session_bus.py OUT_DIR", file=sys.stderr)
        return 2
    print(prepare(argv[1], os.environ))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
