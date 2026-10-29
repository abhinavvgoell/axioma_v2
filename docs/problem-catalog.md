# Axioma problem catalog

Axioma can match a pasted problem statement to a local test pack. Imported packs are kept in
`services/api/data/`, which is intentionally excluded from Git because it contains third-party
problem and test data.

## Import the 1,000-pack starter catalog

From the repository root, run:

```powershell
services/api/.venv/Scripts/python services/api/scripts/import_problem_catalog.py --limit 1000
```

The importer downloads the pinned `v0.3.1` training split from
[newfacade/LeetCodeDataset](https://github.com/newfacade/LeetCodeDataset), parses only its
`input_output` values with Python's literal parser, and writes a local JSON catalog. It never
executes dataset-provided code. The current import format supports `Solution` function entrypoints
whose test values can be represented as JSON. Problems requiring custom linked-list, tree, graph,
or judge-provided object types are skipped. It keeps up to 20 concrete cases per problem and needs
at least four. The local catalog also keeps each source problem description so Axioma can match
title-less prompts without calling an AI service. It extracts simple numeric bounds for scalar
parameters and collection lengths from the `Constraints` section, using the starter method's
argument order. A range is retained only when all imported examples satisfy it. The pinned text
data sometimes flattens a superscript such as `10^4` to `104`; the importer recognizes this form
for `10^3` through `10^9`. It skips element-wise, relational, ambiguous, unsupported, or
sample-conflicting ranges rather than guessing. This is not a complete constraint parser.

Matching first checks known aliases and exact title headings. It then compares meaningful words in
the pasted prompt with the imported descriptions. Short or ambiguous prompts are left unrecognized
instead of being assigned a guess. Recognition only selects a pack; it does not validate its
expected answers or make the dataset cases equivalent to hidden judge tests.

The API loads `services/api/data/problem_catalog.json` automatically, or uses the path in
`AXIOMA_PROBLEM_CATALOG_PATH`. Imported packs report their dataset source and explicitly say that
their cases are not LeetCode's hidden judge tests and have not been independently verified by Axioma.

The local workspace's current 1,000-pack catalog was regenerated on 2026-10-29 from the same 2,448
compatible dataset problems:
210 Easy, 395 Medium, and 395 Hard. Selection cycles through core DSA topics and difficulty levels,
then fills remaining slots in question-ID order. The catalog contains 48 Tree-tagged, 103 Graph-tagged,
223 Dynamic Programming-tagged, and 128 Breadth-First Search-tagged packs. Of the 1,000 packs, 977
contain 20 retained cases; the remaining packs contain 5 to 19. With the constraint parser, 534 of
the current 1,000 packs have at least one retained machine-checkable constraint. All retained
constraints were checked against every imported sample during this import. This balanced starter
catalog still does not cover every LeetCode problem; custom judge object types remain unsupported.
The import is local-only and is not committed to the repository; rerun the command above to generate
the constraint-enriched catalog after cloning or updating the importer.

A one-time self-retrieval check compared each imported full description against the same catalog:
987 matched their own slug, 13 were left unrecognized because the description was ambiguous, and none
were assigned to a different slug. This is a catalog integrity smoke check, not an independent
recognition accuracy estimate; unseen or edited user prompts still need held-out evaluation.

The dataset repository declares an MIT license; that does not by itself settle rights for
embedded third-party problem statements or test data. Review those rights before redistributing
the local catalog. The importer retains the repository license and source revision beside the data.
