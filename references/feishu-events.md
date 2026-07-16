# Feishu / Lark — Events, Permissions & "Connected but silent" Diagnosis

Condensed from a live debugging session (Hermes Feishu gateway, two isolated
profiles). Goal: get inbound group/DM messages into Hermes.

## Event subscription (飞书开放平台 → 事件配置)
Long-connection (长连接 / WebSocket) mode is used by Hermes — no public
domain or encrypt-key callback needed.

Required events (添加事件 → 应用身份订阅):
| Event (CN)        | Code                          | Why needed                         |
|-------------------|-------------------------------|-------------------------------------|
| 接收消息 v2.0     | `im.message.receive_v1`        | **Pushes user messages to the bot.** Without this, NOTHING the user types arrives. |
| 机器人进群 v2.0    | `im.chat.member.bot.added_v1`  | Bot-added-to-chat event (nice to have; proves the WS tunnel works). |

> The bot-added event ALONE is insufficient. If you only see
> `Bot added to chat: oc_...` in the gateway log but no `Inbound message`,
> the `im.message.receive_v1` event is missing.

## Permissions (权限管理)
Grant at least (应用身份):
- `im:message` — 获取与发送单聊、群组消息 (get & send single/group messages)
- `im:chat`, `im:chat:readonly` etc. — group info (if the bot needs it)

Note: permissions and event subscriptions are **independent**. You can have
`im:message` enabled yet still receive zero messages because the
`im.message.receive_v1` EVENT was never subscribed.

## Diagnosis flow — "bot connected but no reply"
**STEP 0 (do this FIRST — it ends the guessing):** open Feishu Open
Platform → your app → **运营监控 → 日志检索** and search the
time window you sent the test message. For each `im.message.receive_v1`
row, read its **Status** column. This is the single most decisive
artifact — it tells you, in one screen, whether Feishu pushed the
event at all. Spend your first diagnostic turn here, NOT on key/identity
guessing. (A full "connected but silent" session was wasted by
guessing at encrypt_key / subscription identity for many turns before
this log was checked — the log resolved it in one screenshot.)

Interpretation table (Feishu Log Search status × Hermes gateway.log):
| Feishu `receive_v1` status | Hermes `Received raw message`? | Meaning / fix |
|---|---|---|
| SUCCESS | ABSENT | Feishu pushed, Hermes dropped it. Cause is Hermes-side: (a) `im.message.receive_v1` not actually subscribed in 应用身份 (see events table), or (b) `FEISHU_VERIFICATION_TOKEN`/`FEISHU_ENCRYPT_KEY` blank → payload fails decrypt/verify and is dropped BEFORE the `Received raw message` line (see Blocker A). Note: a `Bot added to chat` line in Hermes log does NOT prove messages flow — that event routes fine while receive_v1 is silently dropped. |
| FAIL (4ms typical) | ABSENT | Feishu pushed, Hermes REJECTED fast. Almost always a bad/mismatched `FEISHU_ENCRYPT_KEY` or `FEISHU_VERIFICATION_TOKEN` (or one set when Feishu side sends plaintext). Re-check the exact values from 凭证与基础信息 + 事件与回调→加密策略; fix and restart (Blocker B). |
| (no `receive_v1` row at all) | ABSENT | Feishu never generated the event → subscription/permission not truly live on Feishu side. Verify the event is added AND the app version was re-published (版本管理与发布) after the change — Feishu long-connection often serves the PRE-publish subscription set. |

1. Gateway log shows `✓ feishu connected` → WebSocket tunnel is UP.
   (Connection success does NOT imply message delivery.)
2. `grep -i "Received raw message" <profile>/logs/gateway.log`:
   - This line logs ONLY after a payload is decrypted + handed in.
     Its ABSENCE (with `feishu connected`) is the Hermes-side signature —
     it is NOT a mention/allowlist problem (those fire later).
   - `Bot added to chat: oc_...` present but no `Received raw message` →
     receive event missing OR keys blank (Blockers A/#2a).
3. In a GROUP, messages are pushed only when the bot is **@-mentioned**.
   Send `@<BotName> /sethome`, not bare `/sethome`.
4. After console changes (event added, keys filled, version republished),
   Feishu long-connection does NOT hot-load them — **restart the gateway**
   (`hermes -p <profile> gateway restart`). A process up since before the
   change stays silent until restarted (Blocker B).

## TWO MORE SILENT BLOCKERS (from a full "connected-but-silent" session)

### Blocker A — missing `FEISHU_VERIFICATION_TOKEN` / `FEISHU_ENCRYPT_KEY`
These are the config FORM's first two fields (encrypt key / verification
token). Without them the WebSocket STILL connects, but every inbound
message is **silently dropped at the decrypt/verify layer** — before the
`Received raw message` log line, so even that never appears.
- `FEISHU_VERIFICATION_TOKEN` → console 凭证与基础信息 → Verification Token
- `FEISHU_ENCRYPT_KEY` → console 事件与回调 → 加密策略 (Encrypt Key)
- Both must be filled in the PROFILE's `.env` (plain KEY=value, no quotes).
- Symptom that points here: `feishu connected` + `Bot added to chat`
  present, but **zero** `Received raw message` lines even after the
  receive event is subscribed. Fix: fill both keys, then RESTART.

### Blocker B — MUST restart the gateway after console changes
Feishu long-connection (WebSocket) mode does **NOT hot-load** newly
subscribed events or changed keys. If you add `im.message.receive_v1`
or fill the encrypt/verify keys in the console while the gateway is
running, the established connection keeps the OLD subscription —
Feishu never pushes message events to it. A process that's been up
since BEFORE the console change will stay silent until you restart:
```bash
hermes -p <profile> gateway restart
```
This was the root cause of a whole session of "connected but
/sethome never responds": event added + keys filled, yet the process
predated those changes. Restarting made messages flow.

## Platform identity tabs (应用身份 vs 用户身份)
When adding the receive event, the modal shows tabs:
`应用身份订阅(N)` / `用户身份订阅(N)`.
Add `im.message.receive_v1` under **应用身份** for the standard bot flow.
If the bot is meant to act on behalf of a user, the user-identity
subscription may also be needed — but the default Hermes bot path is
应用身份.

⚠️ **`用户身份订阅` has NO message event option.** Confirmed live:
the 用户身份 tab's service menu lists only 云文档/日历/视频会议/任务/邮箱
etc. — there is NO "messages" category there, so `接收消息` is
simply absent from that tab. Do NOT send the user to look for
`im.message.receive_v1` under 用户身份 — it is not there and checking
it wastes a round-trip. Message receive lives ONLY under 应用身份.

## Version re-publish (版本管理与发布) — often REQUIRED
Adding the `im.message.receive_v1` event (and granting permissions)
does NOT take effect on the live long-connection until the app is
**re-published**. Confirmed diagnostic: Feishu's 日志检索 may show
`receive_v1` = SUCCESS (it "sends") while Hermes still logs nothing —
because the long-connection is serving the PRE-publish subscription set.
After any event/permission change in the console: go to
**版本管理与发布 → 创建版本并发布**, THEN `hermes -p <profile> gateway restart`.
If 日志检索 shows NO `receive_v1` row at all for your test time, the
change likely wasn't published (or wasn't saved).


## Two more nuances (from the same session)

### `4ms FAIL` can mean OVER-encryption, not under
If 日志检索 shows `receive_v1` = **FAIL in ~4ms** (not absent, not a
slow timeout), Feishu pushed but Hermes rejected almost instantly. This
is the signature of `FEISHU_ENCRYPT_KEY` being set in `.env` while the
Feishu app's **加密策略 is disabled** — Feishu sends plaintext, the
adapter tries to decrypt it, and fails fast. Fix: **remove**
`FEISHU_ENCRYPT_KEY` (leave it blank) unless the console's 加密策略
page actually shows a key. The inverse (key blank + app encrypts) shows
as SUCCESS-but-no-`Received-raw-message` instead. So the two failure
modes are mirror images — one is fixed by adding the key, the other by
removing it. Trust the 日志检索 Status column over guesswork.

### DM-working ≠ group-working
`Inbound dm message received` in the log proves the profile's DM path is
fine, but a GROUP `chat_id` may still never appear even when 日志检索
`receive_v1` is SUCCESS. Group push is blocked independently at the
Feishu side: bot not actually in the group, message not @-bot, or the
group @-message sub-permission (`获取群组中用户@机器人消息`) missing
from the published version. Validate group separately (send
`@bot /sethome` in the group, watch for a group `chat_id`). If group
keeps failing, fall back to DM `/sethome` — the home channel still gets
set, just from a DM instead of the group.

## Verification (what a healthy inbound line looks like)
```
[Feishu] Inbound dm message received: id=om_xxx type=text
         chat_id=oc_xxx sender=user:ou_xxx text='/sethome' ...
[Feishu] Sending response (...) to oc_xxx
```
For /sethome specifically, success writes `FEISHU_HOME_CHANNEL=oc_xxx`
into the CURRENT profile's `.env` (isolated per HERMES_HOME).
