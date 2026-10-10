---
name: Telegram URL-task verification
description: Telegram Bot API behavior and the chosen timing-gate approach for tasks opened through URL buttons.
---

Telegram does not send a bot update when a user taps an inline keyboard URL button. A bot cannot reliably know whether an external task link was actually opened.

**Why:** Task rewards need a 10-second delay before verification, but the external URL tap itself is not observable through the Bot API.

**How to apply:** Start the timer on an explicit callback button such as “Start task,” then present the URL and allow verification after 10 seconds. Describe this as a minimum wait, not proof that the external action was completed.
