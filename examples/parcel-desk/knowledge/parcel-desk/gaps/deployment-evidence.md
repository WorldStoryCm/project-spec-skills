---
id: "deployment-evidence"
title: "The example cannot establish deployed behavior"
type: "gap"
status: "unverified"
areas: ["access", "pickups"]
sources: ["SPEC.md", "src/routes.py"]
tags: ["verification-gap"]
updated: "2026-11-14"
---

# The example cannot establish deployed behavior

Areas: [[areas/access|Customer access]] and [[areas/pickups|Pickup cancellation]]. **Kind: verification gap; intentionally outside the example.**

The [spec boundary](../../../SPEC.md) and [adapter module](../../../src/routes.py) identify an in-memory fixture without an HTTP server, identity provider or database. This map cannot establish a deployed application's authentication, HTTP responses, persistence or concurrency.

No real deployment checks were run. The next action for an actual project would be to identify its real entrypoint and environment, then test a representative allowed and denied cancellation. For this example, leave the item open as a coverage boundary; do not build infrastructure just to make the graph green.

The [[notes/route-responses|status mapping]] is supported locally. [[notes/ownership-check|The owner check]] is distinct from authentication. [[01-coverage|Coverage]] records what the local tests actually establish.
