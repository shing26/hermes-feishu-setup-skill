# Feishu Events, Permissions & Connected-but-silent Reference

## Required events

| Event (CN) | Code | Why needed |
|------------|------|------------|
| 接收消息 v2.0 | `im.message.receive_v1` | Pushes user messages to the bot. Without this, nothing arrives. |
| 机器人进群 v2.0 | `im.chat.member.bot.added_v1` | Bot-added-to-chat event (proves WS tunnel works, but does **not** prove messaging works). |

`im.message.receive_v1` must be subscribed under **应用身份**. The `用户身份订阅` tab does **not** contain a message-receive event.

> The bot-added event alone is insufficient. `Bot added to chat` in the gateway log does **not** prove messages flow; `im.message.receive_v1` is the actual gating event.

## Permissions (应用身份)

- `im:message` — get & send single/group messages (minimum)
- `im:chat`, `im:chat:readonly` — group info if needed

Permissions and event subscriptions are independent. `im:message` enabled + `im.message.receive_v1` not subscribed = zero inbound messages.

## Connected-but-silent interpretation table

Read Feishu Open Platform → **运营监控 → 日志检索** first. Search the test-message time window; read the `receive_v1` **Status** column.

| Feishu `receive_v1` status | Hermes `Received raw message`? | Meaning / fix |
|----------------------------|--------------------------------|---------------|
| SUCCESS | ABSENT | Feishu pushed, Hermes dropped it. Cause: (a) `receive_v1` not under 应用身份, or (b) keys blank. |
| FAIL (4ms typical) | ABSENT | Bad/mismatched `FEISHU_ENCRYPT_KEY` or `FEISHU_VERIFICATION_TOKEN`. |
| No `receive_v1` row at all | ABSENT | Feishu never generated the event. Verify event added and app version re-published. |

## 4ms FAIL = over-encryption, not under

When 日志检索 shows `receive_v1` = FAIL in ~4ms, the signature is: `FEISHU_ENCRYPT_KEY` is set in `.env` while the app's 加密策略 is disabled.

Fix: **remove** `FEISHU_ENCRYPT_KEY` unless 加密策略 actually shows a key.

## DM works, group does not

`Inbound dm message received` proves the DM path is fine. Blockers: bot not in group; message not @-bot; group @-message sub-permission missing.

## Healthy inbound example

```
[Feishu] Inbound dm message received: id=om_xxx type=text
         chat_id=oc_xxx sender=user:ou_xxx text='/sethome' ...
[Feishu] Sending response (...) to oc_xxx
```

Success writes `FEISHU_HOME_CHANNEL=oc_xxx` into the current profile's `.env`.
