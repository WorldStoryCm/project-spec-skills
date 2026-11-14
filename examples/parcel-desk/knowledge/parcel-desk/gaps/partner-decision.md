---
id: "partner-decision"
title: "Partner cancellation needs a product decision"
type: "gap"
status: "planned"
areas: ["access", "pickups"]
sources: ["SPEC.md", "src/routes.py"]
tags: ["product-plan"]
updated: "2026-11-14"
---

# Partner cancellation needs a product decision

Areas: [[areas/access|Customer access]] and [[areas/pickups|Pickup cancellation]]. **Kind: product plan.**

DEC-1 in [the spec](../../../SPEC.md) explicitly leaves partner cancellation undecided and outside accepted scope. The [adapter](../../../src/routes.py) accepts a customer identity; it provides no separate partner contract.

Absence of that contract is not evidence of a missing accepted feature. Decide who may act on whose behalf, which identity evidence is required and which states are allowed before making an implementation task. Those choices gate partner work only.

[[gaps/packed-cancellation|The accepted customer requirement]] can be addressed independently. [[notes/ownership-check|Today's owner guard]] must remain intact until any replacement contract is explicitly accepted. No partner runtime checks were run because this fixture defines no partner behavior.
