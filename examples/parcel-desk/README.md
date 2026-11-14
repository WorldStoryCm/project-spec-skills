# Parcel Desk: a fictional worked example

The spec, Python source, tests and customer IDs are invented for this repository. The source deliberately disagrees with one accepted requirement, so an audit has something concrete to find.

Open `knowledge/parcel-desk/graph.html` in a browser or `knowledge/parcel-desk` as an Obsidian vault. The Markdown claims cite the files alongside this README. The graph can be opened offline; source links outside the vault may need your editor.

## Follow the example

1. Read [the requirements](SPEC.md) and inspect [the route](src/routes.py) and [the service](src/pickups.py).
2. Browse [the knowledge index](knowledge/parcel-desk/00-index.md).
3. Compare the example [audit](reports/audit.md), [investigation](reports/investigation.md) and [plan](reports/plan.md).

These reports are worked examples, not transcripts of an independent agent evaluation. They distinguish reading tests from running them. The release checks and fresh-agent evaluations are documented separately in the repository's validation record.

Run the fixture tests from this folder:

```sh
python3 -m unittest discover -s tests -v
```

They omit a packed-pickup test. A green suite therefore does not establish compliance with CAN-1.

## Rebuild the example graph

From the repository root:

```sh
python3 skills/project-knowledge/scripts/knowledge.py check \
  --repo examples/parcel-desk --vault examples/parcel-desk/knowledge/parcel-desk --strict
python3 skills/project-knowledge/scripts/knowledge.py build \
  --repo examples/parcel-desk --vault examples/parcel-desk/knowledge/parcel-desk
```

The included source hashes describe the shipped fixture. Changing a source produces a freshness warning; rebuilding alone does not accept it. After actually reviewing the new source and updating a note, accept only the affected note's fingerprints with `snapshot --notes <id>`.

This example has no baked-in Git review cursor. The enclosing toolkit is a different repository from the fictional application. To experiment with `sync`, copy this example to a disposable directory, initialize its own Git repository and let the skill research and initialize a real checkpoint. The [evaluation scenarios](../../docs/evaluation.md) describe this exercise.
