# Audit: cancellation requirements CAN-1 to CAN-3 and DEC-1

A hand-authored example of the report shape in the `spec-audit` skill, not a transcript of an agent run.

## Basis

Requirements: [SPEC.md](../SPEC.md). Implementation: [src/pickups.py](../src/pickups.py), [src/routes.py](../src/routes.py) and [tests/test_pickups.py](../tests/test_pickups.py), as shipped in this fictional fixture; no Git revision and no deployed environment. Inspected: all four files. Not inspected: authentication, persistence, HTTP deployment and concurrent requests, none of which exist here.

## Findings

### F-01 · Packed cancellation diverges from CAN-1

**Classification:** `product-gap`. **Priority:** high within this scope. **Confidence:** high from source; the 409 response was reproduced in a local in-process call during the gap recheck, not in a deployed service.

CAN-1 includes `packed`. [cancel_pickup](../src/pickups.py) permits only `requested`, and [cancel_request](../src/routes.py) turns the resulting `ValueError` into a 409. A customer following the accepted requirement is rejected once the parcel is packed. The existing tests contain no packed case.

Next action: a person decides whether to keep CAN-1 (change the service) or revise it. In the vault this is the gap [packed-cancellation](../knowledge/parcel-desk/gaps/packed-cancellation.md), recorded as accepted with [a plan](../knowledge/parcel-desk/plans/packed-cancellation.md).

### F-02 · Partner behavior is an open decision

**Classification:** `product-plan`. **Priority:** low until DEC-1 is decided. The requirements leave partner identity and permissions undecided, so the absence of a partner path is not a failure of CAN-1 to CAN-3. In the vault: [partner-decision](../knowledge/parcel-desk/gaps/partner-decision.md), rechecked and awaiting a decision.

### F-03 · Nothing shows deployed behavior

**Classification:** `verification-gap`. **Priority:** low. The fixture is in-memory; no check can speak for a real deployment. In the vault: [deployment-evidence](../knowledge/parcel-desk/gaps/deployment-evidence.md), not rechecked yet.

## Confirmed

| Requirement | Outcome | Evidence |
| --- | --- | --- |
| CAN-2 other customer cannot cancel | Implemented | Owner check in `cancel_pickup` raises `PermissionError`; adapter returns 403; `test_other_customer_cannot_cancel` asserts 403 and unchanged state (read, not rerun in this report). |
| CAN-3 picked-up pickup cannot be cancelled | Implemented | `cancel_pickup` rejects any state other than `requested`; `test_collected_pickup_cannot_be_cancelled` asserts 409 and unchanged state (read, not rerun). |

These two are not gaps, and the vault holds no gap page for them.

## Open decisions

DEC-1 partner cancellation: options are reject, defer, or accept and define permissions, identity checks and allowed states first.

## Limits and checks

No command was run for this report: the test run is **NOT RUN**. The audit pass would be recorded in the vault as a run page that lists the four requirements assessed and the gaps created (F-01 to F-03); here that role is played by [the example survey](../knowledge/parcel-desk/runs/example-survey.md).
