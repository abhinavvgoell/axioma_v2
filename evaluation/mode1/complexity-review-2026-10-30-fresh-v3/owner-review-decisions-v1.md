# Owner review decisions — external multi-family pilot v1

**Reviewer:** project owner  
**Date:** 2026-10-30  
**Status:** Labels frozen before analysis; partition is calibration/diagnostic.

The original proposed packet, its manifest, and both proposed label artifacts remain unchanged. This record applies the owner decisions and the case 03 time revision.

| Case | Time decision | Approved time label | Space decision | Approved space label | Source SHA-256 |
|---|---|---|---|---|---|
| `axioma-20261030-v3-01` | approved | `O(log n)` (score `O(log n)`) | approved | `O(1)` (score `O(1)`) | `bf2d0a3cfb68b0518857385cfb41fccebd21c4884b1bd00f44360027b584b88e` |
| `axioma-20261030-v3-02` | approved | `O(n^2)` (score `O(n^2)`) | approved | `O(1)` (score `O(1)`) | `2b244e03a5831e74fc615090828949d6155b56eb1e898e34e021c73ac0723b75` |
| `axioma-20261030-v3-03` | approved_revised | `O(n*h), worst case O(n^2)` (score `O(n^2)`) | approved | `O(h), worst case O(n)` (score `O(n)`) | `828ca8cdba0a2f30dbace78ca4017eb83beea7266928d41de89b24cc6db434d2` |
| `axioma-20261030-v3-04` | approved | `O(m*n), worst case O(N^2) where N=m+n` (score `O(n^2)`) | approved | `O(m*n), worst case O(N^2)` (score `O(n^2)`) | `ed98d5f455bd5e792a734d763bae810767a679333f3f160f353b2769ded84b5b` |
| `axioma-20261030-v3-05` | approved | `O(V+E)` (score `O(n)`) | approved | `O(V+E)` (score `O(n)`) | `830a110a2827d491a5ce9efc4dd49110171950b587ddc2e379c89016c80690e0` |

## Case 03 revision

The owner revised recursive preorder time from O(n) to O(n·h), worst-case O(n²), and approved O(h) auxiliary space, worst-case O(n). PEP 380 describes the generator-protocol delegation chain and explicitly notes that recursive `yield from` traversals can incur enough delegation overhead to turn an intended linear operation into quadratic time. The case is scored by worst-case class O(n²).

## Frozen artifacts

- Gold labels: `gold-reviewed-v1.jsonl`  
- Gold SHA-256: `cae42511139f4c38f8a383950e5494b06b2edcf7adc41af3dbf2cb1095046a31`  
- Case packet SHA-256: `c815bfcb50c869d2dec14d764cf44536f7170a996ab90484d4592da429610a25`  
- Source hashes were checked against the original packet and preserved in the approved gold artifact.

This is a five-case calibration/diagnostic pilot, not a broad or untouched evaluation.
