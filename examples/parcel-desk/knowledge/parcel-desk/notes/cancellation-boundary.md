---
id: "cancellation-boundary"
title: "Only requested pickups are currently cancellable"
type: "note"
status: "current"
areas: ["pickups"]
sources: ["src/pickups.py", "tests/test_pickups.py"]
tags: ["knowledge", "workflow"]
summary: "A customer can cancel a pickup only while it is still requested. Once it is packed or picked up, the cancellation is refused and nothing changes."
updated: "2026-11-14"
---

# Only requested pickups are currently cancellable

Area: [[areas/pickups|Pickup cancellation]]. Use this note when changing allowed states or explaining a rejected cancellation.

`cancel_pickup` first runs the [[notes/ownership-check|ownership check]]. It then requires `pickup.state == "requested"`; any other value, including `picked_up` and `packed`, raises `ValueError("Only requested pickups can be cancelled")` before anything is changed. A pickup that passes both checks gets state `cancelled` and is returned. The [service](../../../src/pickups.py) establishes this; the code has no list of states and treats every value except `requested` the same way. The service refers to no other state name.

The [[notes/route-responses|adapter]] turns the `ValueError` into status 409. The existing [tests](../../../tests/test_pickups.py) cover a `requested` pickup (cancelled) and a `picked_up` pickup (409, unchanged); none uses `packed`. The three-test suite passed during the example check (`python3 -m unittest discover -s tests -v`).
