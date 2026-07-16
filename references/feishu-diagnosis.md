# Feishu Multi-Profile Diagnosis Recipes

Condensed, re-runnable procedures for the per-profile gotchas in the
parent SKILL.md (Pitfalls #14–#16, #11–#13). Use these instead of
re-deriving each time.

## 1. Strip cloned Feishu creds before configuring a new profile

A cloned profile ships with the SOURCE's `FEISHU_*` lines. Replace them
with the new app's values (encrypt key left blank unless the app has a
加密策略 key — Pitfall #8b).

```bash
python - "$HERMES_HOME/profiles/<new>/.env" <<'PY'
import sys, re
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
for k in ("FEISHU_APP_ID","FEISHU_APP_SECRET","FEISHU_VERIFICATION_TOKEN",
          "FEISHU_ENCRYPT_KEY","FEISHU_HOME_CHANNEL","FEISHU_HOME_CHANNEL_THREAD_ID"):
    s = re.sub(rf'(?m)^{k}=.*\n', '', s)
# append new app's four values here, then:
open(p,"w",encoding="utf-8").write(s)
PY
```
Verify no source `FEISHU_APP_ID` lingers:
`grep -nE "^FEISHU_APP_ID=" "$HERMES_HOME/profiles/<new>/.env"`

## 2. Locate the real gateway log (filename varies per profile)

`logs/gateway.log` is NOT guaranteed. If it's missing, list the dir and
grep the actual files:

```bash
ls "$HERMES_HOME/profiles/<new>/logs/"
grep -rIlE "connected|Received raw message" "$HERMES_HOME/profiles/<new>/logs/"
```

Real WS-connected line (even when log is named `gateway-stdio.log`):
`[Lark] connected to wss://msg-frontier.feishu.cn/ws/v2?...`

`gateway-exit-diag.log` may show non-zero exits from a PREVIOUS restart's
old PID — ignore if a current `pythonw` PID is alive and WS shows
connected. Confirm alive PIDs: `tasklist | find "pythonw"`.

## 3. Add a missing `gateway:` section to config.yaml

Cloned profiles often have NO `gateway:` block (file may end at
`image_gen:`). A python/heredoc append that searches for `gateway:` can
mis-detect (`use_gateway: true` contains the substring) and write
nothing. Use a deterministic file-tool patch anchored on the last line:

```yaml
image_gen:
  use_gateway: true

gateway:
  platforms:
    feishu:
      enabled: true
```

Verify: `grep -nE "gateway:|feishu:|enabled" "$HERMES_HOME/profiles/<new>/config.yaml"`

## 4. Bypass an expiring pairing code

Feishu pairing codes live ~1–2 min; screenshot-then-approve usually
expires. Prefer: user pastes bare code text →
`hermes -p <new> pairing approve feishu <CODE>` immediately.

If codes keep expiring, write the open_id directly:

```bash
# Get the correct ou_ id from THIS profile's feishu-pending.json
python - "$HERMES_HOME/profiles/<new>/platforms/pairing/feishu-pending.json" <<'PY'
import sys, json, time, os
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
uid = next(iter(d.values()))["user_id"]   # first pending user_id
out = os.path.join(os.path.dirname(p), "feishu-approved.json")
data = {uid: {"user_name": "", "approved_at": time.time()}}
json.dump(data, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("approved", uid)
PY
hermes -p <new> gateway restart
```
⚠️ Use THIS profile's own `ou_*` id — never copy an id from another
profile (each Feishu app mints a different open_id for the same human,
Pitfall #13).

## 5. Isolation proof (after all profiles up)

Each profile's `FEISHU_HOME_CHANNEL` (set via DM `/sethome`, since group
delivery is unreliable — Pitfall #10) must be DISTINCT:

```bash
for f in "$HERMES_HOME"/profiles/*/.env; do
  echo "$f:"; grep -E "^FEISHU_HOME_CHANNEL=" "$f" | sed 's/=.*/=<set>/'
done
```

## 6. Default profile has NO autostart — register it explicitly

Per-profile `gateway install --start-on-login` creates Startup `.vbs`
items for coder/trder/etc., but the DEFAULT gateway is NOT auto-registered
by those commands. After a reboot the default silently dies ("feishu no
response", no `gateway.pid`, no log activity) because the process was never
started. Register it separately, with NO `--profile` flag:

```bash
hermes gateway install --start-on-login --no-start-now
# → creates Hermes_Gateway.vbs (no _<profile> suffix) in Startup folder
```

Verify all employees self-heal after a reboot:

```bash
ls "$APPDATA/Microsoft/Windows/Start Menu/Programs/Startup/" | grep -i hermes
tasklist | find "pythonw"   # one PID per employee
```

On ANY "no response" report, STEP 0 is `tasklist | find "pythonw"` —
a missing PID means "start it" (`hermes gateway start`), not "debug the
config".
