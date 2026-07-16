---
name: hermes-feishu-setup
description: "Configure the Hermes Feishu/Lark messaging gateway — single or multi-profile, with isolated cron delivery and Windows startup-service registration. Covers credentials, config.yaml enablement, /sethome home channel, Windows gateway install (incl. UAC→Startup fallback), and the Feishu event-subscription pitfalls that silently block inbound messages."
version: 1.1.0
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

> This skill was distilled from a real multi-day debugging session where a
> Feishu bot showed `✓ feishu connected` but never received a single user
> message. Every Pitfall below is a failure mode that actually happened.

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

### 1. Feishu app/bot (do in Feishu Open Platform, not Hermes)
- Create an **enterprise self-built app** per bot you need.
- Note `App ID` and `App Secret` (credentials form).
- Enable the **bot** capability; in **事件订阅 (Event Subscription)** choose
  **长连接 (Long Connection / WebSocket)** mode — no public domain needed.
- **Critical:** add the `接收消息` event (`im.message.receive_v1`) under
  Event Subscription. `机器人进群` (`im.chat.member.bot.added_v1`) alone is
  NOT enough — see Pitfall #2.
- Grant permissions: `im:message` (get & send single/group messages) at
  minimum. `im:chat*` for group info if needed.
- Put the bot in the target group(s).
- **Re-publish:** after adding the event/permissions, go to
  **版本管理与发布 → 创建版本并发布** — see Pitfall #9.

### 2. Write credentials into the PROFILE's `.env`
`.env` files are **read-blocked by the file tool** (secret-bearing) but ARE
writable from the terminal. Append (do not overwrite):

```bash
# For profile "analyst":
cat >> "$HERMES_HOME/profiles/analyst/.env" <<'EOF'

FEISHU_APP_ID=cli_xxxxxxxx
FEISHU_APP_SECRET=xxxxxxxx
FEISHU_VERIFICATION_TOKEN=xxxxxxxx   # 凭证与基础信息 — REQUIRED (Pitfall #8)
# FEISHU_ENCRYPT_KEY=xxxxxxxx        # 事件与回调→加密策略 — ONLY if that page shows a key (Pitfall #8b)
EOF
# Format is plain KEY=value, no quotes — match the default profile's existing
# FEISHU_APP_ID / FEISHU_APP_SECRET lines.
```
⚠️ **Four keys, not two.** `FEISHU_VERIFICATION_TOKEN` and
`FEISHU_ENCRYPT_KEY` are the form's first two fields (encrypt key /
verification token). Verification token is always required; encrypt key is
required ONLY when the app's 加密策略 page actually shows one — otherwise
leave it blank (Pitfall #8b). With verification token blank the WebSocket
still connects, yet every inbound message is **silently dropped at the
decrypt/verify layer** (see Pitfall #8).

### 2b. RESTART the gateway after ANY Feishu-console change (CRITICAL)
Feishu long-connection (WebSocket) mode does **NOT hot-load** newly
subscribed events or changed keys. If you add `im.message.receive_v1`
or fill the encrypt/verify keys in the console while the gateway is running,
the established connection KEEPS the OLD subscription — Feishu never
pushes message events to it. You MUST restart:
```bash
hermes -p analyst gateway restart
```
`$HERMES_HOME` on Windows defaults to `C:\Users\<user>\AppData\Local\hermes`.
Per-profile home is `$HERMES_HOME/profiles/<name>`.

### 3. Enable feishu in the profile's `config.yaml`
Profiles created without a gateway section need one added:
```yaml
gateway:
  platforms:
    feishu:
      enabled: true
```
Use `hermes config edit` with `-p <profile>`, or append via a file-tool
patch anchored on the file's last line (Pitfall #16). If the file already
ends with e.g. `image_gen: / use_gateway: true`, append after it.

### 4. Register as a Windows startup service (per profile)
```bash
hermes -p analyst gateway install --start-on-login --no-start-now
```
- Task name is auto-scoped: `Hermes_Gateway_<profile>` (default = `Hermes_Gateway`).
- The generated launcher (`.vbs`/`.cmd` under `<profile>/gateway-service/`)
  bakes in `HERMES_HOME=<profile home>` AND `--profile <name>` → isolation
  is enforced at the process level. Verify with
  `grep HERMES_HOME <profile>/gateway-service/Hermes_Gateway_<profile>.vbs`.
- `--no-start-now` installs but does not launch (use when the user will
  finish Feishu-side setup first). `--start-now` launches immediately.

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

## Pitfalls (learned the hard way)

**#1 — Don't force the multiplexer model.** If the user says they have
separate bots per profile ("two employees"), run **independent gateway
processes** with separate `HERMES_HOME`. It bypasses all the
port-binding / single-token limitations of `multiplex_profiles`.

**#2 — Feishu "connected" but never receives messages.**
DECTIVE STEP 0 (do this BEFORE guessing at keys/identity):
open Feishu Open Platform → your app → **运营监控 → 日志检索**,
search the test-message time window, read the **Status** column on each
`im.message.receive_v1` row. This one screenshot ends the guessing:
- row absent entirely → event/permission not live on Feishu side →
  re-publish the app version (版本管理与发布) after the change (Pitfall #9).
- row = FAIL (4ms typical) → bad/mismatched
  `FEISHU_ENCRYPT_KEY`/`FEISHU_VERIFICATION_TOKEN` (Pitfall #8b).
- row = SUCCESS yet Hermes log has NO `Received raw message` →
  Feishu pushed but Hermes dropped it (keys blank, or
  receive event not actually under 应用身份). Cross-check
  `references/feishu-events.md`.
A full "connected but silent" session was lost to key/identity
guessing for many turns before this log was checked — check it FIRST.

Then the two independent causes, BOTH must be fixed, then RESTART (#2b):
  (a) Missing `im.message.receive_v1` event. The adapter shows
      `✓ feishu connected` (WebSocket up) even when only `机器人进群`
      is subscribed. Without `接收消息`, Feishu pushes NOTHING on user
      messages. Fix: Event Subscription → 添加事件 → check
      `接收消息 v2.0` (`im.message.receive_v1`). Permissions
      (`im:message`) can be enabled yet messages still won't arrive if the
      EVENT isn't subscribed — they are independent settings.
  (b) Missing `FEISHU_VERIFICATION_TOKEN` in the profile's `.env` (Pitfall #8).
      Event subscribed + perms on + still silent = token blank → messages
      decrypt/verify-fail and are dropped silently.
  (c) Gateway process predates the console changes → MUST restart
      (Pitfall #2b). The long connection does NOT hot-load new
      event subscriptions or keys.

**#2b — RESTART after console changes.** Feishu WebSocket mode
does not hot-load newly subscribed events. Add the event / fill keys in
the console, then `hermes -p <profile> gateway restart`. A process
that's been up since before the change will never receive message
events — this alone produced a full "connected but silent" session.

**#3 — Group messages are only pushed when the bot is @-mentioned.**
A bare `/sethome` in a group may be ignored. Send `@<BotName> /sethome`.

**#4 — Windows gateway processes are `pythonw.exe` (GUI subsystem).**
`ps aux` in git-bash / MSYS **does not list them**. Verify with:
```bash
tasklist | find "pythonw"
# or PowerShell:
powershell -NoProfile -Command "Get-Process pythonw"
```
The `gateway.pid` file is often absent; trust `tasklist` / the live
`logs/` (see #15) for `connected` / `Received raw message`.

**#5 — `gateway install` UAC fallback.** On Windows the installer tries
`schtasks` with elevation; in a NON-INTERACTIVE shell (no UAC click
possible) it auto-falls-back to a Startup-folder `.vbs` login item. That
still auto-starts on login — acceptable — but if you need the more robust
Scheduled Task (restart-on-failure, starts pre-login), run the SAME
command in a normal interactive terminal where you can click "Yes" on the
UAC prompt.

**#6 — `.env` is read-blocked but terminal-writable.** Never use the file
tool to read/edit `.env`; use `cat >>` from the terminal and `grep` to
verify keys were written (without dumping secret values).

**#7 — Check the RIGHT log.** Each profile writes its own
`<profile>/logs/`. A successful inbound shows
`[Feishu] Inbound ... message received: ... chat_id=oc_... sender=user:ou_...`.
Empty log + `feishu connected` = events not subscribed (Pitfall #2) or
message not @-bot (Pitfall #3).

**#8 — Silent drop when `FEISHU_VERIFICATION_TOKEN` is missing.**
The config FORM's second field (verification token) maps to this `.env` key.
It is NOT optional for message RECEIPT even though the WebSocket
connects fine with only `APP_ID`/`APP_SECRET`. With it blank, the
adapter's `EventDispatcherHandler` (built from verification_token) fails to
verify inbound payloads, so the message is dropped BEFORE the
`Received raw message` log line. Fill it per profile, then RESTART (#2b).
Exact console source: 凭证与基础信息 (Verification Token).

**#8b — `FEISHU_ENCRYPT_KEY` can be BLANK if the Feishu app has NO
加密策略 enabled.** If the app's 事件与回调 → 加密策略 is left
disabled, Feishu pushes events IN CLEARTEXT and the adapter expects no
decryption. Filling `FEISHU_ENCRYPT_KEY` in that case makes the
`EventDispatcherHandler` try to decrypt plaintext → it fails FAST (Feishu
日志检索 shows `receive_v1` = FAIL in ~4ms). Symptom signature:
  - event subscribed + keys blank → Feishu `receive_v1` SUCCESS but
    Hermes log has no `Received raw message` (decrypt silently drops).
  - event subscribed + `ENCRYPT_KEY` filled but app has no 加密策略 →
    Feishu `receive_v1` = FAIL (4ms) and Hermes still sees nothing.
  So: only set `FEISHU_ENCRYPT_KEY` if the console's 加密策略 page
  actually shows a key. When in doubt, leave it blank and confirm
  Feishu's 日志检索 flips from FAIL→SUCCESS (or stays SUCCESS with
  messages arriving).

**#9 — Feishu console changes need a RE-PUBLISH, not just save.**
Adding `im.message.receive_v1` under 事件订阅, granting `im:message`
permissions, or enabling the bot capability are all **draft** changes.
The long-connection (应用身份) event set is taken from the LAST
PUBLISHED version, NOT the live draft. If you only "saved" without
going to **版本管理与发布 → 创建版本并发布**, the WS connection keeps
the OLD event set — so `机器人进群` (subscribed in an earlier published
version) arrives, but `接收消息` (added in the draft) never does. This
is the single most common "connected but bot only sees join events"
trap. Verify: 版本管理与发布 latest-version timestamp must be AFTER the
time you added `receive_v1`. Re-publish, then RESTART (#2b).

**#10 — DM works but GROUP messages never arrive — different class of
problem.** If `Inbound dm message received` appears in the log yet no
`chat_id=oc_...` for the group ever shows up (and Feishu 日志检索
`receive_v1` rows are SUCCESS), the group message path is blocked at the
Feishu side, independent of the DM path. Known group-only blockers:
  - bot not actually a member of that group / was removed;
  - the message wasn't @-bot (Pitfall #3) — but even with @-bot, group
    push can stay silent if the app's group-message permission scope
    (`im:message` sub-permission "获取群组中用户@机器人消息") wasn't
    included in the published version;
  - group events go through a different subscription dimension than DM
    in some app configs.
DM-only success does NOT prove group config is fine. If group delivery
is required, validate it separately (send `@bot /sethome` in the group,
watch that profile's log for a group `chat_id`). If group keeps failing,
it is acceptable to fall back to DM-based interaction — the per-profile
home channel can still be set via a DM `/sethome`.

**#11 — `Received raw message` is the decisive log line.** The
adapter logs `[Feishu] Received raw message type=... message_id=...`
ONLY after a payload is successfully decrypted/verified and handed in. Its
presence = Feishu IS pushing message events AND keys verify them.
Its ABSENCE (with `feishu connected`) = fix Pitfall #2a (event
not subscribed) or #8 (token blank). Steps #2a/#8 alone don't
surface this line — you also need the restart from #2b.

**#12 — Feishu pairing codes expire in ~1-2 minutes.** When a user
DMs the bot it replies `这是您的配对码: XXXXXXXX` with the command
`hermes pairing approve 飞书 XXXXXXXX`. That code is short-lived. The
classic failure: user screenshots the code, pastes it back later →
`Code 'XXXX' not found or expired`. Fixes, in order of preference:
  (a) Have the user paste the **bare code text** (not a screenshot) so
      you run `hermes -p <profile> pairing approve feishu <CODE>`
      within seconds of it appearing.
  (b) If codes keep expiring (slow loop), bypass the code: write the
      user's open_id directly into
      `profiles/<name>/platforms/pairing/feishu-approved.json` in the
      exact structure `approve` produces:
      `{"<open_id>": {"user_name": "", "approved_at": <unix_float>}}`
      (use `time.time()`). Then `hermes -p <profile> gateway restart`
      so it reloads the allowlist.
  Get the correct open_id from THAT profile's own gateway log
  (`sender=user:ou_...`) or its `feishu-pending.json` — never copy an
  ID from another profile (see #13).

**#13 — Each Feishu app issues a DIFFERENT open_id for the same human.**
If your first app (`cli_xxx` example) and your second app
(`cli_yyy` example) are different apps, each mints its OWN open_id for
you. A user approved on one profile is NOT auto-approved on another — the
adapter matches on the app-specific open_id. Consequence: you MUST pair
(or file-write the approved JSON) EACH profile with THAT profile's
app-specific open_id. Do NOT copy an approved ID from one profile's
`feishu-approved.json` into another — it won't match and messages stay
blocked. Pull each profile's correct ID from its own gateway log
(`sender=user:ou_xxx`) or its own `feishu-pending.json`.

**#14 — A profile created via clone carries the SOURCE's Feishu creds.
Strip them FIRST.** `hermes profile create <new> --clone-from <src>`
copies `<src>/.env` wholesale, so `<new>/.env` already has
`FEISHU_APP_ID/SECRET/HOME_CHANNEL` from the source bot. If you miss
this, the new profile silently uses the source app AND shares its home
channel → cron collisions + cross-talk. FIX before enabling feishu —
strip and replace:
```bash
python - "$HERMES_HOME/profiles/<new>/.env" <<'PY'
import sys, re
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
for k in ("FEISHU_APP_ID","FEISHU_APP_SECRET","FEISHU_VERIFICATION_TOKEN",
          "FEISHU_ENCRYPT_KEY","FEISHU_HOME_CHANNEL","FEISHU_HOME_CHANNEL_THREAD_ID"):
    s = re.sub(rf'(?m)^{k}=.*\n', '', s)
# then append the NEW app's values (encrypt key blank if app has
# no 加密策略 — Pitfall #8b). Do NOT leave the source's values behind.
open(p,"w",encoding="utf-8").write(s)
PY
```
After restart, confirm `<new>`'s `FEISHU_HOME_CHANNEL` is DISTINCT from
every other profile's (isolation proof).

**#15 — Profile gateway log is NOT always `gateway.log`.** Cloned/older
profiles may write to `logs/gateway-stdio.log` (or `gateway-exit-diag.log`,
`agent.log`) instead of `gateway.log`. If `tail logs/gateway.log` says
"No such file", list the `logs/` dir and grep the real files for
`connected` / `Received raw message`. The decisive WS-up line is:
`[Lark] connected to wss://msg-frontier.feishu.cn/ws/v2?...`
`gateway-exit-diag.log` may show non-zero-exit entries from a prior
restart's OLD pid — ignore them if a CURRENT pid is alive and WS shows
connected. Confirm PIDs with `tasklist | find "pythonw"` (Pitfall #4).

**#16 — Enabling feishu in `config.yaml`: the `gateway:` section is
often ABSENT on cloned profiles.** `hermes config edit -p <profile>`
may show no `gateway:` block at all (file ends at e.g. `image_gen:`).
A heredoc/python append that looks for `gateway:` can mis-detect
(`use_gateway: true` contains the substring) and silently write nothing.
RELIABLE method: `patch` the file appending, anchored on the LAST line:
```yaml
image_gen:
  use_gateway: true

gateway:
  platforms:
    feishu:
      enabled: true
```
Verify with `grep -nE "gateway:|feishu:|enabled" profiles/<new>/config.yaml`.
See `references/feishu-diagnosis.md`.

**#17 — The DEFAULT profile has NO autostart; its gateway silently dies
after a reboot.** Per-profile `gateway install --start-on-login` creates
Startup-folder `.vbs` items, but the DEFAULT gateway is NOT auto-registered
by those commands — you must run `hermes gateway install --start-on-login
--no-start-now` with **NO `--profile` flag** (default is the implicit one).
It produces `Hermes_Gateway.vbs` (no `_<profile>` suffix) in the Startup
folder. Symptom of a missing default: "feishu no response" with zero log
activity AND no `gateway.pid` = the process simply isn't running. STEP 0 on
any "no response" report: `tasklist | find "pythonw"` — a missing PID means
"start it", not "debug the config". All employees should have a Startup
`.vbs`; after registering default, a reboot self-heals all of them.

## Verification checklist (after setup)
- [ ] `tasklist | find "pythonw"` shows one PID per profile gateway.
- [ ] Each `<profile>/logs/` shows `connected` and `✓ feishu connected`.
- [ ] `/sethome` in each chat writes a DISTINCT `FEISHU_HOME_CHANNEL` in each profile's `.env` (isolation proof).
- [ ] Sending `@bot /sethome` (or DM `/sethome`) produces an `Inbound ... message received` line in THAT profile's log only.
- [ ] A test cron in profile A delivers to channel A, not channel B.

## References
- `references/feishu-events.md` — Feishu event codes, permission scopes, and the exact "connected-but-silent" diagnosis flow.
- `references/feishu-diagnosis.md` — per-profile setup gotchas: strip cloned creds, locate the real log file, add a missing `gateway:` section, bypass expiring pairing codes.
