---
name: hermes-feishu-setup
description: "Configure the Hermes Feishu/Lark messaging gateway — single bot or multi-profile isolation with independent cron delivery. Use when connecting a Feishu bot, setting /sethome, registering Windows gateway autostart, isolating multiple Hermes profiles with separate Feishu apps, or debugging message-delivery failures."
version: 1.3.0
author: Hermes Agent Contributors
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [hermes, feishu, lark, gateway, messaging, windows-service, multi-profile]
---

# Hermes Feishu / Lark Gateway Setup

Configure Hermes <-> Feishu (Lark) bot integration with per-profile isolation.

## Leading word

**feishu-gateway-setup** — set up or repair the Hermes <-> Feishu connection so a profile reliably receives messages and delivers cron output to the right channel.

## Architecture

**Per-profile isolation = independent `HERMES_HOME`.** Each profile (`~/.hermes/profiles/<name>/`) has its own `config.yaml`, `.env`, and gateway process.

Topologies:
1. **Independent processes (recommended for multiple tenants).** Each profile gets its own Feishu app, `HERMES_HOME`, and gateway process. No port-sharing limits.
2. **Single multiplexed gateway** (`gateway.multiplex_profiles: true`). Only the default profile may enable feishu; secondary profiles reuse the default's listener. More fragile.

Cron delivery is per-profile by design, resolving `FEISHU_HOME_CHANNEL` from that profile's `.env`.

## Steps

### 1. Create Feishu app (Feishu Open Platform)

- Create an **enterprise self-built app** per bot.
- Note `App ID` and `App Secret`.
- Enable **bot** capability; choose **长连接 (Long Connection / WebSocket)** mode.
- Add event `接收消息` (`im.message.receive_v1`) under Event Subscription.
  - `机器人进群` alone is NOT enough.
- Grant minimum permission: `im:message`.
- Put bot in target group(s).
- **Re-publish after changes.**

**Completion criterion**: Feishu app has bot enabled, `im.message.receive_v1` subscribed, and at least one published version.

### 2. Write credentials to profile `.env`

Append to `$HERMES_HOME/profiles/<profile>/.env`:

```bash
FEISHU_APP_ID=cli_xxxxxxxx
FEISHU_APP_SECRET=xxxxxxxx
FEISHU_VERIFICATION_TOKEN=xxxxxxxx   # REQUIRED
# FEISHU_ENCRYPT_KEY=xxxxxxxx        # ONLY if 加密策略 page shows a key
```

Rules:
- `FEISHU_VERIFICATION_TOKEN` is always required.
- `FEISHU_ENCRYPT_KEY` is required **only** when 加密策略 shows a key.
- Never read `.env` with the file tool; use `cat >>` and `grep`.

**Completion criterion**: `.env` contains the three required lines; `grep` confirms they are present.

### 3. Enable feishu in `config.yaml`

```yaml
gateway:
  platforms:
    feishu:
      enabled: true
```

**Completion criterion**: `config.yaml` has `gateway.platforms.feishu.enabled: true`.

### 4. Register gateway startup (cross-platform)

**Windows**:
```bash
hermes -p <profile> gateway install --start-on-login --no-start-now
```
The launcher bakes in `HERMES_HOME=<profile home>` AND `--profile <name>`.
The default profile needs explicit registration without `--profile`.
UAC elevation may auto-fallback to a Startup-folder `.vbs`; that still auto-starts on login.

**Linux/macOS**:
Configure a systemd user service, launchd plist, or your init system of choice to run:
```bash
hermes -p <profile> gateway start
```
Ensure `HERMES_HOME` is set to the profile home directory.

**Completion criterion**: Gateway starts automatically on login/reboot; platform-specific process list shows the gateway PID.

### 5. Start gateway

```bash
hermes -p <profile> gateway start
```

**Completion criterion**: Profile log shows `✓ feishu connected` and `[Feishu] Received raw message` on test DM.

### 6. Set home channel

In the Feishu chat (DM works reliably; group requires @-bot), send `/sethome`.

**Completion criterion**: Profile `.env` contains `FEISHU_HOME_CHANNEL=<chat_id>`.

## connected-but-silent diagnosis

When a bot shows `✓ feishu connected` but never receives messages, follow this fixed order.

**Step 0 — Check Feishu 运营监控 → 日志检索 FIRST.**

Search the test-message time window; read the `receive_v1` **Status** column.

| Feishu `receive_v1` status | Hermes `Received raw message`? | Meaning / fix |
|---------------------------|--------------------------------|---------------|
| SUCCESS | ABSENT | Feishu pushed, Hermes dropped it. Cause: (a) `receive_v1` not under 应用身份, or (b) keys blank. |
| FAIL (4ms typical) | ABSENT | Bad/mismatched `FEISHU_ENCRYPT_KEY` or `FEISHU_VERIFICATION_TOKEN`. |
| No row at all | ABSENT | Feishu never generated the event. Re-publish the app version. |

**Step 1 — Fix subscription and keys.**
- (a) `im.message.receive_v1` subscribed under 应用身份.
- (b) `FEISHU_VERIFICATION_TOKEN` in `.env`.
- (c) `FEISHU_ENCRYPT_KEY` in `.env` **only if** 加密策略 page shows a key.

**Step 2 — RESTART.** Feishu long-connection does NOT hot-load new events or keys.

Decisive log line: `[Feishu] Received raw message type=... message_id=...`.

**Step 3 — If DM works but group fails**, see `references/feishu-events.md`.

## Pitfalls

1. **Don't force the multiplexer model.** If separate bots per profile, use independent gateway processes with separate `HERMES_HOME`.
2. **All profiles failing with same provider error** means upstream, not Feishu. Check `logs/errors.log` for 402/503/429.
3. **Group messages require @-bot.** A bare `/sethome` in a group may be ignored.
4. **Windows gateway processes are `pythonw.exe`.** `tasklist | find "pythonw"` to verify.
5. **`gateway install` UAC fallback.** Non-interactive shells auto-fallback to Startup-folder `.vbs`.
6. **`.env` is read-blocked but terminal-writable.** Never use the file tool.
7. **Check the RIGHT log.** Each profile writes its own `<profile>/logs/`.
8. **`FEISHU_VERIFICATION_TOKEN` is required; `FEISHU_ENCRYPT_KEY` is conditional.** Encryption off + key filled = 4ms FAIL.
9. **Feishu console changes need RE-PUBLISH.** Adding events/granting permissions are draft changes.
10. **DEFAULT profile has NO autostart.** Needs explicit `gateway install --start-on-login` without `--profile`.

## Verification checklist

- [ ] `tasklist | find "pythonw"` (Windows) or systemd/launchd status shows one gateway process per profile.
- [ ] Each `<profile>/logs/` shows `connected` and `✓ feishu connected`.
- [ ] `/sethome` in each chat writes a DISTINCT `FEISHU_HOME_CHANNEL`.
- [ ] Sending a DM produces an `Inbound ... message received` line in THAT profile's log.
- [ ] A test cron in profile A delivers to channel A, not channel B.

## References

- `references/feishu-events.md` — event codes, permissions, group-vs-DM diagnosis.
- `references/feishu-diagnosis.md` — per-profile setup recipes: strip cloned creds, locate logs, add missing `gateway:` section, bypass expiring pairing codes, and the `Received raw message` log anatomy.
