#!/usr/bin/env python3
"""
first_boot.py: the newborn's first-boot step. In this template every birth is a
7-day MiniMax-M3 trial, and this is what makes it one, with no extra fleet step.

It runs automatically, before any model call, from every path that starts the AiCIV:

  tools/restart-self.sh          (the fleet's launch/restart path)
  tools/launch_civ_tower.sh      tools/launch_primary_visible.sh      tools/model_boot.sh
  .claude/hooks/trial_gate.py    (SessionStart and every prompt, as the safety net for
                                  any other launcher)

What it does (idempotent; a lock serializes concurrent callers):

  * trial already applied   -> nothing to write; `--verify` re-runs the no-frontier check
  * trial converted to paid -> nothing (conversion is final)
  * first boot, seams given -> tools/apply_trial_profile.py apply with TRIAL_START = now:
                               config/trial.json (7 days from now, payment link from
                               config/partner.json), M3 on every surface, the full VP org,
                               the trial hook and grounding. Ends with the check.
  * first boot, seams MISSING -> refuses loudly: a banner on stderr, config/birth_status.json
                               {"status": "blocked", "missing": [...]}, exit 2. Nothing falls
                               back to another model: the tree ships with ANTHROPIC_BASE_URL on a
                               closed local port, and the trial hook blocks every prompt with the
                               same message, so the human sees why their AiCIV is not answering.

SEAMS (provisioning fills them; never committed). Read from the process environment first,
then from the operator seam file $M3_SEAMS_FILE (default /etc/aiciv/m3-router.env, KEY=VALUE lines):

  M3_ROUTER_BASE_URL    REQUIRED  Anthropic-wire base URL of this tenant's M3 router
  M3_ROUTER_KEY_FILE    REQUIRED  path to this tenant's router key (or M3_ROUTER_KEY=<value>)
  TRIAL_OPERATOR_COPY   production: /etc/aiciv/trial.json (outside the tree; the portal's
                        TRIAL_CONFIG_PATH points at it). Must be writable by whoever runs first boot.
  M3_MODEL_ID           optional, default MiniMax-M3
  TRIAL_PAYMENT_URL     optional, default payment_url from config/partner.json
  TRIAL_START           optional ISO8601 UTC, default now (first boot)

    python3 tools/first_boot.py [--root DIR] [--via NAME] [--session-id ID] [--verify] [--quiet]
    python3 tools/first_boot.py status        # prints config/birth_status.json

Exit: 0 born (or already born / converted), 2 blocked (seams missing), 1 apply/check failed.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import trial_state  # noqa: E402

SEAM_KEYS = ("M3_ROUTER_BASE_URL", "M3_ROUTER_KEY_FILE", "M3_ROUTER_KEY", "M3_MODEL_ID",
             "TRIAL_PAYMENT_URL", "TRIAL_START", "TRIAL_OPERATOR_COPY")
DEFAULT_SEAMS_FILE = "/etc/aiciv/m3-router.env"
STATUS_FILE = "config/birth_status.json"
LOG_FILE = "logs/first_boot.log"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def status_path(root: Path) -> Path:
    return root / STATUS_FILE


def read_status(root: Path) -> dict:
    try:
        d = json.loads(status_path(root).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def write_status(root: Path, rec: dict) -> None:
    trial_state._atomic_write_json(status_path(root), rec)


def log_line(root: Path, text: str) -> None:
    try:
        p = root / LOG_FILE
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as fh:
            fh.write(f"{now_iso()} {text}\n")
    except OSError:
        pass


def parse_seams_file(path: Path) -> dict:
    out: dict[str, str] = {}
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip().removeprefix("export ").strip()
        v = v.strip().strip('"').strip("'")
        if k in SEAM_KEYS and v:
            out[k] = v
    return out


def gather_seams() -> tuple[dict, str]:
    """Seams from the environment, then the operator seam file. Returns (env additions, source note)."""
    seams_file = Path(os.environ.get("M3_SEAMS_FILE") or DEFAULT_SEAMS_FILE)
    from_file = parse_seams_file(seams_file)
    env = {}
    used_file = False
    for k in SEAM_KEYS:
        v = os.environ.get(k, "").strip()
        if not v and from_file.get(k):
            v, used_file = from_file[k], True
        if v:
            env[k] = v
    return env, (f"environment + {seams_file}" if used_file else "environment")


def missing_seams(root: Path, env: dict) -> list[str]:
    miss = []
    if not env.get("M3_ROUTER_BASE_URL"):
        miss.append("M3_ROUTER_BASE_URL")
    kf = env.get("M3_ROUTER_KEY_FILE", "")
    if not env.get("M3_ROUTER_KEY") and not (kf and Path(kf).is_file()):
        miss.append("M3_ROUTER_KEY_FILE (or M3_ROUTER_KEY)" if not kf
                    else f"M3_ROUTER_KEY_FILE (no readable file at {kf})")
    pay = env.get("TRIAL_PAYMENT_URL") or trial_state.partner(root).get("payment_url", "")
    if not str(pay).startswith("https://"):
        miss.append("payment link (config/partner.json payment_url, or TRIAL_PAYMENT_URL)")
    op = env.get("TRIAL_OPERATOR_COPY", "")
    if op and not writable_target(Path(op)):
        # Checked BEFORE apply: a clock written without its operator copy would fail closed on day 1.
        miss.append(f"TRIAL_OPERATOR_COPY {op} is not writable by uid {os.geteuid()} "
                    "(run first boot as root once, or pre-create it for this user)")
    return miss


def writable_target(dest: Path) -> bool:
    d = dest.expanduser()
    if d.exists():
        return os.access(d, os.W_OK) and os.access(d.parent, os.W_OK)
    parent = d.parent
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    return os.access(parent, os.W_OK | os.X_OK)


def blocked_banner(root: Path, missing: list[str]) -> str:
    brand = trial_state.partner(root).get("brand") or trial_state.DEFAULT_BRAND
    return (
        f"THIS AiCIV CANNOT START YET. It is a {brand} 7-day trial that runs ONLY on MiniMax-M3, and "
        f"its M3 router was not provided at birth (missing: {', '.join(missing)}). It will not fall back "
        "to any other model, so it cannot think or reply until this is fixed. "
        "OPERATOR: put the seams in the container environment or in /etc/aiciv/m3-router.env "
        "(M3_ROUTER_BASE_URL, M3_ROUTER_KEY_FILE or M3_ROUTER_KEY), then run "
        "`python3 tools/first_boot.py` and restart the session (tools/restart-self.sh). "
        "The 7-day clock has NOT started; it starts at the first boot that has the router."
    )


class Lock:
    def __init__(self, root: Path):
        self.path = root / "config/.first_boot.lock"
        self.fh = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = self.path.open("a")
        fcntl.flock(self.fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.fh, fcntl.LOCK_UN)
        self.fh.close()


def give_back_to_tree_owner(root: Path) -> None:
    """First boot run as root (so the operator copy outside the tree is root-owned): every file it created
    or replaced INSIDE the tree goes back to the tree's owner, so the AiCIV can still edit its own
    constitution (the self-removing gates) and the launchers keep working as that user."""
    st = root.stat()
    if st.st_uid == 0:
        return
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for name in [*dirnames, *filenames]:
            p = os.path.join(dirpath, name)
            try:
                if os.lstat(p).st_uid == 0:
                    os.lchown(p, st.st_uid, st.st_gid)
            except OSError:
                continue


def run_check(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(root / "tools/apply_trial_profile.py"), "check", "--root", str(root)],
                          capture_output=True, text=True)


def first_boot(root: Path, via: str, session_id: str = "", verify: bool = False, quiet: bool = False) -> int:
    say = (lambda m: None) if quiet else (lambda m: print(f"[first-boot] {m}"))
    with Lock(root):
        rec_path, _ = trial_state.record_path(root)
        has_record = trial_state.trial_path(root).exists() or rec_path.exists()
        if has_record or not trial_state.birth_pending(root):
            civ = trial_state.load(root)
            if civ is None and trial_state.trial_path(root).exists():
                say("trial converted (config/trial.json \"trial\": false); nothing to do")
                return 0
            if not has_record and not trial_state.birth_applied(root):
                say("not a trial-by-default tree (no pending first boot); nothing to do")
                return 0
            if verify:
                r = run_check(root)
                say(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "check produced no output")
                return 0 if r.returncode == 0 else 1
            say("already born: trial profile applied; nothing to do")
            return 0

        env, source = gather_seams()
        miss = missing_seams(root, env)
        if miss:
            banner = blocked_banner(root, miss)
            write_status(root, {"status": "blocked", "missing": miss, "checked_at": now_iso(), "via": via,
                                "message": banner})
            log_line(root, f"BLOCKED via={via} missing={miss}")
            bar = "=" * 78
            print(f"\n{bar}\n[first-boot] {banner}\n{bar}\n", file=sys.stderr)
            return 2

        start = env.get("TRIAL_START") or now_iso()
        child_env = {**os.environ, **env, "TRIAL_START": start, "CIV_ROOT": str(root)}
        cmd = [sys.executable, str(root / "tools/apply_trial_profile.py"), "apply", "--root", str(root)]
        r = subprocess.run(cmd, capture_output=True, text=True, env=child_env)
        log_line(root, f"apply via={via} rc={r.returncode}\n{r.stdout}{r.stderr}")
        if r.returncode != 0:
            write_status(root, {"status": "failed", "checked_at": now_iso(), "via": via,
                                "message": (r.stderr or r.stdout).strip()[-2000:]})
            print(f"[first-boot] FAILED to apply the trial profile (exit {r.returncode}); "
                  f"see {LOG_FILE}\n{(r.stderr or r.stdout).strip()[-2000:]}", file=sys.stderr)
            return 1
        trial = json.loads(trial_state.trial_path(root).read_text())
        status = {"status": "trial-active", "born_at": now_iso(), "via": via, "seams_from": source,
                  "started_at": trial["started_at"], "expires_at": trial["expires_at"],
                  "payment_url": trial["payment_url"], "model": trial["model"],
                  "trial_record": str(trial_state.record_path(root)[0])}
        if session_id:
            # Provisioned from inside a running Claude session (the hook path): that session read its
            # settings before the router existed, so the gate asks for one restart (see trial_gate.py).
            status["provisioned_in_session"] = session_id
        write_status(root, status)
        say(f"born as a 7-day {trial.get('brand')} trial on {trial['model']}: "
            f"started_at={trial['started_at']} expires_at={trial['expires_at']}")
        say(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "")
        return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="first boot: every birth is a 7-day MiniMax-M3 trial")
    ap.add_argument("cmd", nargs="?", default="run", choices=["run", "status"])
    ap.add_argument("--root", default=None)
    ap.add_argument("--via", default="manual", help="which launcher called (recorded in birth_status.json)")
    ap.add_argument("--session-id", default="")
    ap.add_argument("--verify", action="store_true", help="on an already-born civ, re-run the check")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    root = trial_state.civ_root(a.root).resolve()
    if a.cmd == "status":
        print(json.dumps(read_status(root) or {"status": "unknown"}, indent=2))
        return 0
    try:
        return first_boot(root, a.via, a.session_id, a.verify, a.quiet)
    finally:
        if os.geteuid() == 0:
            give_back_to_tree_owner(root)


if __name__ == "__main__":
    sys.exit(main())
