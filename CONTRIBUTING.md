# Contributing

Thanks for helping improve this skill!

## How skills work

This is a [Hermes Agent](https://github.com/NousResearch/hermes-agent) skill. It loads into the
agent's context when relevant, and is meant to be **self-contained and copy-paste runnable**.

## Guidelines

- **Keep pitfalls real.** Every entry in `SKILL.md` (Pitfalls #1–#17) should be a failure mode
  that actually happened, with the exact symptom → log artifact → fix. Don't add theoretical
  advice.
- **No secrets.** Never commit real App IDs, secrets, open_ids, chat_ids, or tokens. Use
  placeholder forms like `cli_xxxxxxxx`, `oc_xxxxxxxx`, `ou_xxxxxxxx`.
- **Stay generic.** Avoid tying examples to one person's profiles. Use neutral names
  (`analyst`, `coder`, `tenant A/B`).
- **Keep the references in sync.** If you change a diagnosis flow in `SKILL.md`, update
  `references/feishu-events.md` / `references/feishu-diagnosis.md` to match.
- **Frontmatter must stay valid** (name/description/version/platforms) so Hermes' skill loader
  accepts it.

## Submitting

1. Fork and create a branch.
2. Make your change; bump the `version` in `SKILL.md` frontmatter (semver).
3. Open a PR with a short note on what failure mode you fixed or added.

## Local testing

Drop the folder into your Hermes skills dir and reload:

```bash
cp -r hermes-feishu-setup ~/.hermes/skills/
hermes reload-skills
# then in a session: /skill hermes-feishu-setup
```
