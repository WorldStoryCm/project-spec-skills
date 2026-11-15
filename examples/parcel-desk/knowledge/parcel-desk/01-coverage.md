---
id: "coverage"
title: "Coverage and evidence limits"
type: "index"
status: "partial"
areas: []
sources: []
tags: ["coverage"]
updated: "2026-11-15"
---

# Coverage and evidence limits

Return to [[00-index|the index]].

## Pickup coverage

In [[areas/pickups|Pickups]], the service, adapter and all three tests were read. Three existing unit tests passed; none uses a `packed` pickup. Real HTTP responses, concurrent writes and persistent state are outside the fixture.

## Access coverage

In [[areas/access|Access]], the owner guard and the denied-action test were read. The test shows another customer's requested pickup is refused without a state change. Authentication, partner identities and deployed authorization are outside the fixture.

The release check ran `python3 -m unittest discover -s tests -v` from the fictional project: **PASS, 3 tests**. That result says nothing about packed pickups; the open question is [[gaps/packed-cancellation|packed cancellation]].

## Limits

The source fingerprints describe this shipped fixture. There is no reviewed Git checkpoint embedded in the example because it is a subdirectory of the toolkit, not an independent application repository. Copy the fixture into a temporary Git project before trying incremental commit sync.

No real service, logs or customer data were inspected. That does not imply those systems are missing from an actual product; [[gaps/deployment-evidence|deployment evidence]] records the boundary as a gap.
