# Cancellation audit — worked example

Scope: CAN-1–CAN-3 and DEC-1 in [SPEC.md](../SPEC.md). Basis: shipped fictional source; no deployed environment. This report is a hand-authored example of the expected evidence format.

## A-01 · Packed cancellation diverges from CAN-1

**Kind:** product gap / specification conflict. **Priority:** high within this scope. **Confidence:** high from source; runtime reproduction NOT RUN in this worked report.

CAN-1 includes `packed`. [cancel_pickup](../src/pickups.py) permits only `requested`. [cancel_request](../src/routes.py) translates the resulting `ValueError` to a 409 response. A customer following the accepted requirement would be rejected after packing.

Next action: reconcile the accepted requirement and the service condition with the owner. If CAN-1 remains the target, implement the focused state change with positive packed, negative collected and ownership checks. The existing test suite does not contain a packed case.

## A-02 · Ownership and collected-state boundaries align in source

CAN-2 and CAN-3 agree with the service branches. [The tests](../tests/test_pickups.py) describe both boundaries. Reading these tests is not a fresh PASS. This is aligned source behavior, not a finding that requires a feature task.

## A-03 · Partner behavior remains a decision

**Kind:** product plan. **Priority:** defer pending DEC-1. The specification explicitly leaves partner identity and permission rules undecided. Their absence is not a failure of CAN-1–CAN-3.

## Coverage

Reviewed: specification, route adapter, cancellation service, three listed tests. Not present in this fixture: real authentication, persistence, HTTP deployment and concurrent requests. These cannot be certified by this audit.
