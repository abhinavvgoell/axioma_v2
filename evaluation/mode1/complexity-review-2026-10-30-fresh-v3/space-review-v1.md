# Auxiliary-space review — external multi-family pilot v1

**Status:** Proposed; pending project-owner review. These are separate auxiliary-space labels for the exact five source snapshots in `review-packet-v1.jsonl`. They do not alter its time-complexity labels. Axioma has not been run on these cases.

**Space convention:** Exclude input storage and returned output; include temporary data structures and recursion stack. The exact expression is shown separately from the coarse scoring class. For the tree and graph cases, the scoring class uses the stated worst-case/input-size convention.

| Case | Exact proposed auxiliary space | Scoring class | Rationale | Source SHA-256 | Owner decision |
|---|---|---|---|---|---|
| `axioma-20261030-v3-01` | `O(1)` | `O(1)` | The implementation keeps only scalar indices and the midpoint; it allocates no input-sized auxiliary structure. | `bf2d0a3cfb68b0518857385cfb41fccebd21c4884b1bd00f44360027b584b88e` | pending |

**Assumptions — axioma-20261030-v3-01:** n = len(sorted_collection).
| `axioma-20261030-v3-02` | `O(1)` | `O(1)` | Insertion sort keeps the current value and index scalars and shifts elements within the input collection; it allocates no input-sized auxiliary structure. | `2b244e03a5831e74fc615090828949d6155b56eb1e898e34e021c73ac0723b75` | pending |

**Assumptions — axioma-20261030-v3-02:** n = len(collection); count auxiliary storage only, excluding the mutated input collection.
| `axioma-20261030-v3-03` | `O(h), worst case O(n)` | `O(n)` | Recursive yield-from traversal retains one active generator/frame per level, using O(h) stack space; the worst case is O(n). | `828ca8cdba0a2f30dbace78ca4017eb83beea7266928d41de89b24cc6db434d2` | pending |

**Assumptions — axioma-20261030-v3-03:** n is the node count and h is tree height; exclude the input tree and streamed yielded values. Worst case permits a skewed tree with h = n.
| `axioma-20261030-v3-04` | `O(m*n)` | `O(n^2)` | The int DP matrix has (m+1)(n+1) cells. Character arrays add O(m+n), which is bounded by O(m*n) for non-empty inputs; null or empty inputs return in O(1) or allocate only linear arrays before a zero-dimension table. | `ed98d5f455bd5e792a734d763bae810767a679333f3f160f353b2769ded84b5b` | pending |

**Assumptions — axioma-20261030-v3-04:** m = len(str1), n_total = len(str1) + len(str2); exclude input strings and the returned LCS. The character arrays and result construction are O(m+n); the DP matrix is O(m*n). The scoring class uses n_total.
| `axioma-20261030-v3-05` | `O(V + E)` | `O(n)` | The visited list and set use O(V) space. Because nodes are marked when dequeued, child references are queued before duplicate detection; pending queue entries can be O(E). Total auxiliary space is O(V+E). | `830a110a2827d491a5ce9efc4dd49110171950b587ddc2e379c89016c80690e0` | pending |

**Assumptions — axioma-20261030-v3-05:** V is the number of reachable nodes, E is the number of child references examined, and n = V+E for the coarse class bucket. Exclude the input graph. Analyze one call on a fresh instance; include the retained visited list/set and queue.

Reply for each ID with `approve`, `revise` (include the corrected label and rationale), or `exclude`. These remain proposed labels until the owner confirms them.
