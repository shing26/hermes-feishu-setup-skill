# Hermes Feishu / Lark Gateway Setup Skill

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A reusable [Hermes Agent](https://github.com/NousResearch/hermes-agent) skill that configures the
Hermes ↔ Feishu (Lark) messaging gateway — for a single bot **or** multiple isolated
profiles, each with its own Feishu app, its own gateway process, and its own cron-delivery
channel.

## Why this exists

This skill was distilled from a real multi-day debugging session where a Feishu bot reported
`✓ feishu connected` but never received a single user message. Every pitfall below is a
failure mode that actually happened, and this skill encodes the proven fixes.

## What this skill covers

- Connect a Feishu/Lark bot to Hermes (configuring `Feishu / Lark encrypt key`,
  `Verification token`, `Home channel ID`, and event subscriptions).
- **Per-profile isolation**: one independent Feishu app + gateway process per Hermes profile,
  so multiple "employees"/tenants stay physically separated.
- `/sethome` home-channel setup for cron and notification delivery.
- Windows startup registration, including the UAC → Startup-folder fallback.
- The Feishu event-subscription traps that silently block inbound messages.
- Optional gateway guardian script for multi-profile monitoring and auto-repair.

## Prerequisites

- Hermes Agent installed and running on Windows, Linux, or macOS.
- A Feishu/Lark **enterprise account** with permission to create self-built apps on the
  [Feishu Open Platform](https://open.feishu.cn/).
- For multi-profile isolation: multiple Feishu apps (one per profile), each with its own
  `App ID` and `App Secret`.

## Quick start (5 minutes)

Follow these steps to go from "new Feishu app" to "receiving messages in Hermes".

### 1. Create and configure the Feishu app

On the Feishu Open Platform:

1. Create an **enterprise self-built app**.
2. Enable **bot** capability and choose **长连接 (WebSocket)** mode.
3. Add event `接收消息` (`im.message.receive_v1`) under **事件订阅 → 应用身份**.
4. Grant permission `im:message`.
5. **Re-publish** the app version.

Expected result: in **运营监控 → 日志检索**, a test message shows `receive_v1` with
`SUCCESS` status.

### 2. Write credentials to the profile `.env`

Append to `$HERMES_HOME/profiles/<profile>/.env`:

```bash
FEISHU_APP_ID=cli_xxxxxxxx
FEISHU_APP_SECRET=xxxxxxxx
FEISHU_VERIFICATION_TOKEN=xxxxxxxx   # REQUIRED
# FEISHU_ENCRYPT_KEY=xxxxxxxx        # ONLY if 加密策略 page shows a key
```

Verify: `grep -nE "^FEISHU_(APP_ID|APP_SECRET|VERIFICATION_TOKEN)=" <profile>/.env`

### 3. Enable feishu in `config.yaml`

```yaml
gateway:
  platforms:
    feishu:
      enabled: true
```

### 4. Start the gateway

```bash
hermes -p <profile> gateway start
```

Expected log output:

```
[Feishu] connected to wss://msg-frontier.feishu.cn/ws/v2?...
[Feishu] Received raw message type=text message_id=om_xxx ...
```

### 5. Set the home channel

In the Feishu chat (DM works reliably; group requires @-bot), send:

```
/sethome
```

Expected result: `FEISHU_HOME_CHANNEL=oc_xxx` appears in the profile's `.env`.

### 6. Register startup (optional)

**Windows**: `hermes -p <profile> gateway install --start-on-login --no-start-now`  
**Linux/macOS**: add a systemd user service or launchd plist that runs
`HERMES_HOME=<path> hermes -p <profile> gateway start`.

## Gateway guardian (optional)

For multi-profile setups, `scripts/guardian.py` monitors gateway health and restarts stale
or dead processes.

```bash
# All profiles
python scripts/guardian.py --all

# One-shot (for cron / Task Scheduler)
python scripts/guardian.py --all --once
```

See `SKILL.md` for environment variables and behavior details.

## Common pitfalls

- `im.message.receive_v1` must be subscribed under **应用身份**.
- `FEISHU_VERIFICATION_TOKEN` is required; `FEISHU_ENCRYPT_KEY` is required **only** if the
  app's **加密策略** page shows a key.
- Feishu long-connection does **not** hot-load console changes — you must re-publish the app
  version **and** restart the gateway.
- Each Feishu app issues a different `open_id` for the same user.

For a fuller pitfall list and runnable fixes, see [SKILL.md](SKILL.md) and
[`references/feishu-diagnosis.md`](references/feishu-diagnosis.md).

## What you should see when it works

A successful inbound DM looks like:

```
[Feishu] Inbound dm message received: id=om_xxx type=text
         chat_id=oc_xxx sender=user:ou_xxx text='/sethome' ...
[Feishu] Sending response (...) to oc_xxx
```

After `/sethome`, the profile's `.env` contains:

```
FEISHU_HOME_CHANNEL=oc_xxx
```

## Layout

```
hermes-feishu-setup/
├── SKILL.md                       # steps + pitfalls + verification checklist
├── references/
│   ├── feishu-events.md           # event codes, permissions, connected-but-silent diagnosis
│   └── feishu-diagnosis.md        # re-runnable per-profile fix recipes
├── scripts/
│   └── guardian.py                # optional multi-profile monitoring + auto-repair
├── CHANGELOG.md                   # version history
├── LICENSE                        # MIT
├── CONTRIBUTING.md
└── README.md
```

## Versioning

See [CHANGELOG.md](CHANGELOG.md) for release notes.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
