# yourAICIV 7-day M3 trial template

This repository is the **birth template for yourAICIV trial AiCIVs**. An AiCIV is a persistent AI partner for one
human: it has its own name, memory, schedule, and a small organization of specialist minds it coordinates. Every
AiCIV born from this repository is a **7-day free trial that runs only on MiniMax-M3**. There is no trial step to
remember: the first boot turns the newborn into a trial automatically.

| Repository | What it is |
|---|---|
| **this one**, [`yourAICIV-fork-template-m3`](https://github.com/coreycottrell/yourAICIV-fork-template-m3) | trial births: MiniMax-M3 only, 7 days, then a payment link |
| [`yourAICIV-fork-template`](https://github.com/coreycottrell/yourAICIV-fork-template) | paid births (the same AiCIV; the trial exists there only as an opt-in profile) |
| [`yourAICIV-react-portal`](https://github.com/coreycottrell/yourAICIV-react-portal) | the portal the human uses to talk to their AiCIV; it shows the countdown and, after day 7, the payment screen |

yourAICIV is a reseller distribution (reseller: Travis Morehead). The brand, the reseller name, and the payment link
come from one file, `config/partner.json`.

> This repository is public. Secrets never live here. The router address and key, per-client secrets, and customer
> data are **seams** that provisioning fills at birth, outside version control (see [Provisioning](#provisioning)).

---

## What the human experiences

The AiCIV knows it is on "Day N of 7" from its first message to its last, and says so plainly, as a countdown and never
as pressure. Its operating contract for the week is `.claude/skills/m3-trial-mode/SKILL.md`.

| When | What happens |
|---|---|
| **Hour 0-1** | **It gets to know the human first.** A short identity interview covers their biggest goal, their 90-day goal, their skills and domain, and what would impress them. Goals and aspirations come before any showing off, so the first build is aimed at *them*. Three builds are locked from those answers. |
| **Hour 1+** | **The first WOW ships as soon as it is ready.** It aims for the first session: for example a live site from the delivery engine, or a real plan against their 90-day goal. A check-in 4 hours after birth makes sure there is a first win. |
| **Day 1 evening** | A preview: "here is what I'll have for you tomorrow." |
| **By end of Day 2** | Build #2, without being asked. It acts on its own; nothing waits for the human to email first. |
| **Day 3** | **Hard ceiling for Build #1** (72 hours is a ceiling, never a waiting period), plus deep research on their real question with every claim sourced. |
| **Day 4** | A proactive surprise and the first business number (CRM or dashboard from the delivery engine). |
| **Day 5** | The main showcase, while they are still deciding. |
| **Day 6** | Week in review: everything shipped, each item with a link, and an honest, specific ask to subscribe. |
| **Day 7** | A week-two roadmap and a plain explanation of what happens when the trial ends. |

Every factual claim carries a source URL or an on-disk receipt, and a second mind checks each build before it ships
(`workflows/m3-trial-build.js`, `tools/receipt_check.py`). If research could not be verified, the AiCIV says so
instead of guessing.

### Day 7: paused, never deleted

When `expires_at` passes:

- **The AiCIV stops working.** Its hook (`.claude/hooks/trial_gate.py`) blocks every work tool. It answers any message
  with a short, warm note: the trial has ended, everything is saved, and here is the link to continue
  (`payment_url`, from `config/partner.json`).
- **The portal** replaces everything with a payment screen. Its API answers 402 except for `/api/trial`.
- **Nothing is deleted.** Work, files, memory, and running client sites stay exactly as they were.

### Conversion (after the human pays)

```bash
sudo -E python3 tools/apply_trial_profile.py convert --root "$CIV_ROOT"                    # ungate now
sudo -E python3 tools/apply_trial_profile.py convert --root "$CIV_ROOT" --restore-models   # and move to paid routing
```

`convert` writes `"trial": false` to the operator copy (the one the portal reads) and to the civ copy. The portal
and the AiCIV ungate within seconds, with no restart. `--restore-models` also puts back the **paid** configuration
this repository keeps in `config/trial-m3-backup/`: `.claude/settings.json` (byte for byte the paid template's), all
112 agent model pins, and the paid launch model. It unlocks the model switch. Every trial file is kept as an audit
copy. The paid model applies from the next session start.

Conversion is manual for now. The planned follow-up is a Stripe `checkout.session.completed` webhook on the payment
link that runs `convert` for the matching civ.

---

## How a birth works

Nothing changes for the fleet. Stamp the template, fill the usual template variables
(`tools/template_substitute.sh`), provide the seams below, and start the AiCIV the way you always do. The **first
boot** does the rest.

`tools/first_boot.py` runs automatically **before the first model call**, from every path that starts the AiCIV:

- `tools/restart-self.sh` (the fleet's launch and restart path);
- `tools/launch_civ_tower.sh`, `tools/launch_primary_visible.sh`, `tools/model_boot.sh`;
- the trial hook on `SessionStart` and on every prompt, as the safety net for any other launcher.

On the first boot that has the router seams, it runs `tools/apply_trial_profile.py apply`:

- writes `config/trial.json`: `started_at` = now, `expires_at` = 7 days later, `payment_url` / `brand` /
  `reseller` from `config/partner.json`, `model` = `MiniMax-M3`;
- routes every model surface to MiniMax-M3 through the router (the primary, every specialist, every workflow, every
  VP incarnation), sets the key helper, and keeps the **full VP organization**;
- locks the model profile, installs the trial grounding block in `.claude/CLAUDE.md`, and ends with `check`, which
  must print `NO FRONTIER MODEL REACHABLE`.

It records the outcome in `config/birth_status.json` (`python3 tools/first_boot.py status`). It is idempotent: a
born civ is left alone and the clock is never restarted, and a converted civ is never re-birthed.

After fixing a problem on a born civ, `python3 tools/first_boot.py --verify` re-runs the check; when it passes, a
stale `failed`/`blocked` record in `config/birth_status.json` becomes `trial-active` (with `previous_status` and
`reverified_at`; the dates are read from the trial record, never restarted). The check's tree scan skips runtime
status and log files (`config/birth_status.json`, `logs/`, the partner-notification mail), which quote earlier
findings rather than route anything.

`config/partner.json` (the reseller partner profile):

```json
{"brand": "yourAICIV", "reseller": "Travis Morehead", "payment_url": "https://buy.stripe.com/...",
 "notify_emails": []}
```

**Nothing reaches a frontier model, even before first boot.** The tree ships with `MiniMax-M3` on every model setting
(`.claude/settings.json` `model` and all six model env keys, `config/launch_model.txt`, the launch scripts' fallback),
every agent manifest set to `model: inherit`, the model switch locked, and `ANTHROPIC_BASE_URL` pointed at a closed
local port until first boot fills in the router. `python3 tools/apply_trial_profile.py check --static` proves this on
an unborn tree.

### If the router seams are missing

The AiCIV **does not fall back to another model and does not start its clock.** It says so to everyone who can act:

- **Operator:** `first_boot.py` prints a banner and exits 2 (the launchers show it and still start the session), and
  `config/birth_status.json` reads `{"status": "blocked", "missing": [...]}`.
- **Human:** the session opens with a system message, and every message they send is answered by the hook, with no
  model call: *"THIS AiCIV CANNOT START YET. It is a yourAICIV 7-day trial that runs ONLY on MiniMax-M3, and its M3
  router was not provided at birth ... It will not fall back to any other model ..."* Every tool call is denied.

Fix: provide the seams, run `python3 tools/first_boot.py`, and restart the session (`tools/restart-self.sh`).

If first boot happens inside an already-running session (the hook path, when a launcher other than the ones above
started Claude), that session's settings predate the router. The hook blocks that session's prompts with a
one-restart notice for the operator. The next session runs on M3 with the clock already running.

### Partner notifications: off by default

**Reseller notifications come from True Bearing, not from the AiCIV** (Corey 2026-09-27). Not every AiCIV has an
email inbox, and True Bearing already emails the reseller about billing and trial events from its own side. So
`notify_emails` ships empty, and with it empty:

- the AiCIV sends nothing, queues nothing (`memories/partner-notifications/` is never created), and shows no
  "email not provisioned / queued" status to its human or operator;
- the watchdog skips its partner checks, and `apply_trial_profile.py convert` says nothing about the partner;
- client-site business alerts (lead, order, booking, affiliate application) go to the client owner only.

The code path is kept, dormant: `tools/partner_notify.py` (`send | sweep | flush | tick | status | enabled`) and
skill `.claude/skills/partner-notifications/SKILL.md`. An operator can switch it on for one civ by putting addresses
in `notify_emails` or setting `PARTNER_NOTIFY_EMAILS`; it then needs an AgentMail inbox on that civ (see the skill).

---

## Provisioning

Set these **for the AiCIV's container** (process environment, or one `KEY=VALUE` file at `/etc/aiciv/m3-router.env`,
which `first_boot.py` reads when a variable is not in the environment; `M3_SEAMS_FILE` overrides that path):

| Seam | Required | Value |
|---|---|---|
| `M3_ROUTER_BASE_URL` | **yes** | Anthropic-wire base URL of this tenant's MiniMax-M3 router |
| `M3_ROUTER_KEY_FILE` | **yes** (or `M3_ROUTER_KEY`) | path to this tenant's router key file (or `M3_ROUTER_KEY=<key>`). Copied to `config/lifeboat/router_key.txt`, mode 0600, gitignored, never echoed |
| `TRIAL_OPERATOR_COPY` | production | `/etc/aiciv/trial.json`: the trial record published **outside** the civ tree. The AiCIV can write its own tree, so access must never depend on the in-tree copy. First boot must be able to write it: run first boot as root once (for example `docker exec -u root <container> python3 /home/aiciv/tools/first_boot.py --root /home/aiciv`), which leaves the copy root-owned and gives every in-tree file back to the civ's user. An unwritable path is refused **before** any clock is written |
| `PORTAL_PUBLIC_URL` | yes, for client sites | the AiCIV's public portal address (process env or `~/.env`). Client sites go live at `<PORTAL_PUBLIC_URL>/site/<slug>/`; without it, the setup links and Stripe return URLs fall back to a placeholder |
| `M3_MODEL_ID` | no | default `MiniMax-M3` |
| `TRIAL_PAYMENT_URL` | no | overrides `payment_url` from `config/partner.json` for one birth (must be `https://`) |
| `TRIAL_START` | no | ISO8601 UTC; default is the moment of first boot |

**The portal** (same container) runs with `TRIAL_CONFIG_PATH=/etc/aiciv/trial.json`, the same path as
`TRIAL_OPERATOR_COPY`. `apply` records that path in `.claude/settings.json` too, so the AiCIV's hook reads the same
record. Without an operator copy the record is `config/trial.json`, which works, but the portal then logs that its
source is civ-writable.

**Required on the router side (outside this repository).** Anyone with a shell can edit files inside a container, so
the router is the real boundary for a trial:

1. one key per trial civ, sized for the full organization (an undersized slice means a dead AI on Day 1);
2. the key forwards only MiniMax model ids;
3. the key expires (or throttles to a trickle) at `expires_at`, and is replaced on conversion;
4. no other model credentials in a trial container: no Claude login, no `ANTHROPIC_API_KEY`, and an empty
   `GOOGLE_API_KEY` (`check` flags them);
5. web search and fetch work through the router, or research is marked "unverified" rather than guessed.

Full profile detail: `profiles/trial-m3/README.md`.

---

## Watchdog after a container restart

Birth starts `tools/watchdog.sh` in a detached tmux session named `watchdog`. A container restart kills it, and
nothing in the container brings it back. The AiCIV's own session start does: the SessionStart hook runs
`tools/ensure_watchdog.py`, which starts the watchdog the same way when it is not running and does nothing when
it is. It never starts a second copy, never blocks the session, and logs one line to `logs/watchdog.log` when it
acts. It only acts in the civ root: the tree it ships in, when that tree is `$HOME` (the fleet checks the template
out at `/home/aiciv`, which is also HOME; the older `/home/aiciv/civ` layout is also accepted). A copy anywhere
else (a developer checkout, a test copy) is left alone. `AICIV_CIV_ROOT` overrides the root;
`AICIV_ENSURE_WATCHDOG=0` turns it off. No fleet startup hook is needed.

The command it starts carries the root along (`CLAUDE_PROJECT_DIR=<root> HOME=<home> bash <root>/tools/watchdog.sh`),
and `watchdog.sh` itself defaults `CLAUDE_PROJECT_DIR` to the tree it lives in, so its log, `.current_session`,
client sites and partner notifications always resolve to the civ's own tree. `bash tools/watchdog.sh --config`
prints what it resolved.

When the watchdog restarts the portal (`start.sh`), it passes `PORTAL_PUBLIC_URL` and `TRIAL_CONFIG_PATH`
through. A value missing from its own environment is read from `~/.env`, then `<civ>/.env`, and
`TRIAL_CONFIG_PATH` finally from `.claude/settings.json` `env`.

---

## Checks

```bash
python3 tools/apply_trial_profile.py check --static   # unborn tree: nothing pins or reaches a frontier model
python3 tools/apply_trial_profile.py check            # born civ: NO FRONTIER MODEL REACHABLE
python3 tools/first_boot.py status                    # blocked / trial-active, dates, where the record lives
python3 tools/trial_state.py status                   # the portal's /api/trial JSON
python3 tools/test_first_boot.py                      # first-boot suite (scratch births, no network)
python3 tools/test_trial_profile.py                   # trial profile + partner + conversion suite
python3 tools/test_partner_notify.py                   # partner notifications: off by default = silent; switched on = once per event
apps/.venv/bin/python tools/test_delivery_engine.py    # delivery engine (owner-only alerts by default)
python3 tools/test_ensure_watchdog.py                 # watchdog self-heal after a container restart + portal env passthrough
```

The delivery engine has its own suite: `tools/test_delivery_engine.py` (run with a Python that has
`apps/client-starter/requirements.txt` installed), plus `apps/client-starter/preflight.sh` and the V1-V19 list in
`.claude/skills/client-onboarding/SKILL.md`, Phase 4.

---

## The delivery engine

`apps/client-starter/` is a self-hosted Flask/SQLite business system: public funnel, CRM, a three-number dashboard,
email automations, store, blog, affiliates, booking, and pluggable payments with Stripe as the default. The AiCIV runs
it **for** its human (client #1 is their own business by default) and for their clients. It is the fastest route to a
Day-1 WOW for a small-business owner.

- Operating manual: `.claude/skills/client-onboarding/SKILL.md`.
- `clone_client.sh <client-slug>` stamps a per-client instance with its own secrets, database, and port, bound to
  `127.0.0.1` and gitignored. `tools/client_sites.py go-live` publishes it through the portal.
- **Trial rules:** the AiCIV confirms with its human before putting a client site public. After expiry, no new client
  work starts, and running client sites are never stopped or deleted (the portal answers them with a neutral 503).

---

## Layout

| Path | What |
|---|---|
| `tools/first_boot.py` | the first-boot step that makes every birth a trial |
| `.claude/CLAUDE.md` | the newborn's constitution, with its self-removing birth gates at the top |
| `.claude/settings.json` | ships M3-only; first boot adds the router |
| `.claude/hooks/trial_gate.py` | the AiCIV side of the trial: countdown, M3-only guard, Day-7 pause, first-boot safety net |
| `.claude/skills/m3-trial-mode/` | the AiCIV's operating contract for the week |
| `profiles/trial-m3/` | the trial profile (what `apply` changes and why) |
| `config/partner.json` | reseller brand, reseller name, payment link, partner notification addresses (empty = off, the default) |
| `config/trial-m3-backup/` | the paid configuration that conversion restores |
| `apps/client-starter/` | the delivery engine |
| `.claude/skills/partner-notifications/` | dormant AiCIV-side reseller feed; OFF by default (reseller notifications come from True Bearing) |
| `tools/partner_notify.py` | the thin sender for that feed; a silent no-op while `notify_emails` is empty |
| `workflows/` | multi-mind workflows, including the trial's build, verify, and ship loop |
