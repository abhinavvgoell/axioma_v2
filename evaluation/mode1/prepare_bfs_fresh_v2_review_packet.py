"""Prepare the human-review gate for the fresh BFS v2 packet; never runs analyzers."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evaluation/mode1/bfs-fresh-v2-review-2026-10-30"

# Each item: id, language, pattern, source, math label, expected response,
# representation/constraints, rationale, assumptions.
CASES = [
    ("j01", "java", "adjacency_list_single_source", """import java.util.*; class ReachA { int count(Map<Integer,List<Integer>> g,int root){ Set<Integer>s=new HashSet<>(); ArrayDeque<Integer>q=new ArrayDeque<>(); s.add(root);q.add(root);int n=0;while(!q.isEmpty()){int u=q.removeFirst();n++;for(int v:g.get(u))if(s.add(v))q.addLast(v);}return n;} }""", "O(V + E)", "estimate", "Map<Integer,List<Integer>> adjacency list with an entry, possibly empty, for every vertex; one source.", "Each reachable vertex is queued and expanded once; every stored neighbor entry is scanned once.", ["Expected O(1) HashSet and ArrayDeque operations.", "E is the total adjacency-entry count."]),
    ("j02", "java", "adjacency_list_multi_source", """import java.util.*; class ReachB { Set<Integer> walk(HashMap<Integer,List<Integer>>g,List<Integer>starts){Set<Integer>seen=new HashSet<>();Deque<Integer>q=new ArrayDeque<>();for(int s:starts)if(seen.add(s))q.offer(s);while(!q.isEmpty()){int u=q.poll();for(int v:g.get(u))if(seen.add(v))q.offer(v);}return seen;} }""", "O(S + V + E)", "estimate", "HashMap adjacency list with an entry for every vertex; S starting entries may include duplicates.", "The seed loop costs O(S), then at most V vertices and E adjacency entries are processed.", ["No S <= V assumption.", "Expected O(1) hash and deque operations."]),
    ("j03", "java", "disconnected_components_key_iteration", """import java.util.*; class ReachC { int all(Map<Integer,List<Integer>>g){Set<Integer>seen=new HashSet<>();int n=0;for(int seed:g.keySet()){if(seen.add(seed)){Deque<Integer>q=new ArrayDeque<>();q.add(seed);while(!q.isEmpty()){int u=q.remove();n++;for(int v:g.getOrDefault(u,List.of()))if(seen.add(v))q.add(v);}}}return n;} }""", "O(V + E)", "unknown", "Map keySet enumerates all vertices; one shared visited set spans components.", "Every vertex seeds at most one traversal; each adjacency entry is scanned once overall.", ["Expected O(1) hash and queue operations.", "The enhanced-for component driver may be outside the bounded recognizer."]),
    ("j04", "java", "array_of_adjacency_lists_boolean_visited", """import java.util.*; class ReachD { int walk(List<Integer>[]a,int s){boolean[]seen=new boolean[a.length];Queue<Integer>q=new ArrayDeque<>();seen[s]=true;q.add(s);while(!q.isEmpty()){int u=q.remove();for(int v:a[u])if(!seen[v]){seen[v]=true;q.add(v);}}return 0;} }""", "O(V + E)", "unknown", "Array of per-vertex neighbor lists and dense integer IDs.", "Each vertex is marked before enqueue and each adjacency entry is examined once.", ["Array, boolean and queue operations are O(1).", "Array-of-lists is distinct from nested List and Map declarations."]),
    ("j05", "java", "adjacency_matrix", """import java.util.*; class MatrixWalk { int run(boolean[][]m,int s){int n=m.length;boolean[]seen=new boolean[n];Queue<Integer>q=new ArrayDeque<>();seen[s]=true;q.add(s);while(!q.isEmpty()){int u=q.remove();for(int v=0;v<n;v++)if(m[u][v]&&!seen[v]){seen[v]=true;q.add(v);}}return 0;} }""", "O(V^2)", "estimate", "V by V boolean matrix; each dequeued node scans every column.", "At most V vertices are dequeued, each with a V-entry row scan.", ["Matrix, visited and queue operations are O(1)."]),
    ("j06", "java", "repeated_bfs_per_query", """import java.util.*; class QueryWalk { int all(Map<Integer,List<Integer>>g,int[]starts){int total=0;for(int s:starts){Set<Integer>seen=new HashSet<>();Queue<Integer>q=new ArrayDeque<>();seen.add(s);q.add(s);while(!q.isEmpty()){int u=q.remove();total++;for(int v:g.getOrDefault(u,List.of()))if(seen.add(v))q.add(v);}}return total;} }""", "O(Q * (V + E))", "unknown", "Fresh BFS state for each of Q query starts.", "Each query can traverse V vertices and E entries; the outer loop repeats that work Q times.", ["Q is independent of V; no simplifying relationship is assumed.", "Expected O(1) hash and queue operations."]),
    ("j07", "java", "ordered_map_and_set", """import java.util.*; class OrderedWalk { int run(TreeMap<Integer,List<Integer>>g,int s){TreeSet<Integer>seen=new TreeSet<>();Queue<Integer>q=new ArrayDeque<>();seen.add(s);q.add(s);while(!q.isEmpty()){int u=q.remove();for(int v:g.getOrDefault(u,List.of()))if(seen.add(v))q.add(v);}return seen.size();} }""", "O((V + E) log V)", "unknown", "TreeMap adjacency and TreeSet visited state.", "Ordered lookup and membership/insertion cost O(log V); scanning E entries gives O(E log V), plus vertex work.", ["Tree operations are worst-case O(log V)."]),
    ("j08", "java", "edge_list_rescanned_per_vertex", """import java.util.*; class EdgeWalk { static class E{int a,b;E(int x,int y){a=x;b=y;}} int run(List<E>edges,int n,int s){boolean[]seen=new boolean[n];Queue<Integer>q=new ArrayDeque<>();seen[s]=true;q.add(s);while(!q.isEmpty()){int u=q.remove();for(E e:edges){int v=e.a==u?e.b:(e.b==u?e.a:-1);if(v>=0&&!seen[v]){seen[v]=true;q.add(v);}}}return 0;} }""", "O(V * E)", "unknown", "Edges stored once in a flat list; every dequeued vertex scans all E records.", "There are at most V dequeues and each scans E edges.", ["Visited and queue operations are O(1)."]),
    ("j09", "java", "nested_vertex_scan_inside_bfs", """import java.util.*; class NestedWork { int run(List<List<Integer>>g,int n,int s){Set<Integer>seen=new HashSet<>();Queue<Integer>q=new ArrayDeque<>();seen.add(s);q.add(s);while(!q.isEmpty()){int u=q.remove();for(int i=0;i<n;i++)consume(i);for(int v:g.get(u))if(seen.add(v))q.add(v);}return 0;} void consume(int x){} }""", "O(V^2 + E)", "unknown", "One full V-sized loop runs for each dequeued vertex, in addition to adjacency scanning.", "The repeated loop costs V*V; edge enumeration adds E.", ["The extra loop always scans all V vertices."]),
    ("j10", "java", "directed_tree_without_visited", """import java.util.*; class TreeWalk { int run(List<List<Integer>>children,int root){Queue<Integer>q=new ArrayDeque<>();q.add(root);int n=0;while(!q.isEmpty()){int u=q.remove();n++;for(int v:children.get(u))q.add(v);}return n;} }""", "O(V + E)", "unknown", "Input is guaranteed to be a directed rooted tree oriented away from root; no visited set is used.", "Unique root-to-node paths imply each vertex is queued once; all vertices and edges are traversed linearly.", ["Tree orientation and acyclicity are external input guarantees.", "The method body alone cannot establish them."]),
    ("j11", "java", "grid_four_direction_offset_arrays", """import java.util.*; class GridFour { int run(int[][]a,int sr,int sc){int r=a.length,c=a[0].length;boolean[][]seen=new boolean[r][c];int[]dr={1,-1,0,0},dc={0,0,1,-1};ArrayDeque<int[]>q=new ArrayDeque<>();seen[sr][sc]=true;q.add(new int[]{sr,sc});while(!q.isEmpty()){int[]p=q.remove();for(int d=0;d<4;d++){int x=p[0]+dr[d],y=p[1]+dc[d];if(x>=0&&x<r&&y>=0&&y<c&&a[x][y]==1&&!seen[x][y]){seen[x][y]=true;q.add(new int[]{x,y});}}}return 0;} }""", "O(R * C)", "estimate", "Rectangular binary grid with four fixed orthogonal offsets.", "Each reachable cell enters once and checks four constant directions.", ["R and C are dimensions; four is constant.", "Array, queue and visited accesses are O(1)."]),
    ("j12", "java", "grid_eight_direction_offsets", """import java.util.*; class GridEight { int run(int[][]a,int sr,int sc){int r=a.length,c=a[0].length;boolean[][]seen=new boolean[r][c];int[]dr={-1,-1,-1,0,0,1,1,1},dc={-1,0,1,-1,1,-1,0,1};Deque<int[]>q=new ArrayDeque<>();seen[sr][sc]=true;q.addLast(new int[]{sr,sc});while(!q.isEmpty()){int[]p=q.removeFirst();for(int d=0;d<8;d++){int x=p[0]+dr[d],y=p[1]+dc[d];if(x>=0&&x<r&&y>=0&&y<c&&a[x][y]!=0&&!seen[x][y]){seen[x][y]=true;q.addLast(new int[]{x,y});}}}return 0;} }""", "O(R * C)", "estimate", "Rectangular grid with eight fixed neighbor offsets.", "Each cell expands once and checks eight constant-time neighbors.", ["Eight is a fixed constant.", "Queue and visited operations are O(1)."]),
    ("j13", "java", "full_grid_scan_inside_neighbor_processing", """import java.util.*; class GridScan { int run(int[][]a,int sr,int sc){int r=a.length,c=a[0].length;boolean[][]seen=new boolean[r][c];int[]dr={1,0,-1,0},dc={0,1,0,-1};Queue<int[]>q=new ArrayDeque<>();seen[sr][sc]=true;q.add(new int[]{sr,sc});while(!q.isEmpty()){int[]p=q.remove();for(int d=0;d<4;d++){int x=p[0]+dr[d],y=p[1]+dc[d];if(x>=0&&x<r&&y>=0&&y<c){for(int i=0;i<r;i++)for(int j=0;j<c;j++)inspect(a[i][j]);if(!seen[x][y]){seen[x][y]=true;q.add(new int[]{x,y});}}}}return 0;} void inspect(int x){} }""", "O((R * C)^2)", "estimate", "Binary grid and each valid local neighbor candidate triggers a full grid scan before enqueueing.", "Each reachable cell has at most four candidates; in an all-open grid, each candidate incurs R*C scan work, giving O((R*C)^2) total.", ["Grid cells are binary/nonnegative so the scan has no early-return exit.", "Four candidates per cell is constant; R and C are dimensions."]),
    ("j14", "java", "indexed_array_queue_adjacency_list", """import java.util.*; class IndexedWalk { int run(List<List<Integer>>g,int start){boolean[]seen=new boolean[g.size()];ArrayList<Integer>q=new ArrayList<>();q.add(start);seen[start]=true;for(int head=0;head<q.size();head++){int u=q.get(head);for(int v:g.get(u))if(!seen[v]){seen[v]=true;q.add(v);}}return q.size();} }""", "O(V + E)", "unknown", "List-of-lists adjacency and an ArrayList queue read with a monotonically increasing head index.", "Each vertex is appended/read once and each adjacency entry is scanned once; indexed reads avoid front-removal shifts.", ["ArrayList append is amortized O(1); indexed access is O(1).", "The current graph matcher may require Queue/Deque API operations."]),
    ("p01", "python", "adjacency_list_dict_deque", """from collections import deque\ndef reachable(graph, origin):\n    visited = {origin}\n    pending = deque([origin])\n    while pending:\n        current = pending.popleft()\n        for neighbor in graph[current]:\n            if neighbor not in visited:\n                visited.add(neighbor)\n                pending.append(neighbor)\n    return visited""", "O(V + E)", "estimate", "Dictionary with an adjacency list, including empty lists, for each vertex; deque and visited set.", "Each vertex is appended and expanded once, and each adjacency entry is scanned once.", ["Average O(1) set/dict operations; deque endpoint operations O(1)."]),
    ("p02", "python", "multi_source_duplicate_starts", """from collections import deque\ndef spread(graph, seeds):\n    marked, line = set(), deque()\n    for seed in seeds:\n        if seed not in marked:\n            marked.add(seed)\n            line.append(seed)\n    while line:\n        node = line.popleft()\n        for child in graph.get(node, ()):\n            if child not in marked:\n                marked.add(child)\n                line.append(child)\n    return marked""", "O(S + V + E)", "unknown", "S starting entries may include duplicates; graph is an adjacency list.", "The seed pass costs O(S), then traversal costs O(V+E); no S<=V assumption permits simplification.", ["Average O(1) set/dict operations and O(1) deque endpoints.", "Current Python BFS rule has no explicit S-term evidence."]),
    ("p03", "python", "disconnected_components_global_visited", """from collections import deque\ndef components(graph):\n    seen = set()\n    for root in graph:\n        if root in seen:\n            continue\n        seen.add(root)\n        q = deque([root])\n        while q:\n            u = q.popleft()\n            for v in graph.get(u, ()):\n                if v not in seen:\n                    seen.add(v)\n                    q.append(v)\n    return seen""", "O(V + E)", "unknown", "Iterate all vertices and launch a traversal only for unseen roots; one global set.", "Each vertex seeds at most once and each adjacency list is expanded once overall.", ["Average O(1) hash and queue operations.", "A queue loop is nested under the component driver."]),
    ("p04", "python", "boolean_list_visited", """from collections import deque\ndef visit(adj, start):\n    used = [False] * len(adj)\n    used[start] = True\n    q = deque([start])\n    while q:\n        u = q.popleft()\n        for v in adj[u]:\n            if not used[v]:\n                used[v] = True\n                q.append(v)\n    return sum(used)""", "O(V + E)", "unknown", "Dense integer IDs, list-of-lists adjacency and a boolean visited list.", "Every vertex is enqueued once and every adjacency entry is examined once.", ["List indexing and deque operations are O(1).", "Current Python graph matcher may require a set membership guard."]),
    ("p05", "python", "adjacency_matrix", """from collections import deque\ndef matrix_reach(matrix, source):\n    n = len(matrix)\n    seen = [False] * n\n    seen[source] = True\n    q = deque([source])\n    while q:\n        u = q.popleft()\n        for v, connected in enumerate(matrix[u]):\n            if connected and not seen[v]:\n                seen[v] = True\n                q.append(v)\n    return sum(seen)""", "O(V^2)", "unknown", "V by V boolean matrix; scan a complete row for each dequeued vertex.", "At most V rows are processed, each with V entries.", ["Dense matrix indexing is O(1).", "A list subscript alone must not be treated as adjacency-list evidence."]),
    ("p06", "python", "repeated_bfs_per_request", """from collections import deque\ndef answer(graph, requests):\n    total = 0\n    for source in requests:\n        seen, q = {source}, deque([source])\n        while q:\n            u = q.popleft()\n            total += 1\n            for v in graph.get(u, ()):\n                if v not in seen:\n                    seen.add(v)\n                    q.append(v)\n    return total""", "O(Q * (V + E))", "unknown", "A new BFS is performed for each of Q requests.", "Each traversal may scan V vertices and E entries; the outer loop multiplies the work by Q.", ["Q is independent of V.", "Average O(1) hash and deque operations."]),
    ("p07", "python", "neighbor_helper_contract", """from collections import deque\ndef walk(graph, source):\n    seen, q = {source}, deque([source])\n    while q:\n        node = q.popleft()\n        for neighbor in graph.neighbors(node):\n            if neighbor not in seen:\n                seen.add(neighbor)\n                q.append(neighbor)\n    return len(seen)""", "O(V + E)", "unknown", "neighbors(node) is contractually an iterator over that vertex's adjacency entries.", "The contract gives O(E) total neighbor iteration plus O(V) queue work, but the selected method delegates the core traversal source.", ["The helper contract is supplied to the user.", "The current analyzer does not expand helper implementations."]),
    ("p08", "python", "list_queue_front_removal", """def walk(graph, start):\n    seen, q = {start}, [start]\n    while q:\n        node = q.pop(0)\n        for nxt in graph.get(node, ()):\n            if nxt not in seen:\n                seen.add(nxt)\n                q.append(nxt)\n    return len(seen)""", "O(V^2 + E)", "unknown", "Adjacency list, but FIFO queue uses list.pop(0).", "Each of at most V removals may shift O(V) elements, costing O(V^2); neighbor scans add O(E).", ["Python list front removal shifts remaining entries.", "Average O(1) visited/dict operations."]),
    ("p09", "python", "directed_tree_without_visited", """from collections import deque\ndef tree_size(children, root):\n    q, count = deque([root]), 0\n    while q:\n        parent = q.popleft()\n        count += 1\n        for child in children.get(parent, ()):\n            q.append(child)\n    return count""", "O(V + E)", "unknown", "Input contract guarantees a directed rooted tree oriented away from root; no seen set.", "Unique root paths ensure each vertex is queued once; every child edge is examined once.", ["Acyclicity and orientation are external preconditions not established by the method body."]),
    ("p10", "python", "queue_worklist_not_graph", """from collections import deque\ndef jobs(items):\n    pending = deque(items)\n    done = 0\n    while pending:\n        pending.popleft()\n        done += 1\n    return done""", "O(N)", "unknown", "A queue drains independent jobs; there is no graph or neighbor relation.", "Every item is removed once with constant work.", ["This is a queue-only non-BFS control case."]),
    ("p11", "python", "grid_four_neighbor_component_sweep", """from collections import deque\ndef regions(board):\n    rows, cols = len(board), len(board[0])\n    seen, total = set(), 0\n    for r in range(rows):\n        for c in range(cols):\n            if not board[r][c] or (r,c) in seen:\n                continue\n            total += 1\n            seen.add((r,c))\n            q = deque([(r,c)])\n            while q:\n                x,y = q.popleft()\n                for dx,dy in ((0,1),(1,0),(0,-1),(-1,0)):\n                    a,b = x+dx,y+dy\n                    if 0<=a<rows and 0<=b<cols and board[a][b] and (a,b) not in seen:\n                        seen.add((a,b))\n                        q.append((a,b))\n    return total""", "O(R * C)", "estimate", "Rectangular binary grid; full component sweep and four fixed offsets.", "The outer sweep checks each cell once; each active cell is enqueued once and makes four checks.", ["Average O(1) set operations; four is constant."]),
    ("p12", "python", "grid_eight_neighbor_fixed_tuple", """from collections import deque\ndef flood(image, start):\n    h,w = len(image),len(image[0])\n    seen,q = {start},deque([start])\n    dirs = ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1))\n    while q:\n        r,c = q.popleft()\n        for dr,dc in dirs:\n            nr,nc = r+dr,c+dc\n            if 0<=nr<h and 0<=nc<w and image[nr][nc] and (nr,nc) not in seen:\n                seen.add((nr,nc))\n                q.append((nr,nc))\n    return len(seen)""", "O(R * C)", "unknown", "Rectangular grid with a fixed tuple of eight surrounding offsets.", "Every cell expands once and examines eight constant-time neighbors.", ["Eight is constant; current Python grid rule may only support its four-neighbor form."]),
    ("p13", "python", "full_grid_scan_inside_neighbor_processing", """from collections import deque\ndef scan_flood(grid, start):\n    rows, cols = len(grid), len(grid[0])\n    seen, q = {start}, deque([start])\n    while q:\n        r,c = q.popleft()\n        for nr,nc in ((r-1,c),(r+1,c),(r,c-1),(r,c+1)):\n            if 0<=nr<rows and 0<=nc<cols:\n                for i in range(rows):\n                    for j in range(cols):\n                        inspect(grid[i][j])\n                if (nr,nc) not in seen:\n                    seen.add((nr,nc))\n                    q.append((nr,nc))\n    return len(seen)\ndef inspect(value):\n    return value""", "O((R * C)^2)", "unknown", "Each valid local neighbor candidate triggers a complete grid scan before discovery.", "A constant number of candidates per dequeued cell each cost R*C; across R*C cells this is quadratic in the cell count.", ["Four local candidates is constant.", "The full-grid scan is nested inside neighbor processing."]),
    ("p14", "python", "heap_ordered_weighted_traversal", """import heapq\ndef shortest(network, source):\n    distance, heap = {source: 0}, [(0, source)]\n    while heap:\n        cost, node = heapq.heappop(heap)\n        if cost != distance[node]:\n            continue\n        for neighbor, weight in network.get(node, ()):\n            candidate = cost + weight\n            if candidate < distance.get(neighbor, float('inf')):\n                distance[neighbor] = candidate\n                heapq.heappush(heap, (candidate, neighbor))\n    return distance""", "O((V + E) * log(V + E))", "unknown", "Heap-based shortest-path traversal over weighted adjacency lists; not FIFO BFS.", "With nonnegative weights and lazy stale-entry deletion, up to O(E) heap entries can be inserted and removed, each at logarithmic heap cost.", ["Weights are nonnegative and stale heap entries are skipped.", "A binary heap may contain O(E) entries; no simple-graph bound on E is assumed.", "This is a non-BFS priority-queue near-miss."]),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare() -> dict:
    if OUT.exists():
        manifest_path = OUT / "manifest.json"
        packet_path = OUT / "review-packet.jsonl"
        if not manifest_path.is_file() or not packet_path.is_file():
            raise FileExistsError(f"Refusing to overwrite unrecognized contents in {OUT}")
        old_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        old_rows = [json.loads(line) for line in packet_path.read_text(encoding="utf-8").splitlines()]
        sheet_path = OUT / "review-sheet.md"
        exclusions_path = OUT / "exclusions.md"
        artifacts_unchanged = (
            sheet_path.is_file()
            and exclusions_path.is_file()
            and sha(packet_path) == old_manifest.get("packet_sha256")
            and sha(sheet_path) == old_manifest.get("review_sheet_sha256")
            and sha(exclusions_path) == old_manifest.get("exclusions_sha256")
        )
        if not artifacts_unchanged or old_manifest.get("status") != "candidate_packet_pending_human_review" or any(
            row.get("review", {}).get("status") != "pending_human_review"
            or row.get("review", {}).get("decision")
            or row.get("review", {}).get("reviewer_rationale")
            for row in old_rows
        ):
            raise FileExistsError(f"Refusing to overwrite a reviewed or frozen packet in {OUT}")
    old_sources = set()
    old = ROOT / "evaluation/mode1/bfs-independent-2026-10-29-v1/cases.jsonl"
    if old.exists():
        old_sources = {json.loads(line)["source_sha256"] for line in old.read_text(encoding="utf-8").splitlines()}
    rows = []
    for case_id, lang, pattern, source, complexity, response, representation, rationale, assumptions in CASES:
        source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if source_hash in old_sources:
            raise ValueError(f"Reused prior BFS source: {case_id}")
        rows.append({
            "case_id": f"axioma-bfs-v2-{case_id}", "language": lang, "pattern": pattern,
            "source": source, "source_sha256": source_hash,
            "input_constraints_and_representation": representation,
            "expected_time_complexity": complexity, "mathematical_rationale": rationale,
            "assumptions": assumptions, "expected_response_category": response,
            "complexity_scorable": True,
            "review": {"status": "pending_human_review", "reviewer_id": "", "decision": "", "reviewer_rationale": "", "reviewed_at": ""},
        })
    OUT.mkdir(parents=True, exist_ok=True)
    packet_path = OUT / "review-packet.jsonl"
    packet_path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")
    lines = [
        "# Fresh independent BFS evaluation v2 — human review packet", "",
        "**Status: pending human review. The analyzer has not been run.** No predictions or analyzer evidence are present.", "",
        "Review each exact source, mathematical bound, rationale, assumptions, and expected analyzer response. Mark each `approve`, `revise`, or `exclude`; explain each decision. For any correction, identify the case and proposed change. Ambiguous cases must be revised or excluded before freezing approved labels.", "",
        "`expected_time_complexity` is the mathematical bound. `estimate` means the current bounded analyzer is expected to answer; `unknown` means it should abstain, even when the mathematical bound is known. Do not simplify bounds without the stated relationship.", "",
        "| Case | Language | Pattern | Expected complexity | Expected response | Review |", "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| {row['case_id']} | {row['language']} | {row['pattern']} | `{row['expected_time_complexity']}` | `{row['expected_response_category']}` | pending |")
    for row in rows:
        lines += ["", f"## {row['case_id']} — {row['language']} / {row['pattern']}", "",
            f"**Input contract:** {row['input_constraints_and_representation']}", "",
            f"**Proposed complexity:** `{row['expected_time_complexity']}`", "",
            f"**Expected response:** `{row['expected_response_category']}`", "",
            f"**Rationale:** {row['mathematical_rationale']}", "", "**Assumptions:**", ""]
        lines += [f"- {item}" for item in row["assumptions"]]
        lines += ["", f"**Source SHA-256:** `{row['source_sha256']}`", "",
            "**Exact source:**", "", f"```{row['language']}", row["source"], "```", "",
            "**Reviewer decision:** pending", "", "**Reviewer rationale:** pending", "", "---"]
    sheet = OUT / "review-sheet.md"
    sheet.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    exclusions = """# Excluded development and calibration cases

- Entire previous packet `evaluation/mode1/bfs-independent-2026-10-29-v1`: `bfs-ind-001` through `bfs-ind-022`, including adjacency cases 001/003 and grid case 010. This packet and all its cases are development/evaluation data.
- Existing diagnostic replays: Java adjacency BFS cases 001/003 (`java-adjacency-bfs-diagnostic-2026-10-29.json`); Java grid false-positive case 010 (`java-grid-bfs-fix-diagnostic-2026-10-29.json` and `grid-bfs-diagnostic-results-2026-10-29.json`).
- Java unit fixtures already used to develop the matcher: `test_recognizes_java_adjacency_list_bfs_with_visited_guard`, `test_recognizes_reviewed_java_adjacency_bfs_case_001`, `test_recognizes_reviewed_multi_source_case_with_general_s_bound`, `test_recognizes_adjacency_bfs_with_hashmap_declaration_and_braced_guard`, `test_recognizes_disconnected_components_with_one_global_visited_set`, `test_unbraced_set_guard_with_wrong_queue_argument_remains_unknown`, `test_java_adjacency_bfs_with_extra_nested_graph_scan_abstains`, `test_java_adjacency_bfs_without_marked_initial_vertex_abstains`, `test_java_adjacency_bfs_with_unsupported_neighbor_container_abstains`, `test_recognizes_java_adjacency_matrix_bfs_as_quadratic`, `test_matrix_bfs_without_visited_mark_before_enqueue_remains_unknown`, `test_unvisited_java_adjacency_queue_loop_remains_unknown`, `test_recognizes_java_adjacency_bfs_with_boolean_array_visited_guard`, `test_recognizes_java_grid_bfs_with_four_fixed_directions`, `test_java_grid_bfs_reports_a_fixed_eight_neighbor_loop`, `test_java_graph_bfs_inside_outer_loop_is_not_flattened_to_single_pass`, `test_java_grid_bfs_inside_outer_loop_is_not_flattened_to_one_traversal`, `test_frozen_java_grid_full_scan_case_accounts_for_nested_work`, `test_java_grid_full_scan_once_before_bfs_remains_linear`, `test_java_grid_full_scan_per_dequeued_cell_is_quadratic`, `test_java_grid_ambiguous_nested_loop_abstains`, `test_java_matrix_bfs_without_visited_marking_stays_inconclusive`, and `test_unmarked_java_array_visited_guard_does_not_claim_bfs_complexity`.
- Python fixtures already used to develop the matcher: `test_recognizes_adjacency_list_bfs_with_queue_and_visited_guard`, `test_recognizes_frozen_islands_grid_bfs_as_quadratic`, `test_grid_bfs_supports_rectangular_ranges_and_reports_dimensions`, `test_grid_bfs_without_enqueue_time_visited_mark_remains_unknown`, `test_grid_bfs_with_an_independent_full_grid_scan_is_not_bounded_to_one_pass`, `test_queue_usage_unrelated_to_graph_or_grid_stays_unclassified`, `test_unvisited_adjacency_queue_loop_remains_unknown`, and `test_adjacency_list_bfs_inside_outer_loop_is_not_flattened`.
- Packet 04 cases `axioma-20261029-16` through `axioma-20261029-20`: binary-search recurrence, memoized Fibonacci, Java monotonic stack, Python grid BFS and quicksort. The recurrence diagnostics for 16/17/20 and monotonic-stack diagnostic for 18 are not reused.
- Previously reviewed graph/tree catalog cases in `evaluation/mode1/complexity-review-2026-10-22/gold-reviewed.jsonl`: `lcd-v0.3.1-1791-find-center-of-star-graph`, `lcd-v0.3.1-834-sum-of-distances-in-tree`, `lcd-v0.3.1-997-find-the-town-judge`, `lcd-v0.3.1-207-course-schedule`, `lcd-v0.3.1-210-course-schedule-ii`, `lcd-v0.3.1-305-number-of-islands-ii`, `lcd-v0.3.1-329-longest-increasing-path-in-a-matrix`, and `lcd-v0.3.1-1377-frog-position-after-t-seconds`.

Exclusions are based on prior exposure, not on expected analyzer performance. The new source strings are hash-checked against the old 22-case packet. No v2 prediction has been inspected. Do not change or drop cases after analyzer execution; pre-run corrections require documenting the reason and making a new candidate packet hash.
"""
    exclusion_path = OUT / "exclusions.md"
    exclusion_path.write_text(exclusions, encoding="utf-8", newline="\n")
    java_src = ROOT / "services/worker/src/axioma_worker/java_complexity.py"
    python_src = ROOT / "services/worker/src/axioma_worker/python_complexity.py"
    manifest = {
        "packet_id": "axioma-fresh-independent-bfs-v2-2026-10-30",
        "status": "candidate_packet_pending_human_review",
        "execution_gate": "do_not_run_analyzer_until_all_retained_labels_are_human_approved",
        "case_count": len(rows), "language_counts": {"java": 14, "python": 14},
        "packet_file": packet_path.name, "packet_sha256": sha(packet_path),
        "review_sheet": sheet.name, "review_sheet_sha256": sha(sheet),
        "exclusions_file": exclusion_path.name, "exclusions_sha256": sha(exclusion_path),
        "source_hashes_verified": True,
        "analyzer_revision_recorded_separately": {
            "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "worktree_was_dirty_before_packet": True,
            "java_analyzer_sha256": sha(java_src), "python_analyzer_sha256": sha(python_src),
            "java_rule_versions": sorted(set(re.findall(r'"rule_version"\s*:\s*"([^"]+)"', java_src.read_text(encoding="utf-8")))),
            "python_rule_versions": sorted(set(re.findall(r'"rule_version"\s*:\s*"([^"]+)"', python_src.read_text(encoding="utf-8")))),
        },
        "predictions_or_analyzer_evidence_in_packet": False,
        "approved_gold_labels": None,
        "approved_label_sha256": None,
        "note": "The packet is a candidate only. No analyzers were invoked. Freeze an approved label artifact and hash after human review, before evaluation.",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    (OUT / "evidence-audit-entry.md").write_text(
        "# Evidence audit entry — fresh BFS v2 packet preparation (2026-10-30)\n\n"
        "Prepared a 28-case candidate set: 14 Java and 14 Python. It covers adjacency lists, multi-source setup, disconnected components, matrices, representation-dependent costs, repeated and nested work, visited-state and queue near-misses, and four-/eight-neighbor grids. Per-case sources, hashes, proposed math labels, assumptions, rationales, expected response category and blank reviewer fields are in `review-packet.jsonl` and `review-sheet.md`.\n\n"
        "Labels remain pending human review. There are no predictions or analyzer evidence, and the analyzers were not run. Exclusions are listed in `exclusions.md`. Candidate hashes and the current analyzer source hashes/rule versions are recorded separately in `manifest.json`.\n\n"
        "Next gate: owner reviews each retained case, records decisions and rationale, and resolves or excludes ambiguity. Only after approval may labels be frozen/hashed and evaluation begin.\n",
        encoding="utf-8", newline="\n")
    loaded = [json.loads(line) for line in packet_path.read_text(encoding="utf-8").splitlines()]
    assert len(loaded) == 28 and sum(row["language"] == "java" for row in loaded) == 14
    assert sum(row["language"] == "python" for row in loaded) == 14
    assert len({row["case_id"] for row in loaded}) == len(loaded)
    assert all(hashlib.sha256(row["source"].encode("utf-8")).hexdigest() == row["source_sha256"] for row in loaded)
    assert all(row["review"]["status"] == "pending_human_review" for row in loaded)
    return manifest


if __name__ == "__main__":
    print(json.dumps(prepare(), indent=2))
