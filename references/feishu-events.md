# Feishu Events, Permissions & Connected-but-silent Reference

## Required events

| Event (CN) | Code | Why needed |
|------------|------|------------|
| 接收消息 v2.0 | `im.message.receive_v1` | Pushes user messages to the bot. Without this, nothing the user types arrives. |
| 机器人进群 v2.0 | `im.chat.member.bot.added_v1` | Bot-added-to-chat event (proves WS tunnel works, but does **not** prove messaging works). |

`im.message.receive_v1` must be subscribed under **应用身份** (application identity). The `用户身份订阅` tab does **not** contain a message-receive event — do not send the user looking there.

> The bot-added event alone is insufficient. `Bot added to chat` in the gateway log does **not** prove messages flow; `im.message.receive_v1` is the actual gating event.

## Permissions (应用身份)

- `im:message` — get & send single/group messages (minimum)
- `im:chat`, `im:chat:readonly` — group info if needed

Permissions and event subscriptions are independent. `im:message` enabled + `im.message.receive_v1` not subscribed = zero inbound messages.

## Connected-but-silent interpretation table

Read Feishu Open Platform → **运营监控 → 日志检索** first. Search the test-message time window; read the `receive_v1` **Status** column.

| Feishu `receive_v1` status | Hermes `Received raw message`? | Meaning / fix |
|----------------------------|--------------------------------|---------------|
| SUCCESS | ABSENT | Feishu pushed, Hermes dropped it. Cause: (a) `receive_v1` not under 应用身份, or (b) `FEISHU_VERIFICATION_TOKEN` / `FEISHU_ENCRYPT_KEY` blank (decrypt/verify fails silently before the log line). |
| FAIL (4ms typical) | ABSENT | Feishu pushed, Hermes rejected almost instantly. Almost always a bad/mismatched `FEISHU_ENCRYPT_KEY` or `FEISHU_VERIFICATION_TOKEN`, or `ENCRYPT_KEY` set while Feishu side sends plaintext (encryption disabled in console). |
| no `receive_v1` row at all | ABSENT | Feishu never generated the event → event/permission not truly live. Verify the event is added **and** the app version was re-published (版本管理与发布). |

## 4ms FAIL = over-encryption, not under

When 日志检索 shows `receive_v1` = FAIL in ~4ms (not absent, not a slow timeout), the signature is: `FEISHU_ENCRYPT_KEY` is set in `.env` while the app's 加密策略 is disabled. Feishu sends plaintext → adapter tries to decrypt → fails fast.

Fix: **remove** `FEISHU_ENCRYPT_KEY` (leave blank) unless 加密策略 actually shows a key. The inverse failure mode (blank + app encrypts) shows as SUCCESS-but-no-`Received raw message`.

## DM works, group does not

`Inbound dm message received` proves the DM path is fine. A group `chat_id` may still never appear. Blockers: bot not actually in the group; message not @-bot; group @-message sub-permission (`获取群组中用户@机器人消息`) missing from published version. Validate separately; if group keeps failing, fall back to DM `/sethome`.

## What a healthy inbound looks like

```
[Feishu] Inbound dm message received: id=om_xxx type=text
         chat_id=oc_xxx sender=user:ou_xxx text='/sethome' ...
[Feishu] Sending response (...) to oc_xxx
```

Success writes `FEISHU_HOME_CHANNEL=oc_xxx` into the current profile's `.env`.
