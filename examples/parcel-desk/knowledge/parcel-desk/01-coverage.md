---
id: "coverage"
title: "Coverage and evidence limits"
type: "index"
status: "partial"
areas: []
sources: []
tags: ["coverage"]
updated: "2026-11-14"
---

# Coverage and evidence limits

Return to [[00-index|the index]].

## Pickup coverage

In [[areas/pickups|Pickups]], the service, adapter, CAN-1/CAN-3 and all three tests were inspected. Three existing unit tests passed; they omit the packed success case. Real HTTP responses, concurrent writes and persistent state are outside the fixture.

## Access coverage

In [[areas/access|Access]], the owner guard, CAN-2, DEC-1 and denied-action test were inspected. The test verified that another customer's requested pickup is denied without mutation. Authentication, partner identities and deployed authorization are outside the fixture.

The release check ran `python3 -m unittest discover -s tests -v` from the fictional project: **PASS, 3 tests**. This does not prove CAN-1 is satisfied. Static inspection finds the packed mismatch recorded in [[gaps/packed-cancellation|the product gap]].

The source fingerprints describe this shipped fixture. There is no reviewed Git checkpoint embedded in the example because it is a subdirectory of the toolkit, not an independent application repository. Copy the fixture into a temporary Git project before trying incremental commit sync.

No real service, logs or customer data were inspected. The example does not imply those systems are missing from an actual product. [[gaps/deployment-evidence|Deployment evidence]] records that boundary.
