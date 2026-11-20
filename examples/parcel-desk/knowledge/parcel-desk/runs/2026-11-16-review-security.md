---
id: "2026-11-16-review-security"
title: "Security review of the fixture"
type: "run"
status: "current"
review: "security"
areas: []
sources: []
tags: ["run"]
updated: "2026-11-16"
---

# Security review of the fixture

A review of one topic, security, over the whole fictional product: one feature with two entry points. This is an authored example of what such a run page holds, not a transcript of an independent agent run. The code was read; nothing was run.

## Features

- [x] Cancelling a pickup

## What the questions found

- Who can reach it: `cancel_request` takes a customer identity its caller has already authenticated, and the fixture has no sign-in of its own. `notes/ownership-check` already says so (BR-OWNER-03).
- Whose record it is: `cancel_pickup` compares the pickup's customer with the caller before anything else (BR-OWNER-01).
- What may be changed: only the state, and only to `cancelled`. No field is taken from the request.
- What comes back: a refusal to someone who is not the owner is the same 403 whatever the pickup's state, so it tells them nothing about it (BR-OWNER-02). That question was already asked and closed in `gaps/state-leak`.
- A repeated request: the second cancellation is refused with 409, because the pickup is no longer `requested`.

No rule was added and no gap was written.

## Not covered

The fixture has no dependencies, files, secrets, sign-in, jobs or outgoing messages, so the questions about them had nothing to ask. A real product would name here the tools for what reading does not find, such as a dependency audit and a secret scanner.
