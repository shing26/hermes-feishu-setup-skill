# Feishu Multi-Profile Diagnosis Recipes

## 1. Strip cloned Feishu creds

`hermes profile create <new> --clone-from <src>` copies `<src>/.env` wholesale. Remove the source's `FEISHU_*` lines before enabling the new app.

```bash
python - "$HERMES_HOME/profiles/<new>/.env" <<'PY'
import sys, re
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
for k in ("FEISHU_APP_ID","FEISHU_APP_SECRET","FEISHU_VERIFICATION_TOKEN",
          "FEISHU_ENCRYPT_KEY","FEISHU_HOME_CHANNEL","FEISHU_HOME_CHANNEL_THREAD_ID"):
    s = re.sub(rf'(?m)^{k}=.*\n', '', s)
open(p,"w",encoding="utf-8").write(s)
PY
```

Verify: `grep -nE "^FEISHU_APP_ID=" "$HERMES_HOME/profiles/<new>/.env"` should return nothing. Then append the new app's values (encrypt key blank unless 加密策略 shows one).

## 2. Locate the real gateway log

`logs/gateway.log` is not guaranteed. If missing, list the directory and grep the real files:

```bash
ls "$HERMES_HOME/profiles/<profile>/logs/"
grep -rIlE "connected|Received raw message" "$HERMES_HOME/profiles/<profile>/logs/"
```

Decisive WS-up line: `[Lark] connected to wss://msg-frontier.feishu.cn/ws/v2?...`

`gateway-exit-diag.log` may show non-zero exits from a **previous** restart's old PID. Ignore if a current `pythonw` PID is alive. Confirm: `tasklist | find "pythonw"`.

## 3. Add a missing `gateway:` section to `config.yaml`

Cloned profiles often have no `gateway:` block. Use a deterministic file-tool patch anchored on the file's last line:

```yaml
image_gen:
  use_gateway: true

gateway:
  platforms:
    feishu:
      enabled: true
```

Verify: `grep -nE "gateway:|feishu:|enabled" "$HERMES_HOME/profiles/<profile>/config.yaml"`.

## 4. Bypass expiring pairing codes

Pairing codes live ~1–2 minutes. Prefer: user pastes bare code text → `hermes -p <profile> pairing approve feishu <CODE>` immediately.

If codes keep expiring, write the open_id directly:

```bash
python - "$HERMES_HOME/profiles/<profile>/platforms/pairing/feishu-pending.json" <<'PY'
import sys, json, time, os
p = sys.argv[1]
out = os.path.join(os.path.dirname(p), "feishu-approved.json")
with open(p, encoding="utf-8") as f:
    d = json.load(f)
uid = next(iter(d.values()))["user_id"]
data = {uid: {"user_name": "", "approved_at": time.time()}}
with open(out, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print("approved", uid)
PY
hermes -p <profile> gateway restart
```

Use THIS profile's own `ou_*` id. Each Feishu app mints a different open_id for the same human.

## 5. Isolation proof

Each profile's `FEISHU_HOME_CHANNEL` must be distinct:

```bash
for f in "$HERMES_HOME"/profiles/*/.env; do
  echo "$f:"
  grep -E "^FEISHU_HOME_CHANNEL=" "$f" | sed 's/=.*/=<set>/'
done
```
