---
name: hermes-feishu-setup
description: "Configure the Hermes Feishu/Lark messaging gateway — single or multi-profile, with isolated cron delivery and Windows startup-service registration. Covers credentials, config.yaml enablement, /sethome home channel, Windows gateway install (incl. UAC→Startup fallback), and the Feishu event-subscription pitfalls that silently block inbound messages."
version: 1.2.0
author: Hermes Agent Contributors
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [hermes, feishu, lark, gateway, messaging, windows-service, multi-profile]
---

# Hermes Feishu / Lark Gateway Setup

Set up the Hermes <-> Feishu (Lark) bot integration: connect a bot, route
cron/notification delivery to a home channel, and (optionally) run **one
independent gateway process per Hermes profile** so multiple isolated
"employees" / tenants stay separated.

## Triggers

Use this skill when the user:
- Wants to connect a Feishu/Lark bot to Hermes (the config form with
  `Feishu / Lark encrypt key`, `Verification token`, `Home channel ID`, etc.).
- Asks about `/sethome`, home channel, or where cron results get delivered.
- Runs multiple Hermes profiles (e.g. `coder`, `analyst`) and wants each
  to have its OWN Feishu bot + its OWN channel for isolated cron delivery.
- Wants the gateway to survive reboots / start automatically on Windows.
- Reports "bot connected but no messages arrive" on Feishu.

## Architecture (read this first)

**Per-profile isolation = independent `HERMES_HOME`.** Each Hermes profile
(`~/.hermes/profiles/<name>/`) has its own `config.yaml`, `.env`,
`channel_directory.json`, and cron jobs. When you run a gateway with
`hermes -p <profile> gateway run`, that process reads ONLY that profile's
`.env` — so `FEISHU_HOME_CHANNEL` (the home channel cron delivers to) and
`FEISHU_APP_ID`/`FEISHU_APP_SECRET` are naturally per-profile.

Two valid topologies — **do not assume the shared/multiplexer one:**

1. **Independent processes (recommended for "multiple tenants").**
   Each profile gets its OWN Feishu app/bot, its OWN `HERMES_HOME`, its
   OWN gateway process. No port-sharing limits apply (those only bite the
   in-process multiplexer). See Pitfall #1.

2. **Single multiplexed gateway (`gateway.multiplex_profiles: true`).**
   Only the DEFAULT profile may enable port-binding platforms (feishu is one);
   secondary profiles reuse the default's listener via `/p/<profile>/`
   routing and must NOT enable feishu themselves. A single bot token cannot
   be polled twice. More fragile — prefer topology #1.

Cron delivery is per-profile by design (scheduler runs inside the
profile-scoped gateway and resolves `FEISHU_HOME_CHANNEL` from that
profile's `.env`). So topology #1 gives true isolation: profile A's cron
results land in A's channel, profile B's in B's.

## Steps

### 1. Feishu app/bot (Feishu Open Platform, not Hermes)
- Create an **enterprise self-built app** per bot you need.
- Note `App ID` and `App Secret` (credentials form).
- Enable the **bot** capability; in **事件订阅 (Event Subscription)** choose
  **长连接 (Long Connection / WebSocket)** mode — no public domain needed.
- Add the `接收消息` event (`im.message.receive_v1`) under Event Subscription.
  `机器人进群` (`im.chat.member.bot.added_v1`) alone is NOT enough — see
  Pitfall #2.
- Grant permissions: `im:message` (get & send single/group messages) at
  minimum. `im:chat*` for group info if needed.
- Put the bot in the target group(s).
- **Re-publish after changes** — see Pitfall #9.

### 2. Write credentials into the PROFILE's `.env`
`.env` files are **read-blocked by the file tool** (secret-bearing) but ARE
writable from the terminal. Append (do not overwrite):

```bash
# For profile "analyst":
cat >> "$HERMES_HOME/profiles/analyst/.env" <<'EOF'

FEISHU_APP_ID=cli_xxxxxxxx
FEISHU_APP_SECRET=xxxxxxxx
FEISHU_VERIFICATION_TOKEN=xxxxxxxx   # 凭证与基础信息 — REQUIRED
# FEISHU_ENCRYPT_KEY=xxxxxxxx        # 事件与回调→加密策略 — ONLY if that page shows a key (Pitfall #8b)
EOF
# Format is plain KEY=value, no quotes — match the default profile's existing
# FEISHU_APP_ID / FEISHU_APP_SECRET lines.
```

`FEISHU_VERIFICATION_TOKEN` is always required. `FEISHU_ENCRYPT_KEY` is
required **only** when the app's 加密策略 page actually shows one —
otherwise leave it blank (Pitfall #8b).

### 3. Enable feishu in the profile's `config.yaml`
Profiles created without a gateway section need one added:
```yaml
gateway:
  platforms:
    feishu:
      enabled: true
```
Use `hermes config edit` with `-p <profile>`, or append via a file-tool
patch anchored on the file's last line (Pitfall #16).

### 4. Register Windows startup (per profile)
```bash
hermes -p analyst gateway install --start-on-login --no-start-now
```
The generated launcher bakes in `HERMES_HOME=<profile home>` AND
`--profile <name>` → isolation at process level. `--no-start-now` installs
without launching. See Pitfall #5 (UAC fallback) and #17 (default profile
needs separate registration).

### 5. Start the gateway
```bash
hermes -p analyst gateway start
# default profile (no --profile):
hermes gateway start
```

### 6. Set the home channel (isolation key)
In the Feishu chat for that profile (DM works reliably; group is flaky —
Pitfall #10), send:
```
/sethome
```
This writes `FEISHU_HOME_CHANNEL=<chat_id>` into THAT profile's `.env`.
Cron/notification delivery for that profile now targets that channel only.

## Connected-but-silent diagnosis (leading word: **connected-but-silent**)

A Feishu bot showing `✓ feishu connected` but never receiving user messages
is the most common failure mode. The diagnosis has a fixed order; skip steps
only when the log artifact rules them out.

**Step 0 — Check Feishu 运营监控 → 日志检索 FIRST** (before any config
guessing). Search the test-message time window, read the **Status** column
on each `im.message.receive_v1` row:
- Row absent → event/permission not live on Feishu side → re-publish
  (Pitfall #9).
- Row = FAIL (4ms typical) → bad/mismatched `FEISHU_ENCRYPT_KEY` /
  `FEISHU_VERIFICATION_TOKEN` (Pitfall #8b).
- Row = SUCCESS but Hermes log has NO `Received raw message` →
  Feishu pushed, Hermes dropped it. Go to Step 1.

**Step 1 — Fix the subscription and keys (all three required):**
- (a) `im.message.receive_v1` event subscribed under 应用身份.
- (b) `FEISHU_VERIFICATION_TOKEN` in `.env` (Pitfall #8).
- (c) `FEISHU_ENCRYPT_KEY` in `.env` **only if** 加密策略 page shows a key;
  otherwise blank (Pitfall #8b).

**Step 2 — RESTART** (`hermes -p <profile> gateway restart`). Feishu
long-connection does NOT hot-load new events or keys. The decisive log line
is `[Feishu] Received raw message type=... message_id=...` — its presence
confirms Feishu is pushing AND keys verify; its absence means re-check
Steps 0–1.

**Step 3 — If DM works but group never arrives** → different failure layer.
See `references/feishu-events.md` (Pitfall #10).

## Pitfalls

**#1 — Don't force the multiplexer model.** If the user says they have
separate bots per profile ("two employees"), run **independent gateway
processes** with separate `HERMES_HOME`. It bypasses all the
port-binding / single-token limitations of `multiplex_profiles`.

**#2 — "provider failed" across ALL profiles means upstream, not Feishu.**
When every Feishu channel stops replying simultaneously with the same
provider-retry error, suspect `model.default`/`model.provider` first
(502/524/403/exceeded in `logs/errors.log`). Diagnostic split:
- All profiles, same provider error → fix model routing (switch model or
  provider; restart).
- One profile only → likely profile-specific session/cache; `/reset` in that
  channel or restart that profile.
- DM works, group fails → Feishu-side group issue (see `references/feishu-events.md`).

**#3 — Group messages require @-bot.** A bare `/sethome` in a group may be
ignored. Send `@<BotName> /sethome`.

**#4 — Windows gateway processes are `pythonw.exe`.** `ps aux` in
git-bash / MSYS **does not list them**. Verify with:
```bash
tasklist | find "pythonw"
```

**#5 — `gateway install` UAC fallback.** On Windows the installer tries
`schtasks` with elevation; in a non-interactive shell it auto-falls-back to
a Startup-folder `.vbs` login item. That still auto-starts on login.

**#6 — `.env` is read-blocked but terminal-writable.** Never use the file
tool to read/edit `.env`; use `cat >>` from the terminal and `grep` to
verify keys were written (without dumping secret values).

**#7 — Check the RIGHT log.** Each profile writes its own `<profile>/logs/`.
A successful inbound shows `[Feishu] Inbound ... message received`.
Empty log + `feishu connected` = events not subscribed or message not @-bot.

**#8 — `FEISHU_VERIFICATION_TOKEN` is required; `FEISHU_ENCRYPT_KEY` is
conditional.** Verification token is always required — without it the
WebSocket connects but inbound messages are silently dropped at the
verify layer. Encrypt key is required **only** when the app's
事件与回调 → 加密策略 page shows a key. If encryption is off and
`ENCRYPT_KEY` is filled, Feishu `receive_v1` = FAIL in ~4ms. Rule: when
in doubt, leave encrypt key blank and confirm via 日志检索.

**#9 — Feishu console changes need RE-PUBLISH, not just save.** Adding
`im.message.receive_v1`, granting `im:message`, or enabling the bot are
**draft** changes. The long-connection event set is taken from the LAST
PUBLISHED version. Going to **版本管理与发布 → 创建版本并发布** is required
for new events to reach the WS connection. Then RESTART (#2b above).

**#12 — Feishu pairing codes expire in ~1–2 minutes.** When a user DMs the
bot it gets a pairing code. Classic failure: screenshot → paste later →
`Code 'XXXX' not found or expired`. Fix: paste bare code text immediately,
or bypass by writing the user's open_id to `feishu-approved.json` directly.
See `references/feishu-diagnosis.md` for the recipe.

**#13 — Each Feishu app issues a DIFFERENT open_id for the same human.**
A user approved on one profile is NOT auto-approved on another. Pair (or
file-write approved JSON) EACH profile with THAT profile's app-specific
open_id. Pull IDs from each profile's own gateway log or `feishu-pending.json`.

**#17 — DEFAULT profile has NO autostart.** Per-profile `gateway install
--start-on-login` creates Startup `.vbs` items, but the DEFAULT gateway
needs explicit registration: `hermes gateway install --start-on-login
--no-start-now` (no `--profile` flag). Symptom: "feishu no response" with
no `gateway.pid` = process not running. `tasklist | find "pythonw"` is
Step 0 for any "no response" report.

## Verification checklist
- [ ] `tasklist | find "pythonw"` shows one PID per profile gateway.
- [ ] Each `<profile>/logs/` shows `connected` and `✓ feishu connected`.
- [ ] `/sethome` in each chat writes a DISTINCT `FEISHU_HOME_CHANNEL` (isolation proof).
- [ ] Sending a DM produces an `Inbound ... message received` line in THAT profile's log.
- [ ] A test cron in profile A delivers to channel A, not channel B.

## References
- `references/feishu-events.md` — Feishu event codes, permission scopes, group-vs-DM diagnosis, and the `connected-but-silent` interpretation table.
- `references/feishu-diagnosis.md` — per-profile setup recipes: strip cloned creds, locate the real log file, add a missing `gateway:` section, bypass expiring pairing codes, and the `Received raw message` log anatomy.
