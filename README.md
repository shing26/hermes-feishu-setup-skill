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

## When to use it

Use this skill when you want to:

- connect a Feishu/Lark bot to Hermes
- configure `/sethome`, home channel, or where cron results get delivered
- run multiple Hermes profiles with their own Feishu bot, app, and channel
- make the gateway survive reboots / start automatically on Windows
- debug "bot connected but no messages arrive" on Feishu

## Quick install

```bash
hermes skills install hermes-feishu-setup
hermes reload-skills
```

Or manually copy this repo into your skills directory and reload skills.

## Usage

Invoke the skill in a Hermes session, or just describe the task:

- "connect a Feishu bot to my `analyst` profile and make its cron post to a dedicated group"
- "my Feishu bot says connected but never replies — fix it"

The skill walks through: Feishu Open Platform setup → credentials in the profile `.env` →
`config.yaml` enablement → gateway start/install → `/sethome`.

## Layout

```
hermes-feishu-setup/
├── SKILL.md                       # steps + pitfalls + verification checklist
├── references/
│   ├── feishu-events.md           # event codes, permissions, connected-but-silent diagnosis
│   └── feishu-diagnosis.md        # re-runnable per-profile fix recipes
├── LICENSE                        # MIT
├── CONTRIBUTING.md
└── README.md
```

## Key concepts

- **Hermes profile**: an isolated Hermes config/cron/identity context.
- **Feishu app**: an enterprise self-built app on the Feishu Open Platform.
- **Home channel**: the Feishu chat where a profile's cron/notification output is delivered.
- **Long connection**: the Feishu event WebSocket mode; draft changes only take effect after
  re-publishing the app version.

## Common pitfalls

- `im.message.receive_v1` must be subscribed under **应用身份**.
- `FEISHU_VERIFICATION_TOKEN` is required; `FEISHU_ENCRYPT_KEY` is required **only** if the
  app's **加密策略** page shows a key.
- Feishu long-connection does **not** hot-load console changes — you must re-publish the app
  version **and** restart the gateway.
- Pairing codes expire in about 1–2 minutes.
- Each Feishu app issues a different `open_id` for the same user.

For a fuller pitfall list and runnable fixes, see [SKILL.md](SKILL.md) and
[`references/feishu-diagnosis.md`](references/feishu-diagnosis.md).

## License

MIT — see [LICENSE](LICENSE).
