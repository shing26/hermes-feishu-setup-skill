"""
Hermes Feishu Gateway Guardian
Monitor profile gateways and auto-repair if stale or down.

Usage:
    python guardian.py                    # single default profile
    python guardian.py -p profile1 -p profile2
    python guardian.py --all              # all profiles under HERMES_HOME

Env:
    HERMES_HOME   default ~/.hermes
    GUARDIAN_INTERVAL   seconds between checks (default 60)
    GUARDIAN_STALE      seconds without inbound before restart (default 120)
    GUARDIAN_LOG        path to guardian log (default HERMES_HOME/logs/guardian.log)

Behavior:
    - Detects platform (Windows/Linux/macOS) for process listing.
    - For each profile: checks gateway process alive AND recent inbound activity.
    - Restarts dead or stale gateways.
    - Writes one line per check to guardian log; never raises on single-profile failure.
"""

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SYSTEM = platform.system()  # Windows | Linux | Darwin

ENV_DEFAULTS = {
    "HERMES_HOME": os.path.join(os.path.expanduser("~"), ".hermes"),
    "GUARDIAN_INTERVAL": "60",
    "GUARDIAN_STALE": "120",
    "GUARDIAN_LOG": "",  # computed at runtime
}

for k, v in ENV_DEFAULTS.items():
    if k not in os.environ:
        os.environ[k] = v

HERMES_HOME = Path(os.environ["HERMES_HOME"])
INTERVAL = int(os.environ["GUARDIAN_INTERVAL"])
STALE = int(os.environ["GUARDIAN_STALE"])
GUARDIAN_LOG = Path(os.environ["GUARDIAN_LOG"] or str(HERMES_HOME / "logs" / "guardian.log"))
GUARDIAN_LOG.parent.mkdir(parents=True, exist_ok=True)


def log(msg: str):
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    with open(GUARDIAN_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def profile_homes(requested: list[str] | None, include_all: bool) -> list[Path]:
    if include_all:
        return sorted([p for p in HERMES_HOME.glob("profiles/*") if p.is_dir()])
    if requested:
        return [HERMES_HOME / "profiles" / n for n in requested]
    return [HERMES_HOME]


def is_process_alive(name_fragment: str) -> bool:
    try:
        if SYSTEM == "Windows":
            out = subprocess.check_output(["tasklist", "/FO", "CSV", "/NH"], text=True, timeout=10)
            # tasklist CSV: "Image Name","PID","Session Name","Session#","Mem Usage"
            for line in out.splitlines():
                if name_fragment.lower() in line.lower():
                    return True
            return False
        else:
            out = subprocess.check_output(["pgrep", "-f", name_fragment], text=True, timeout=10)
            return bool(out.strip())
    except Exception as e:
        log(f"process-check error for '{name_fragment}': {e}")
        return False


def latest_inbound_ts(log_dir: Path) -> datetime | None:
    """Scan profile log dir for the most recent 'Received raw message' line."""
    pattern = re.compile(r"Received raw message")
    latest = None
    if not log_dir.exists():
        return None
    for fp in log_dir.glob("*.log"):
        try:
            mtime = datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc)
            if latest and mtime < latest:
                continue
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                # Scan from end for perf; keep last 200 lines
                lines = f.readlines()[-200:]
                for line in reversed(lines):
                    if pattern.search(line):
                        # Assume line begins with timestamp like 2026-08-17T10:30:00
                        ts_match = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", line)
                        if ts_match:
                            latest = datetime.fromisoformat(ts_match.group(1)).replace(tzinfo=timezone.utc)
                        break
        except Exception:
            continue
    return latest


def start_gateway(profile_home: Path) -> bool:
    try:
        cmd = [sys.executable, "-m", "hermes", "-p", profile_home.name, "gateway", "start"]
        env = {**os.environ, "HERMES_HOME": str(profile_home)}
        subprocess.Popen(cmd, env=env, close_fds=True)
        time.sleep(3)
        return is_process_alive("pythonw" if SYSTEM == "Windows" else "hermes")
    except Exception as e:
        log(f"restart failed for {profile_home.name}: {e}")
        return False


def check_profile(profile_home: Path):
    name = profile_home.name
    log_dir = profile_home / "logs"
    process_name = "pythonw.exe" if SYSTEM == "Windows" else "hermes"
    alive = is_process_alive(process_name)

    last_inbound = latest_inbound_ts(log_dir)
    now = datetime.now(timezone.utc)
    stale = False
    if last_inbound:
        age = (now - last_inbound).total_seconds()
        if age > STALE:
            stale = True

    if not alive or stale:
        reason = "down" if not alive else f"stale {int((now - last_inbound).total_seconds())}s"
        log(f"PROFILE {name}: {reason} -> restarting")
        ok = start_gateway(profile_home)
        log(f"PROFILE {name}: restart {'ok' if ok else 'FAILED'}")
    else:
        log(f"PROFILE {name}: ok")


def main():
    parser = argparse.ArgumentParser(description="Hermes Feishu Gateway Guardian")
    parser.add_argument("-p", "--profile", action="append", help="Profile name (repeatable)")
    parser.add_argument("--all", action="store_true", help="All profiles under HERMES_HOME")
    parser.add_argument("--once", action="store_true", help="Run one check and exit")
    args = parser.parse_args()

    homes = profile_homes(args.profile, args.all)
    if not homes:
        log("No profiles found; check HERMES_HOME and --profile/--all")
        sys.exit(1)

    if args.once:
        for h in homes:
            check_profile(h)
        return

    log(f"guardian start: profiles={[h.name for h in homes]} interval={INTERVAL}s stale={STALE}s")
    while True:
        try:
            for h in homes:
                check_profile(h)
        except KeyboardInterrupt:
            log("guardian stopped by user")
            break
        except Exception as e:
            log(f"guardian loop error: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
