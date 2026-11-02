# Batch 04 review summary

- Cases 016–020: all five owner decisions recorded on 2026-11-02; batch 04 is frozen as a partial batch only.
- 016 approved: O(n log n) time and O(n) auxiliary space; returned merge output is excluded, while sorted-copy and Timsort storage remain O(n).
- 017 approved: O(n log n) time and O(n) auxiliary space under equal-length inputs with n matching both lengths.
- 018 approved: O(V+E) time and O(V) auxiliary space; requires a fresh visited list and empty global output stack. Deep recursion can exceed Python's recursion limit.
- 019 approved: O(n) worst-case time and O(1) auxiliary space; comparator exception/restoration caveat documented.
- 020 revised auxiliary space only: O(k) exact auxiliary space and O(n) coarse score when k=O(n); total storage including returned output is O(n+k). Time remains O(n+k), coarse O(n).
- Total owner-reviewed: 20/30. Full calibration set frozen: no. Axioma run on candidates: no.
