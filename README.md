# Hermes Feishu/Lark Gateway Setup Skill

A reusable [Hermes Agent](https://github.com/NousResearch/hermes-agent) skill that configures the
Hermes ↔ Feishu (Lark) messaging gateway — for a single bot **or** multiple isolated
profiles, each with its own Feishu app, its own gateway process, and its own cron-delivery
channel.

> Distilled from a real multi-day debugging session where a Feishu bot reported
> `✓ feishu connected` but never received a single user message. Every pitfall below
> is a failure mode that actually happened — the skill exists to stop you re-living them.

## What it covers

- Connecting a Feishu/Lark bot to Hermes (the `Feishu / Lark encrypt key`, `Verification token`,
  `Home channel ID` config form).
- **Per-profile isolation**: one independent Feishu app + gateway process per Hermes profile,
  so multiple "employees"/tenants stay physically separated (`FEISHU_HOME_CHANNEL` and
  `FEISHU_APP_ID` are per-`HERMES_HOME`).
- `/sethome` home-channel setup for cron / notification delivery.
- Windows startup registration (incl. the UAC → Startup-folder fallback).
- The Feishu event-subscription traps that silently block inbound messages:
  - `im.message.receive_v1` must be subscribed (not just `机器人进群`).
  - `FEISHU_VERIFICATION_TOKEN` is required; `FEISHU_ENCRYPT_KEY` is required **only** if the
    app's 加密策略 page shows a key (filling it when encryption is off → 4ms FAIL).
  - Feishu long-connection does **not** hot-load console changes — you must re-publish the
    app version **and** restart the gateway.
  - Pairing codes expire in ~1–2 min; clone-created profiles carry the source's Feishu creds;
    the default profile has no autostart; the gateway log file name varies per profile.

## Install (into Hermes)

```bash
# From the Hermes skills hub (if published):
hermes skills install hermes-feishu-setup

# Or manually — drop the folder into your skills dir:
#   ~/.hermes/skills/hermes-feishu-setup/   (or $HERMES_HOME/skills/...)
# then reload:
hermes reload-skills
```

## Usage

Invoke the skill in a Hermes session, or just describe the task:
"connect a Feishu bot to my `analyst` profile and make its cron post to a dedicated group",
"my Feishu bot says connected but never replies — fix it".

The skill walks through: Feishu Open Platform setup → credentials in the profile `.env` →
`config.yaml` enablement → gateway start/install → `/sethome`.

## Layout

```
hermes-feishu-setup/
├── SKILL.md                       # steps + 17 field-tested pitfalls
├── references/
│   ├── feishu-events.md           # event codes, permissions, "connected-but-silent" diagnosis table
│   └── feishu-diagnosis.md        # re-runnable per-profile fix recipes
├── LICENSE                        # MIT
├── CONTRIBUTING.md
└── README.md
```

## License

MIT — see [LICENSE](LICENSE).
