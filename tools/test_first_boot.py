#!/usr/bin/env python3
"""
test_first_boot.py: every birth of this template is a 7-day MiniMax-M3 trial.

Copies the tree (as it ships: unborn, M3-only, locked) into a temp dir and proves, with
placeholder seams (reserved .invalid host, dummy key; nothing is contacted):

  1. the unborn tree reaches no frontier model (static check + independent greps)
  2. no seams: first boot refuses loudly, starts no clock, and the hook tells the human
     (SessionStart system message, every prompt blocked, every tool denied)
  3. seams in the environment: first boot writes config/trial.json (7 days from first boot,
     payment link from config/partner.json), the full check passes, re-runs keep the clock
  4. seams in the operator seam file (/etc/aiciv/m3-router.env shape) work the same way
  5. the launchers run first boot before Claude (model_boot.sh with a stand-in `claude`)
  6. first boot from inside a running session: one-restart notice for THAT session only
  7. a born civ whose trial record disappears fails CLOSED
  8. agent manifests cannot be given a frontier pin
  9. conversion: ungated immediately; --restore-models returns the paid config; first boot
     after conversion is a no-op

    python3 tools/test_first_boot.py        # exit 0 = all pass
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
FAILS: list[str] = []
PASSES = 0
FRONTIER = re.compile(r"claude-(opus|sonnet|haiku|instant)|claude-\d[\d.-]*-(opus|sonnet|haiku)", re.I)


def ok(cond: bool, label: str) -> None:
    global PASSES
    if cond:
        PASSES += 1
        print(f"  PASS  {label}")
    else:
        FAILS.append(label)
        print(f"  FAIL  {label}")


def run(cmd, cwd, env=None, stdin=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith(("M3_", "TRIAL_"))}
    e["M3_SEAMS_FILE"] = "/nonexistent/m3-router.env"
    e.update(env or {})
    return subprocess.run(cmd, cwd=cwd, env=e, input=stdin, capture_output=True, text=True)


def gate(root: Path, event: dict, env=None) -> str:
    r = run([sys.executable, ".claude/hooks/trial_gate.py"], root,
            {"CLAUDE_PROJECT_DIR": str(root), **(env or {})}, json.dumps(event))
    return r.stdout.strip()


def fresh(dst: Path) -> Path:
    shutil.copytree(SRC, dst, ignore=shutil.ignore_patterns(".git", "__pycache__"), symlinks=True)
    for p in ("config/trial.json", "config/birth_status.json", "config/.first_boot.lock"):
        (dst / p).unlink(missing_ok=True)
    return dst


def first_boot(root: Path, env=None):
    return run([sys.executable, "tools/first_boot.py", "--root", str(root), "--via", "test"], root, env)


def parse(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="firstboot-"))
    try:
        key = tmp / "key.txt"
        key.write_text("rk_TEST_dummy_not_a_key\n")
        seams = {"M3_ROUTER_BASE_URL": "https://m3-router.invalid/anthropic", "M3_ROUTER_KEY_FILE": str(key)}
        partner = json.loads((SRC / "config/partner.json").read_text())

        print("[1] the unborn tree reaches no frontier model")
        unborn = fresh(tmp / "unborn")
        r = run([sys.executable, "tools/apply_trial_profile.py", "check", "--static", "--root", str(unborn)], unborn)
        ok(r.returncode == 0 and "static check:" in r.stdout and "NO FRONTIER MODEL REACHABLE" in r.stdout,
           "check --static passes on the unborn tree")
        s = json.loads((unborn / ".claude/settings.json").read_text())
        ok(not FRONTIER.search(json.dumps(s)), "independent grep: shipped settings.json has no frontier id")
        ok(s["model"] == "MiniMax-M3" and all(s["env"][k] == "MiniMax-M3" for k in (
            "ANTHROPIC_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL",
            "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_SMALL_FAST_MODEL")),
           "shipped settings: model + all 6 model env keys = MiniMax-M3")
        ok(s["env"]["ANTHROPIC_BASE_URL"].startswith("http://127.0.0.1:9/"),
           "shipped base URL is a closed local port (nothing reachable before first boot)")
        pins = [f.name for f in (unborn / ".claude/agents").glob("*.md")
                if re.search(r"^model:[ \t]*(?!inherit[ \t]*$)\S.*$", f.read_text().split("\n---", 1)[0], re.M)]
        ok(not pins, f"independent grep: every agent manifest is `model: inherit` ({len(pins)} not)")
        ok((unborn / "config/launch_model.txt").read_text().strip() == "MiniMax-M3", "launch model = MiniMax-M3")
        wf = [p.name for p in (unborn / "workflows").glob("*.js") if FRONTIER.search(p.read_text())]
        ok(not wf, f"no workflow names a frontier model ({wf})")
        r = run(["bash", "tools/model_switch.sh", "default"], unborn, {"CIV_ROOT": str(unborn)})
        ok(r.returncode == 3, "model_switch.sh default refused on the unborn tree (locked)")
        r = run([sys.executable, "tools/apply_trial_profile.py", "check", "--root", str(unborn)], unborn)
        ok(r.returncode == 1 and "first boot has not run" in r.stdout, "full check says first boot has not run")

        print("[2] no seams: loud refusal, no clock, the human is told")
        r = first_boot(unborn)
        st = json.loads((unborn / "config/birth_status.json").read_text())
        ok(r.returncode == 2 and "CANNOT START YET" in r.stderr and "M3_ROUTER_BASE_URL" in r.stderr,
           "first_boot exits 2 with a banner naming the missing seams")
        ok(not (unborn / "config/trial.json").exists(), "no trial clock started")
        ok(st["status"] == "blocked" and "M3_ROUTER_BASE_URL" in st["missing"], "birth_status.json = blocked")
        out = json.loads(gate(unborn, {"hook_event_name": "SessionStart", "session_id": "a"}))
        ok("CANNOT START YET" in out.get("systemMessage", ""), "SessionStart: system message to the human")
        out = json.loads(gate(unborn, {"hook_event_name": "UserPromptSubmit", "session_id": "a", "prompt": "hi"}))
        ok(out.get("decision") == "block" and "will not fall back" in out.get("reason", ""),
           "every prompt blocked (no model call) with the reason")
        out = json.loads(gate(unborn, {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                                       "tool_input": {"command": "ls"}}))
        ok(out["hookSpecificOutput"]["permissionDecision"] == "deny", "every tool denied")
        partial = first_boot(unborn, {"M3_ROUTER_BASE_URL": seams["M3_ROUTER_BASE_URL"]})
        ok(partial.returncode == 2 and "M3_ROUTER_KEY_FILE" in partial.stderr
           and not (unborn / "config/trial.json").exists(), "URL without a key still refuses")
        missing_key = first_boot(unborn, {**seams, "M3_ROUTER_KEY_FILE": str(tmp / "nope")})
        ok(missing_key.returncode == 2 and "no readable file" in missing_key.stderr, "unreadable key file refuses")

        print("[3] seams in the environment: born as a 7-day trial at first boot")
        civ = fresh(tmp / "civ")
        before = datetime.now(timezone.utc).replace(microsecond=0)
        r = first_boot(civ, seams)
        after = datetime.now(timezone.utc)
        rec = json.loads((civ / "config/trial.json").read_text())
        started, expires = parse(rec["started_at"]), parse(rec["expires_at"])
        ok(r.returncode == 0 and "born as a 7-day" in r.stdout, "first_boot exits 0")
        ok(before <= started <= after, "started_at = first boot")
        ok(expires - started == timedelta(days=7) and rec["duration_days"] == 7, "expires_at = started_at + 7 days")
        ok(rec["payment_url"] == partner["payment_url"] and rec["brand"] == partner["brand"]
           and rec["model"] == "MiniMax-M3", "payment link + brand from config/partner.json, model MiniMax-M3")
        r = run([sys.executable, "tools/apply_trial_profile.py", "check", "--root", str(civ)], civ)
        ok(r.returncode == 0 and "NO FRONTIER MODEL REACHABLE" in r.stdout, "full check passes on the born civ")
        s = json.loads((civ / ".claude/settings.json").read_text())
        ok(s["env"]["ANTHROPIC_BASE_URL"] == seams["M3_ROUTER_BASE_URL"] and s.get("apiKeyHelper"),
           "settings route to the router with the key helper")
        n_gate = sum(1 for ev in ("SessionStart", "UserPromptSubmit", "PreToolUse")
                     for g in s["hooks"][ev] for h in g["hooks"] if "trial_gate" in h["command"])
        ok(n_gate == 3, "trial hook registered once per event (not duplicated by apply)")
        ok("BEGIN trial-m3" in (civ / ".claude/CLAUDE.md").read_text(), "trial grounding block installed")
        n_leads = len(list((civ / ".claude/team-leads").glob("*/manifest.md")))
        n_agents = len(list((civ / ".claude/agents").glob("*.md")))
        ok(n_leads == len(list((SRC / ".claude/team-leads").glob("*/manifest.md"))) and n_agents > 100,
           f"full VP org kept ({n_leads} VP manifests, {n_agents} agent manifests)")
        st = json.loads((civ / "config/birth_status.json").read_text())
        ok(st["status"] == "trial-active" and st["expires_at"] == rec["expires_at"], "birth_status.json = trial-active")
        r2 = first_boot(civ, {**seams, "TRIAL_START": "2030-01-01T00:00:00Z"})
        ok(r2.returncode == 0 and "already born" in r2.stdout
           and json.loads((civ / "config/trial.json").read_text()) == rec, "re-run is a no-op; clock kept")
        r3 = run([sys.executable, "tools/first_boot.py", "--root", str(civ), "--verify"], civ)
        ok(r3.returncode == 0 and "NO FRONTIER MODEL REACHABLE" in r3.stdout, "--verify re-runs the check")

        print("[3b] a stale 'failed' birth_status is re-verified (ticket 3350)")
        st_path = civ / "config/birth_status.json"
        trial_before = (civ / "config/trial.json").read_text()
        born = json.loads(st_path.read_text())
        # the record quotes the old failure, including a frontier model assignment, exactly as a real one does
        stale = {"status": "failed", "checked_at": "2026-09-27T20:00:00Z", "via": "restart-self.sh",
                 "message": "FAIL  tools/launch_civ_tower.sh hard-pins a frontier model: claude --model claude-opus-4-8"
                            "\nFAIL  config/x.sh:2: ANTHROPIC_MODEL=claude-opus-4-8"}
        st_path.write_text(json.dumps(stale, indent=2))
        assign = re.compile(r"(--model[= ]+['\"]?claude|(ANTHROPIC_MODEL|CLAUDE_CODE_SUBAGENT_MODEL)=['\"]?claude)", re.I)
        ok(bool(assign.search(st_path.read_text())), "(the stale record really does match the scan's assignment patterns)")
        (civ / "logs").mkdir(exist_ok=True)
        (civ / "logs/old-check.json").write_text('{"model": "claude-opus-4-8"}\n')
        r = run([sys.executable, "tools/apply_trial_profile.py", "check", "--root", str(civ)], civ)
        ok(r.returncode == 0 and "birth_status" not in r.stdout and "logs/" not in r.stdout,
           "tree scan ignores config/birth_status.json and logs/ (they quote past findings)")
        rogue = civ / "tools/rogue_router.py"
        rogue.write_text('model = "claude-opus-4-8"\n')
        r = run([sys.executable, "tools/first_boot.py", "--root", str(civ), "--verify"], civ)
        ok(r.returncode == 1 and "tools/rogue_router.py" in run(
            [sys.executable, "tools/apply_trial_profile.py", "check", "--root", str(civ)], civ).stdout
           and json.loads(st_path.read_text())["status"] == "failed",
           "a real routing file is still flagged, and a failing --verify leaves the record alone")
        rogue.unlink()
        r = run([sys.executable, "tools/first_boot.py", "--root", str(civ), "--verify"], civ)
        st = json.loads(st_path.read_text())
        ok(r.returncode == 0 and "failed -> trial-active" in r.stdout, "--verify passes and says failed -> trial-active")
        ok(st.get("status") == "trial-active" and st.get("previous_status") == "failed"
           and st.get("previous_checked_at") == "2026-09-27T20:00:00Z" and st.get("reverified_at")
           and "message" not in st, "birth_status.json = trial-active, previous_status + reverified_at kept")
        ok(st.get("started_at") == rec["started_at"] and st.get("expires_at") == rec["expires_at"]
           and (civ / "config/trial.json").read_text() == trial_before, "the clock is read, never restarted")
        st_path.write_text(json.dumps({**born, "provisioned_in_session": "sess-1"}))
        r = run([sys.executable, "tools/first_boot.py", "--root", str(civ), "--verify"], civ)
        st = json.loads(st_path.read_text())
        ok(r.returncode == 0 and st.get("born_at") == born["born_at"] and st.get("provisioned_in_session") == "sess-1"
           and st.get("reverified_at") and "previous_status" not in st,
           "an already trial-active record keeps its fields (born_at, provisioned_in_session) + reverified_at")
        (civ / "logs/old-check.json").unlink()
        ctx = gate(civ, {"hook_event_name": "UserPromptSubmit", "session_id": "b", "prompt": "hi"})
        ok("Day 1 of 7" in ctx, "the AiCIV sees Day 1 of 7")

        print("[4] seams from the operator seam file")
        sf = tmp / "m3-router.env"
        sf.write_text(f"# operator seam file\nexport M3_ROUTER_BASE_URL=\"{seams['M3_ROUTER_BASE_URL']}\"\n"
                      f"M3_ROUTER_KEY_FILE={key}\n")
        civ4 = fresh(tmp / "civ4")
        r = first_boot(civ4, {"M3_SEAMS_FILE": str(sf)})
        st = json.loads((civ4 / "config/birth_status.json").read_text())
        ok(r.returncode == 0 and (civ4 / "config/trial.json").exists() and str(sf) in st["seams_from"],
           "seam file alone is enough")

        print("[4b] the operator copy (portal's TRIAL_CONFIG_PATH) at first boot")
        civ4b = fresh(tmp / "civ4b")
        r = first_boot(civ4b, {**seams, "TRIAL_OPERATOR_COPY": "/proc/aiciv-not-writable/trial.json"})
        ok(r.returncode == 2 and "not writable" in r.stderr and not (civ4b / "config/trial.json").exists(),
           "unwritable operator copy refuses BEFORE any clock is written")
        opc = tmp / "etc-aiciv" / "trial.json"
        r = first_boot(civ4b, {**seams, "TRIAL_OPERATOR_COPY": str(opc)})
        chk = run([sys.executable, "tools/apply_trial_profile.py", "check", "--root", str(civ4b)], civ4b)
        ok(r.returncode == 0 and opc.exists()
           and json.loads(opc.read_text()) == json.loads((civ4b / "config/trial.json").read_text())
           and chk.returncode == 0 and "read from the operator copy" in chk.stdout,
           "operator copy published at first boot; check reads it")

        print("[5] launchers run first boot before Claude")
        civ5 = fresh(tmp / "civ5")
        fake = tmp / "bin"
        fake.mkdir()
        (fake / "claude").write_text("#!/bin/bash\necho \"FAKE-CLAUDE model=$ANTHROPIC_MODEL base=$ANTHROPIC_BASE_URL"
                                     " trial=$(test -f config/trial.json && echo yes)\"\n")
        (fake / "claude").chmod(0o755)
        r = run(["bash", "tools/model_boot.sh", "-p", "hi"], civ5,
                {**seams, "PATH": f"{fake}:{os.environ['PATH']}", "CIV_ROOT": str(civ5)})
        ok(r.returncode == 0 and "FAKE-CLAUDE model=MiniMax-M3" in r.stdout and "trial=yes" in r.stdout
           and seams["M3_ROUTER_BASE_URL"] in r.stdout, "model_boot.sh: first boot, then claude on M3 via the router")
        for sh in ("tools/restart-self.sh", "tools/launch_civ_tower.sh", "tools/launch_primary_visible.sh"):
            text = (civ5 / sh).read_text()
            fb, cl = text.find("tools/first_boot.py"), text.find("claude --")
            ok(0 < fb < cl, f"{sh}: first_boot.py runs before `claude`")
        civ5b = fresh(tmp / "civ5b")
        line = next(l for l in (civ5b / "tools/launch_primary_visible.sh").read_text().splitlines()
                    if "first_boot.py" in l and l.startswith("python3"))
        r = run(["bash", "-c", f'set -euo pipefail; CIV_ROOT="{civ5b}"; {line}; echo LAUNCH-CONTINUES'], civ5b)
        ok(r.returncode == 0 and "LAUNCH-CONTINUES" in r.stdout and "CANNOT START YET" in r.stderr,
           "launcher without seams: loud banner, launch continues (so the hook can tell the human)")

        print("[6] first boot from inside a running session")
        civ6 = fresh(tmp / "civ6")
        out = json.loads(gate(civ6, {"hook_event_name": "SessionStart", "session_id": "s1"},
                              {**seams, "ANTHROPIC_BASE_URL": "http://127.0.0.1:9/m3-router-not-provisioned"}))
        ok((civ6 / "config/trial.json").exists() and "restarted once" in out.get("systemMessage", ""),
           "hook provisions the trial and asks for one restart")
        out = json.loads(gate(civ6, {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "prompt": "hi"}))
        ok(out.get("decision") == "block" and "restart-self.sh" in out["reason"], "same session: prompts blocked")
        out = gate(civ6, {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "prompt": "hi"},
                   {"ANTHROPIC_BASE_URL": seams["M3_ROUTER_BASE_URL"]})
        ok("Day 1 of 7" in out, "same session already on the router env: not blocked")
        out = gate(civ6, {"hook_event_name": "UserPromptSubmit", "session_id": "s2", "prompt": "hi"})
        ok("Day 1 of 7" in out and "decision" not in out, "next session: normal trial grounding")

        print("[7] a born civ never silently ungates")
        civ7 = fresh(tmp / "civ7")
        first_boot(civ7, seams)
        (civ7 / "config/trial.json").unlink()
        ok("TRIAL EXPIRED" in gate(civ7, {"hook_event_name": "UserPromptSubmit", "session_id": "x", "prompt": "hi"}),
           "trial record deleted after birth -> fail CLOSED")
        r = first_boot(civ7, seams)
        ok(not (civ7 / "config/trial.json").exists(), "first boot does not re-birth a tampered civ (no fresh clock)")

        print("[8] agent manifests cannot be given a frontier pin")
        body = "---\nname: x\nmodel: claude-sonnet-4-6\n---\nhi\n"
        out = gate(civ, {"hook_event_name": "PreToolUse", "tool_name": "Write",
                         "tool_input": {"file_path": str(civ / ".claude/agents/new-agent.md"), "content": body}})
        ok('"deny"' in out, "Write of an agent with a frontier pin denied")
        out = gate(civ, {"hook_event_name": "PreToolUse", "tool_name": "Write",
                         "tool_input": {"file_path": str(civ / ".claude/agents/new-agent.md"),
                                        "content": body.replace("claude-sonnet-4-6", "inherit")}})
        ok('"deny"' not in out, "Write of an agent with `model: inherit` allowed")
        out = gate(civ, {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                         "tool_input": {"command": "python3 tools/first_boot.py --reset"}})
        ok('"deny"' in out, "the AiCIV cannot drive first_boot beyond `status`")
        out = gate(civ, {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                         "tool_input": {"command": "python3 tools/first_boot.py status"}})
        ok('"deny"' not in out, "first_boot.py status stays open")
        skill = (civ / ".claude/skills/agent-creation/SKILL.md").read_text()
        ok(not FRONTIER.search(skill) and "model: inherit" in skill, "agent-creation skill defaults to inherit")

        print("[9] conversion")
        r = run([sys.executable, "tools/apply_trial_profile.py", "convert", "--root", str(civ)], civ)
        ok(r.returncode == 0 and gate(civ, {"hook_event_name": "UserPromptSubmit", "session_id": "c",
                                            "prompt": "hi"}) == "", "convert: ungated immediately")
        r = run([sys.executable, "tools/apply_trial_profile.py", "convert", "--root", str(civ), "--restore-models"],
                civ, {"CIV_ROOT": str(civ)})
        ok((civ / ".claude/settings.json").read_bytes()
           == (SRC / "config/trial-m3-backup/settings.paid.json").read_bytes(),
           "--restore-models: settings.json = the paid template's, byte for byte")
        ok((civ / "config/launch_model.txt").read_text().strip() == "claude-opus-4-8", "--restore-models: paid launch model")
        r = run(["bash", "tools/model_switch.sh", "status"], civ, {"CIV_ROOT": str(civ)})
        ok("mode: default" in r.stdout, "model_switch back on the default rail")
        r = first_boot(civ, seams)
        ok(r.returncode == 0 and "converted" in r.stdout
           and json.loads((civ / "config/trial.json").read_text())["trial"] is False,
           "first boot after conversion is a no-op")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{PASSES} passed, {len(FAILS)} failed")
    for f in FAILS:
        print(f"  FAILED: {f}")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
