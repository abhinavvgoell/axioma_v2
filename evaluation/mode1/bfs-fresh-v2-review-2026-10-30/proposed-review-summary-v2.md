# BFS Fresh Evaluation v2 — proposed review summary

**Status:** Proposed labels; pending owner confirmation. No gold labels have been frozen and Axioma has not been run on this packet.

- Cases: 28 unique (14 Java, 14 Python)
- Proposed decisions: 20 approve, 8 revise, 0 exclude
- Original packet SHA-256: `d7f997fee6a1317e164f20e59dac5f2edd0da6398f0c6d8a33b9f8f455ab29b1`
- Original manifest packet hash matches the packet; all 28 case source hashes were recalculated and matched.

## Eight revisions

- `axioma-bfs-v2-j01` — expected O(1) HashMap-equivalent lookup and valid root.
- `axioma-bfs-v2-j03` — expected O(1) backing-map operations; component-driver remains outside recognizer scope.
- `axioma-bfs-v2-j06` — Q = `starts.length`; expected O(1) map operations.
- `axioma-bfs-v2-j08` — O(V + VE) = O(V(E + 1)); n = V; valid source and endpoint IDs in [0,V); O(VE) simplified when E >= 1.
- `axioma-bfs-v2-j10` — O(1) indexed access to outer children collection; retain directed rooted-tree guarantee.
- `axioma-bfs-v2-j13` — every in-bounds neighbor candidate triggers a full-grid scan; grid values do not gate traversal.
- `axioma-bfs-v2-j14` — O(1) indexed outer adjacency access; preserve ArrayList queue and increasing head index.
- `axioma-bfs-v2-p07` — neighbors helper: O(1) iterator creation, O(deg(node)) iteration, no hidden full-graph scan.

Other approved cases retain their proposed mathematical labels and expected analyzer response categories, with the consolidated dense-ID, matrix, and grid input-contract clarifications. P11 remains `estimate` based on inspection of the existing recognizer and regression test. P14 retains O((V + E) * log(V + E)) and `unknown`, with nonnegative weights, lazy stale-entry deletion, and hashable/comparable heap node identifiers recorded.
