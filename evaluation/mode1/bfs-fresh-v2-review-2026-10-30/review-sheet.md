# Fresh independent BFS evaluation v2 — human review packet

**Status: pending human review. The analyzer has not been run.** No predictions or analyzer evidence are present.

Review each exact source, mathematical bound, rationale, assumptions, and expected analyzer response. Mark each `approve`, `revise`, or `exclude`; explain each decision. For any correction, identify the case and proposed change. Ambiguous cases must be revised or excluded before freezing approved labels.

`expected_time_complexity` is the mathematical bound. `estimate` means the current bounded analyzer is expected to answer; `unknown` means it should abstain, even when the mathematical bound is known. Do not simplify bounds without the stated relationship.

| Case | Language | Pattern | Expected complexity | Expected response | Review |
|---|---|---|---|---|---|
| axioma-bfs-v2-j01 | java | adjacency_list_single_source | `O(V + E)` | `estimate` | pending |
| axioma-bfs-v2-j02 | java | adjacency_list_multi_source | `O(S + V + E)` | `estimate` | pending |
| axioma-bfs-v2-j03 | java | disconnected_components_key_iteration | `O(V + E)` | `unknown` | pending |
| axioma-bfs-v2-j04 | java | array_of_adjacency_lists_boolean_visited | `O(V + E)` | `unknown` | pending |
| axioma-bfs-v2-j05 | java | adjacency_matrix | `O(V^2)` | `estimate` | pending |
| axioma-bfs-v2-j06 | java | repeated_bfs_per_query | `O(Q * (V + E))` | `unknown` | pending |
| axioma-bfs-v2-j07 | java | ordered_map_and_set | `O((V + E) log V)` | `unknown` | pending |
| axioma-bfs-v2-j08 | java | edge_list_rescanned_per_vertex | `O(V * E)` | `unknown` | pending |
| axioma-bfs-v2-j09 | java | nested_vertex_scan_inside_bfs | `O(V^2 + E)` | `unknown` | pending |
| axioma-bfs-v2-j10 | java | directed_tree_without_visited | `O(V + E)` | `unknown` | pending |
| axioma-bfs-v2-j11 | java | grid_four_direction_offset_arrays | `O(R * C)` | `estimate` | pending |
| axioma-bfs-v2-j12 | java | grid_eight_direction_offsets | `O(R * C)` | `estimate` | pending |
| axioma-bfs-v2-j13 | java | full_grid_scan_inside_neighbor_processing | `O((R * C)^2)` | `estimate` | pending |
| axioma-bfs-v2-j14 | java | indexed_array_queue_adjacency_list | `O(V + E)` | `unknown` | pending |
| axioma-bfs-v2-p01 | python | adjacency_list_dict_deque | `O(V + E)` | `estimate` | pending |
| axioma-bfs-v2-p02 | python | multi_source_duplicate_starts | `O(S + V + E)` | `unknown` | pending |
| axioma-bfs-v2-p03 | python | disconnected_components_global_visited | `O(V + E)` | `unknown` | pending |
| axioma-bfs-v2-p04 | python | boolean_list_visited | `O(V + E)` | `unknown` | pending |
| axioma-bfs-v2-p05 | python | adjacency_matrix | `O(V^2)` | `unknown` | pending |
| axioma-bfs-v2-p06 | python | repeated_bfs_per_request | `O(Q * (V + E))` | `unknown` | pending |
| axioma-bfs-v2-p07 | python | neighbor_helper_contract | `O(V + E)` | `unknown` | pending |
| axioma-bfs-v2-p08 | python | list_queue_front_removal | `O(V^2 + E)` | `unknown` | pending |
| axioma-bfs-v2-p09 | python | directed_tree_without_visited | `O(V + E)` | `unknown` | pending |
| axioma-bfs-v2-p10 | python | queue_worklist_not_graph | `O(N)` | `unknown` | pending |
| axioma-bfs-v2-p11 | python | grid_four_neighbor_component_sweep | `O(R * C)` | `estimate` | pending |
| axioma-bfs-v2-p12 | python | grid_eight_neighbor_fixed_tuple | `O(R * C)` | `unknown` | pending |
| axioma-bfs-v2-p13 | python | full_grid_scan_inside_neighbor_processing | `O((R * C)^2)` | `unknown` | pending |
| axioma-bfs-v2-p14 | python | heap_ordered_weighted_traversal | `O((V + E) * log(V + E))` | `unknown` | pending |

## axioma-bfs-v2-j01 — java / adjacency_list_single_source

**Input contract:** Map<Integer,List<Integer>> adjacency list with an entry, possibly empty, for every vertex; one source.

**Proposed complexity:** `O(V + E)`

**Expected response:** `estimate`

**Rationale:** Each reachable vertex is queued and expanded once; every stored neighbor entry is scanned once.

**Assumptions:**

- Expected O(1) HashSet and ArrayDeque operations.
- E is the total adjacency-entry count.

**Source SHA-256:** `216b479db758ab27134b82bff666e1c339561ebcf0863cfcd2134650cd937d20`

**Exact source:**

```java
import java.util.*; class ReachA { int count(Map<Integer,List<Integer>> g,int root){ Set<Integer>s=new HashSet<>(); ArrayDeque<Integer>q=new ArrayDeque<>(); s.add(root);q.add(root);int n=0;while(!q.isEmpty()){int u=q.removeFirst();n++;for(int v:g.get(u))if(s.add(v))q.addLast(v);}return n;} }
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-j02 — java / adjacency_list_multi_source

**Input contract:** HashMap adjacency list with an entry for every vertex; S starting entries may include duplicates.

**Proposed complexity:** `O(S + V + E)`

**Expected response:** `estimate`

**Rationale:** The seed loop costs O(S), then at most V vertices and E adjacency entries are processed.

**Assumptions:**

- No S <= V assumption.
- Expected O(1) hash and deque operations.

**Source SHA-256:** `9ee0c0d70038b29a28d6c6fce9ebd254f18a458f19afb8b40fbefc8e7cb4eed0`

**Exact source:**

```java
import java.util.*; class ReachB { Set<Integer> walk(HashMap<Integer,List<Integer>>g,List<Integer>starts){Set<Integer>seen=new HashSet<>();Deque<Integer>q=new ArrayDeque<>();for(int s:starts)if(seen.add(s))q.offer(s);while(!q.isEmpty()){int u=q.poll();for(int v:g.get(u))if(seen.add(v))q.offer(v);}return seen;} }
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-j03 — java / disconnected_components_key_iteration

**Input contract:** Map keySet enumerates all vertices; one shared visited set spans components.

**Proposed complexity:** `O(V + E)`

**Expected response:** `unknown`

**Rationale:** Every vertex seeds at most one traversal; each adjacency entry is scanned once overall.

**Assumptions:**

- Expected O(1) hash and queue operations.
- The enhanced-for component driver may be outside the bounded recognizer.

**Source SHA-256:** `889cfb9e0734a97401746f26d48d05f85ecfd1ef3227edf0a31554727bacd4e7`

**Exact source:**

```java
import java.util.*; class ReachC { int all(Map<Integer,List<Integer>>g){Set<Integer>seen=new HashSet<>();int n=0;for(int seed:g.keySet()){if(seen.add(seed)){Deque<Integer>q=new ArrayDeque<>();q.add(seed);while(!q.isEmpty()){int u=q.remove();n++;for(int v:g.getOrDefault(u,List.of()))if(seen.add(v))q.add(v);}}}return n;} }
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-j04 — java / array_of_adjacency_lists_boolean_visited

**Input contract:** Array of per-vertex neighbor lists and dense integer IDs.

**Proposed complexity:** `O(V + E)`

**Expected response:** `unknown`

**Rationale:** Each vertex is marked before enqueue and each adjacency entry is examined once.

**Assumptions:**

- Array, boolean and queue operations are O(1).
- Array-of-lists is distinct from nested List and Map declarations.

**Source SHA-256:** `7c195b389540f3f961b48d4ecf50c47f3b9ae8c3e389128d6e98c80e50e51284`

**Exact source:**

```java
import java.util.*; class ReachD { int walk(List<Integer>[]a,int s){boolean[]seen=new boolean[a.length];Queue<Integer>q=new ArrayDeque<>();seen[s]=true;q.add(s);while(!q.isEmpty()){int u=q.remove();for(int v:a[u])if(!seen[v]){seen[v]=true;q.add(v);}}return 0;} }
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-j05 — java / adjacency_matrix

**Input contract:** V by V boolean matrix; each dequeued node scans every column.

**Proposed complexity:** `O(V^2)`

**Expected response:** `estimate`

**Rationale:** At most V vertices are dequeued, each with a V-entry row scan.

**Assumptions:**

- Matrix, visited and queue operations are O(1).

**Source SHA-256:** `ec39246eaac54a8b20fec8fc2cce1807463d9cae32a98d388c85666bfa0099ad`

**Exact source:**

```java
import java.util.*; class MatrixWalk { int run(boolean[][]m,int s){int n=m.length;boolean[]seen=new boolean[n];Queue<Integer>q=new ArrayDeque<>();seen[s]=true;q.add(s);while(!q.isEmpty()){int u=q.remove();for(int v=0;v<n;v++)if(m[u][v]&&!seen[v]){seen[v]=true;q.add(v);}}return 0;} }
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-j06 — java / repeated_bfs_per_query

**Input contract:** Fresh BFS state for each of Q query starts.

**Proposed complexity:** `O(Q * (V + E))`

**Expected response:** `unknown`

**Rationale:** Each query can traverse V vertices and E entries; the outer loop repeats that work Q times.

**Assumptions:**

- Q is independent of V; no simplifying relationship is assumed.
- Expected O(1) hash and queue operations.

**Source SHA-256:** `4302bc4f48e8b71ed01c427318cec010e3d8de6ab862d2e343392b265baa6530`

**Exact source:**

```java
import java.util.*; class QueryWalk { int all(Map<Integer,List<Integer>>g,int[]starts){int total=0;for(int s:starts){Set<Integer>seen=new HashSet<>();Queue<Integer>q=new ArrayDeque<>();seen.add(s);q.add(s);while(!q.isEmpty()){int u=q.remove();total++;for(int v:g.getOrDefault(u,List.of()))if(seen.add(v))q.add(v);}}return total;} }
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-j07 — java / ordered_map_and_set

**Input contract:** TreeMap adjacency and TreeSet visited state.

**Proposed complexity:** `O((V + E) log V)`

**Expected response:** `unknown`

**Rationale:** Ordered lookup and membership/insertion cost O(log V); scanning E entries gives O(E log V), plus vertex work.

**Assumptions:**

- Tree operations are worst-case O(log V).

**Source SHA-256:** `284c25fbed7bf46f410f5cf7eb3e6b4c0d54497b79cd584d2b47f7e5fb4357b2`

**Exact source:**

```java
import java.util.*; class OrderedWalk { int run(TreeMap<Integer,List<Integer>>g,int s){TreeSet<Integer>seen=new TreeSet<>();Queue<Integer>q=new ArrayDeque<>();seen.add(s);q.add(s);while(!q.isEmpty()){int u=q.remove();for(int v:g.getOrDefault(u,List.of()))if(seen.add(v))q.add(v);}return seen.size();} }
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-j08 — java / edge_list_rescanned_per_vertex

**Input contract:** Edges stored once in a flat list; every dequeued vertex scans all E records.

**Proposed complexity:** `O(V * E)`

**Expected response:** `unknown`

**Rationale:** There are at most V dequeues and each scans E edges.

**Assumptions:**

- Visited and queue operations are O(1).

**Source SHA-256:** `17037d0e839be2b1367515e132e86fa5c5e1a2b3be25b7947e0784cf64a71e3b`

**Exact source:**

```java
import java.util.*; class EdgeWalk { static class E{int a,b;E(int x,int y){a=x;b=y;}} int run(List<E>edges,int n,int s){boolean[]seen=new boolean[n];Queue<Integer>q=new ArrayDeque<>();seen[s]=true;q.add(s);while(!q.isEmpty()){int u=q.remove();for(E e:edges){int v=e.a==u?e.b:(e.b==u?e.a:-1);if(v>=0&&!seen[v]){seen[v]=true;q.add(v);}}}return 0;} }
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-j09 — java / nested_vertex_scan_inside_bfs

**Input contract:** One full V-sized loop runs for each dequeued vertex, in addition to adjacency scanning.

**Proposed complexity:** `O(V^2 + E)`

**Expected response:** `unknown`

**Rationale:** The repeated loop costs V*V; edge enumeration adds E.

**Assumptions:**

- The extra loop always scans all V vertices.

**Source SHA-256:** `9bd2de6bec1b1504f75e144d2a906fafb7330402f1286716dd1e9b9bb62c892f`

**Exact source:**

```java
import java.util.*; class NestedWork { int run(List<List<Integer>>g,int n,int s){Set<Integer>seen=new HashSet<>();Queue<Integer>q=new ArrayDeque<>();seen.add(s);q.add(s);while(!q.isEmpty()){int u=q.remove();for(int i=0;i<n;i++)consume(i);for(int v:g.get(u))if(seen.add(v))q.add(v);}return 0;} void consume(int x){} }
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-j10 — java / directed_tree_without_visited

**Input contract:** Input is guaranteed to be a directed rooted tree oriented away from root; no visited set is used.

**Proposed complexity:** `O(V + E)`

**Expected response:** `unknown`

**Rationale:** Unique root-to-node paths imply each vertex is queued once; all vertices and edges are traversed linearly.

**Assumptions:**

- Tree orientation and acyclicity are external input guarantees.
- The method body alone cannot establish them.

**Source SHA-256:** `d3fadf415fa966b80e61966fefe881f038645f5f2084d4d1fdfd3bf96be4ae4f`

**Exact source:**

```java
import java.util.*; class TreeWalk { int run(List<List<Integer>>children,int root){Queue<Integer>q=new ArrayDeque<>();q.add(root);int n=0;while(!q.isEmpty()){int u=q.remove();n++;for(int v:children.get(u))q.add(v);}return n;} }
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-j11 — java / grid_four_direction_offset_arrays

**Input contract:** Rectangular binary grid with four fixed orthogonal offsets.

**Proposed complexity:** `O(R * C)`

**Expected response:** `estimate`

**Rationale:** Each reachable cell enters once and checks four constant directions.

**Assumptions:**

- R and C are dimensions; four is constant.
- Array, queue and visited accesses are O(1).

**Source SHA-256:** `78ef756e81c64358d429c5db96421405e4c5a41a3c15d3890525989aeaa07144`

**Exact source:**

```java
import java.util.*; class GridFour { int run(int[][]a,int sr,int sc){int r=a.length,c=a[0].length;boolean[][]seen=new boolean[r][c];int[]dr={1,-1,0,0},dc={0,0,1,-1};ArrayDeque<int[]>q=new ArrayDeque<>();seen[sr][sc]=true;q.add(new int[]{sr,sc});while(!q.isEmpty()){int[]p=q.remove();for(int d=0;d<4;d++){int x=p[0]+dr[d],y=p[1]+dc[d];if(x>=0&&x<r&&y>=0&&y<c&&a[x][y]==1&&!seen[x][y]){seen[x][y]=true;q.add(new int[]{x,y});}}}return 0;} }
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-j12 — java / grid_eight_direction_offsets

**Input contract:** Rectangular grid with eight fixed neighbor offsets.

**Proposed complexity:** `O(R * C)`

**Expected response:** `estimate`

**Rationale:** Each cell expands once and checks eight constant-time neighbors.

**Assumptions:**

- Eight is a fixed constant.
- Queue and visited operations are O(1).

**Source SHA-256:** `c79577dd525413a66c82e66a0c9388a45ca75c095e2fba7c2e4590c8adcf3986`

**Exact source:**

```java
import java.util.*; class GridEight { int run(int[][]a,int sr,int sc){int r=a.length,c=a[0].length;boolean[][]seen=new boolean[r][c];int[]dr={-1,-1,-1,0,0,1,1,1},dc={-1,0,1,-1,1,-1,0,1};Deque<int[]>q=new ArrayDeque<>();seen[sr][sc]=true;q.addLast(new int[]{sr,sc});while(!q.isEmpty()){int[]p=q.removeFirst();for(int d=0;d<8;d++){int x=p[0]+dr[d],y=p[1]+dc[d];if(x>=0&&x<r&&y>=0&&y<c&&a[x][y]!=0&&!seen[x][y]){seen[x][y]=true;q.addLast(new int[]{x,y});}}}return 0;} }
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-j13 — java / full_grid_scan_inside_neighbor_processing

**Input contract:** Binary grid and each valid local neighbor candidate triggers a full grid scan before enqueueing.

**Proposed complexity:** `O((R * C)^2)`

**Expected response:** `estimate`

**Rationale:** Each reachable cell has at most four candidates; in an all-open grid, each candidate incurs R*C scan work, giving O((R*C)^2) total.

**Assumptions:**

- Grid cells are binary/nonnegative so the scan has no early-return exit.
- Four candidates per cell is constant; R and C are dimensions.

**Source SHA-256:** `9d4503a0737f7f0b01504c1d766098ea346b4f0cea97562a19ad91c5e77e5238`

**Exact source:**

```java
import java.util.*; class GridScan { int run(int[][]a,int sr,int sc){int r=a.length,c=a[0].length;boolean[][]seen=new boolean[r][c];int[]dr={1,0,-1,0},dc={0,1,0,-1};Queue<int[]>q=new ArrayDeque<>();seen[sr][sc]=true;q.add(new int[]{sr,sc});while(!q.isEmpty()){int[]p=q.remove();for(int d=0;d<4;d++){int x=p[0]+dr[d],y=p[1]+dc[d];if(x>=0&&x<r&&y>=0&&y<c){for(int i=0;i<r;i++)for(int j=0;j<c;j++)inspect(a[i][j]);if(!seen[x][y]){seen[x][y]=true;q.add(new int[]{x,y});}}}}return 0;} void inspect(int x){} }
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-j14 — java / indexed_array_queue_adjacency_list

**Input contract:** List-of-lists adjacency and an ArrayList queue read with a monotonically increasing head index.

**Proposed complexity:** `O(V + E)`

**Expected response:** `unknown`

**Rationale:** Each vertex is appended/read once and each adjacency entry is scanned once; indexed reads avoid front-removal shifts.

**Assumptions:**

- ArrayList append is amortized O(1); indexed access is O(1).
- The current graph matcher may require Queue/Deque API operations.

**Source SHA-256:** `4846d8fe44b7a56566206c23d60f06c6ca6a25fbfbedf35f483b761280c8e39e`

**Exact source:**

```java
import java.util.*; class IndexedWalk { int run(List<List<Integer>>g,int start){boolean[]seen=new boolean[g.size()];ArrayList<Integer>q=new ArrayList<>();q.add(start);seen[start]=true;for(int head=0;head<q.size();head++){int u=q.get(head);for(int v:g.get(u))if(!seen[v]){seen[v]=true;q.add(v);}}return q.size();} }
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-p01 — python / adjacency_list_dict_deque

**Input contract:** Dictionary with an adjacency list, including empty lists, for each vertex; deque and visited set.

**Proposed complexity:** `O(V + E)`

**Expected response:** `estimate`

**Rationale:** Each vertex is appended and expanded once, and each adjacency entry is scanned once.

**Assumptions:**

- Average O(1) set/dict operations; deque endpoint operations O(1).

**Source SHA-256:** `26399d442c257b39f52c329965aa198a514f5471e6f50ae6cd59b49746caf5be`

**Exact source:**

```python
from collections import deque
def reachable(graph, origin):
    visited = {origin}
    pending = deque([origin])
    while pending:
        current = pending.popleft()
        for neighbor in graph[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                pending.append(neighbor)
    return visited
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-p02 — python / multi_source_duplicate_starts

**Input contract:** S starting entries may include duplicates; graph is an adjacency list.

**Proposed complexity:** `O(S + V + E)`

**Expected response:** `unknown`

**Rationale:** The seed pass costs O(S), then traversal costs O(V+E); no S<=V assumption permits simplification.

**Assumptions:**

- Average O(1) set/dict operations and O(1) deque endpoints.
- Current Python BFS rule has no explicit S-term evidence.

**Source SHA-256:** `6a5c56e6341311208e1e8b4b4a68e580b0f57219b49947a1e603ab5cbe8d5f45`

**Exact source:**

```python
from collections import deque
def spread(graph, seeds):
    marked, line = set(), deque()
    for seed in seeds:
        if seed not in marked:
            marked.add(seed)
            line.append(seed)
    while line:
        node = line.popleft()
        for child in graph.get(node, ()):
            if child not in marked:
                marked.add(child)
                line.append(child)
    return marked
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-p03 — python / disconnected_components_global_visited

**Input contract:** Iterate all vertices and launch a traversal only for unseen roots; one global set.

**Proposed complexity:** `O(V + E)`

**Expected response:** `unknown`

**Rationale:** Each vertex seeds at most once and each adjacency list is expanded once overall.

**Assumptions:**

- Average O(1) hash and queue operations.
- A queue loop is nested under the component driver.

**Source SHA-256:** `d1a395bb31a5fe587457e683ba234de3a52ba62edceb1bce8c20040475e497cb`

**Exact source:**

```python
from collections import deque
def components(graph):
    seen = set()
    for root in graph:
        if root in seen:
            continue
        seen.add(root)
        q = deque([root])
        while q:
            u = q.popleft()
            for v in graph.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    q.append(v)
    return seen
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-p04 — python / boolean_list_visited

**Input contract:** Dense integer IDs, list-of-lists adjacency and a boolean visited list.

**Proposed complexity:** `O(V + E)`

**Expected response:** `unknown`

**Rationale:** Every vertex is enqueued once and every adjacency entry is examined once.

**Assumptions:**

- List indexing and deque operations are O(1).
- Current Python graph matcher may require a set membership guard.

**Source SHA-256:** `1fe2d68938c1c7a6a7dca5f0ce3e05b6684cd0fd2d0a6cf12af9124cf29349b8`

**Exact source:**

```python
from collections import deque
def visit(adj, start):
    used = [False] * len(adj)
    used[start] = True
    q = deque([start])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if not used[v]:
                used[v] = True
                q.append(v)
    return sum(used)
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-p05 — python / adjacency_matrix

**Input contract:** V by V boolean matrix; scan a complete row for each dequeued vertex.

**Proposed complexity:** `O(V^2)`

**Expected response:** `unknown`

**Rationale:** At most V rows are processed, each with V entries.

**Assumptions:**

- Dense matrix indexing is O(1).
- A list subscript alone must not be treated as adjacency-list evidence.

**Source SHA-256:** `476d8169b8ac6af72b6070c269b1b797138c3b31ba341534a1f8654f44c976e5`

**Exact source:**

```python
from collections import deque
def matrix_reach(matrix, source):
    n = len(matrix)
    seen = [False] * n
    seen[source] = True
    q = deque([source])
    while q:
        u = q.popleft()
        for v, connected in enumerate(matrix[u]):
            if connected and not seen[v]:
                seen[v] = True
                q.append(v)
    return sum(seen)
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-p06 — python / repeated_bfs_per_request

**Input contract:** A new BFS is performed for each of Q requests.

**Proposed complexity:** `O(Q * (V + E))`

**Expected response:** `unknown`

**Rationale:** Each traversal may scan V vertices and E entries; the outer loop multiplies the work by Q.

**Assumptions:**

- Q is independent of V.
- Average O(1) hash and deque operations.

**Source SHA-256:** `9352fa157deb34247aceb3b63f29004c84cdd8aa430926d143d577f7592fc03b`

**Exact source:**

```python
from collections import deque
def answer(graph, requests):
    total = 0
    for source in requests:
        seen, q = {source}, deque([source])
        while q:
            u = q.popleft()
            total += 1
            for v in graph.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    q.append(v)
    return total
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-p07 — python / neighbor_helper_contract

**Input contract:** neighbors(node) is contractually an iterator over that vertex's adjacency entries.

**Proposed complexity:** `O(V + E)`

**Expected response:** `unknown`

**Rationale:** The contract gives O(E) total neighbor iteration plus O(V) queue work, but the selected method delegates the core traversal source.

**Assumptions:**

- The helper contract is supplied to the user.
- The current analyzer does not expand helper implementations.

**Source SHA-256:** `28e2b5a872bd71470481770cf9922d9d98ca4985c0726f4b97f0ac580360b52d`

**Exact source:**

```python
from collections import deque
def walk(graph, source):
    seen, q = {source}, deque([source])
    while q:
        node = q.popleft()
        for neighbor in graph.neighbors(node):
            if neighbor not in seen:
                seen.add(neighbor)
                q.append(neighbor)
    return len(seen)
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-p08 — python / list_queue_front_removal

**Input contract:** Adjacency list, but FIFO queue uses list.pop(0).

**Proposed complexity:** `O(V^2 + E)`

**Expected response:** `unknown`

**Rationale:** Each of at most V removals may shift O(V) elements, costing O(V^2); neighbor scans add O(E).

**Assumptions:**

- Python list front removal shifts remaining entries.
- Average O(1) visited/dict operations.

**Source SHA-256:** `2b9b3f0617fd144adaabcd13987f293ea1e843da2e1d65bfdcd413396a02c145`

**Exact source:**

```python
def walk(graph, start):
    seen, q = {start}, [start]
    while q:
        node = q.pop(0)
        for nxt in graph.get(node, ()):
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return len(seen)
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-p09 — python / directed_tree_without_visited

**Input contract:** Input contract guarantees a directed rooted tree oriented away from root; no seen set.

**Proposed complexity:** `O(V + E)`

**Expected response:** `unknown`

**Rationale:** Unique root paths ensure each vertex is queued once; every child edge is examined once.

**Assumptions:**

- Acyclicity and orientation are external preconditions not established by the method body.

**Source SHA-256:** `24e7bbb638cdf652bcec9cbbe057852bc001e982f03956017590f92746226031`

**Exact source:**

```python
from collections import deque
def tree_size(children, root):
    q, count = deque([root]), 0
    while q:
        parent = q.popleft()
        count += 1
        for child in children.get(parent, ()):
            q.append(child)
    return count
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-p10 — python / queue_worklist_not_graph

**Input contract:** A queue drains independent jobs; there is no graph or neighbor relation.

**Proposed complexity:** `O(N)`

**Expected response:** `unknown`

**Rationale:** Every item is removed once with constant work.

**Assumptions:**

- This is a queue-only non-BFS control case.

**Source SHA-256:** `19e9a6edcbd0e069665f9c363bfb7f8e55004c2b0cfe5c842abe0126b8e0d1ec`

**Exact source:**

```python
from collections import deque
def jobs(items):
    pending = deque(items)
    done = 0
    while pending:
        pending.popleft()
        done += 1
    return done
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-p11 — python / grid_four_neighbor_component_sweep

**Input contract:** Rectangular binary grid; full component sweep and four fixed offsets.

**Proposed complexity:** `O(R * C)`

**Expected response:** `estimate`

**Rationale:** The outer sweep checks each cell once; each active cell is enqueued once and makes four checks.

**Assumptions:**

- Average O(1) set operations; four is constant.

**Source SHA-256:** `de3b72257eaba0d35e91b18c0f16dc424b37dea631ef930cfe7c23819dd65edb`

**Exact source:**

```python
from collections import deque
def regions(board):
    rows, cols = len(board), len(board[0])
    seen, total = set(), 0
    for r in range(rows):
        for c in range(cols):
            if not board[r][c] or (r,c) in seen:
                continue
            total += 1
            seen.add((r,c))
            q = deque([(r,c)])
            while q:
                x,y = q.popleft()
                for dx,dy in ((0,1),(1,0),(0,-1),(-1,0)):
                    a,b = x+dx,y+dy
                    if 0<=a<rows and 0<=b<cols and board[a][b] and (a,b) not in seen:
                        seen.add((a,b))
                        q.append((a,b))
    return total
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-p12 — python / grid_eight_neighbor_fixed_tuple

**Input contract:** Rectangular grid with a fixed tuple of eight surrounding offsets.

**Proposed complexity:** `O(R * C)`

**Expected response:** `unknown`

**Rationale:** Every cell expands once and examines eight constant-time neighbors.

**Assumptions:**

- Eight is constant; current Python grid rule may only support its four-neighbor form.

**Source SHA-256:** `f32093739f1765879464563a9110d6eeab439458a992e24ec1736d7b5cf18ef9`

**Exact source:**

```python
from collections import deque
def flood(image, start):
    h,w = len(image),len(image[0])
    seen,q = {start},deque([start])
    dirs = ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1))
    while q:
        r,c = q.popleft()
        for dr,dc in dirs:
            nr,nc = r+dr,c+dc
            if 0<=nr<h and 0<=nc<w and image[nr][nc] and (nr,nc) not in seen:
                seen.add((nr,nc))
                q.append((nr,nc))
    return len(seen)
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-p13 — python / full_grid_scan_inside_neighbor_processing

**Input contract:** Each valid local neighbor candidate triggers a complete grid scan before discovery.

**Proposed complexity:** `O((R * C)^2)`

**Expected response:** `unknown`

**Rationale:** A constant number of candidates per dequeued cell each cost R*C; across R*C cells this is quadratic in the cell count.

**Assumptions:**

- Four local candidates is constant.
- The full-grid scan is nested inside neighbor processing.

**Source SHA-256:** `776aa08ef1fd2b09f066e98854f6626a2488d4312f6d1fddd4fc3df50356a63c`

**Exact source:**

```python
from collections import deque
def scan_flood(grid, start):
    rows, cols = len(grid), len(grid[0])
    seen, q = {start}, deque([start])
    while q:
        r,c = q.popleft()
        for nr,nc in ((r-1,c),(r+1,c),(r,c-1),(r,c+1)):
            if 0<=nr<rows and 0<=nc<cols:
                for i in range(rows):
                    for j in range(cols):
                        inspect(grid[i][j])
                if (nr,nc) not in seen:
                    seen.add((nr,nc))
                    q.append((nr,nc))
    return len(seen)
def inspect(value):
    return value
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---

## axioma-bfs-v2-p14 — python / heap_ordered_weighted_traversal

**Input contract:** Heap-based shortest-path traversal over weighted adjacency lists; not FIFO BFS.

**Proposed complexity:** `O((V + E) * log(V + E))`

**Expected response:** `unknown`

**Rationale:** With nonnegative weights and lazy stale-entry deletion, up to O(E) heap entries can be inserted and removed, each at logarithmic heap cost.

**Assumptions:**

- Weights are nonnegative and stale heap entries are skipped.
- A binary heap may contain O(E) entries; no simple-graph bound on E is assumed.
- This is a non-BFS priority-queue near-miss.

**Source SHA-256:** `7e2474a5b0f9bff24722c54759bd01089326b41d7a2c3bab919697f24fd7824b`

**Exact source:**

```python
import heapq
def shortest(network, source):
    distance, heap = {source: 0}, [(0, source)]
    while heap:
        cost, node = heapq.heappop(heap)
        if cost != distance[node]:
            continue
        for neighbor, weight in network.get(node, ()):
            candidate = cost + weight
            if candidate < distance.get(neighbor, float('inf')):
                distance[neighbor] = candidate
                heapq.heappush(heap, (candidate, neighbor))
    return distance
```

**Reviewer decision:** pending

**Reviewer rationale:** pending

---


## Proposed consolidated review — awaiting final owner confirmation

**This proposal is not an approved or frozen gold-label set.** The original `review-packet.jsonl` and `manifest.json` remain unchanged. No analyzer was run against these 28 cases. Confirm or correct this complete case-level review before labels are frozen.

Final tally: **20 approve, 8 revise, 0 exclude**. P11 remains approved with expected response `estimate`.

| Case | Decision | Mathematical complexity | Expected analyzer response | Review note / input-contract clarification |
|---|---|---|---|---|
| axioma-bfs-v2-j01 | revise | `O(V + E)` | `estimate` | Specify HashMap or equivalent expected O(1) backing-map lookup and require a valid root. |
| axioma-bfs-v2-j02 | approve | `O(S + V + E)` | `estimate` | Add input condition: every starting vertex is a valid graph vertex. Duplicates may occur and S need not be <= V. |
| axioma-bfs-v2-j03 | revise | `O(V + E)` | `unknown` | Add assumption: Map operations have expected O(1) cost (for example, HashMap backing). Keep expected response unknown because the component-driver pattern is outside the stated bounded recognizer. |
| axioma-bfs-v2-j04 | approve | `O(V + E)` | `unknown` | No algorithm-label correction; see recorded input assumptions.; Array of per-vertex neighbor lists with dense integer IDs 0 through V-1; every referenced ID and start s is in [0,V). |
| axioma-bfs-v2-j05 | approve | `O(V^2)` | `estimate` | No algorithm-label correction; see recorded input assumptions.; Non-empty V by V boolean matrix; valid source s in [0,V); each dequeued node scans every column. |
| axioma-bfs-v2-j06 | revise | `O(Q * (V + E))` | `unknown` | Define Q as starts.length and specify expected O(1) map operations. |
| axioma-bfs-v2-j07 | approve | `O((V + E) log V)` | `unknown` | No algorithm-label correction; see recorded input assumptions. |
| axioma-bfs-v2-j08 | revise | `O(V + V*E) = O(V*(E + 1))` | `unknown` | Define n = V and correct the complete bound to O(V + VE) = O(V(E+1)); state O(VE) is the simplified form when E >= 1. |
| axioma-bfs-v2-j09 | approve | `O(V^2 + E)` | `unknown` | Explicitly state in the input contract that n = V. |
| axioma-bfs-v2-j10 | revise | `O(V + E)` | `unknown` | Add assumption: the outer children collection supports O(1) indexed access, such as ArrayList. Retain the external directed rooted-tree guarantee. |
| axioma-bfs-v2-j11 | approve | `O(R * C)` | `estimate` | No algorithm-label correction; see recorded input assumptions.; ; grid is non-empty and rectangular (R >= 1, C >= 1); starting coordinate is in bounds (0 <= row < R, 0 <= col < C) |
| axioma-bfs-v2-j12 | approve | `O(R * C)` | `estimate` | No algorithm-label correction; see recorded input assumptions.; ; grid is non-empty and rectangular (R >= 1, C >= 1); starting coordinate is in bounds (0 <= row < R, 0 <= col < C) |
| axioma-bfs-v2-j13 | revise | `O((R * C)^2)` | `estimate` | Correct the rationale: every in-bounds neighbor candidate triggers a full-grid scan; grid values do not control traversal.; ; grid is non-empty and rectangular (R >= 1, C >= 1); starting coordinate is in bounds (0 <= row < R, 0 <= col < C) |
| axioma-bfs-v2-j14 | revise | `O(V + E)` | `unknown` | Add assumption: g supports O(1) indexed access, such as an ArrayList of adjacency lists. The monotonically increasing ArrayList queue head avoids remove(0) shifts. |
| axioma-bfs-v2-p01 | approve | `O(V + E)` | `estimate` | No algorithm-label correction; see recorded input assumptions. |
| axioma-bfs-v2-p02 | approve | `O(S + V + E)` | `unknown` | No algorithm-label correction; see recorded input assumptions. |
| axioma-bfs-v2-p03 | approve | `O(V + E)` | `unknown` | No algorithm-label correction; see recorded input assumptions. |
| axioma-bfs-v2-p04 | approve | `O(V + E)` | `unknown` | No algorithm-label correction; see recorded input assumptions.; Dense integer IDs 0 through V-1; every adjacency reference and start is in [0,V), so boolean visited-list indexing is valid. |
| axioma-bfs-v2-p05 | approve | `O(V^2)` | `unknown` | No algorithm-label correction; see recorded input assumptions.; Non-empty V by V boolean matrix; valid source in [0,V); scan a complete row for each dequeued vertex. |
| axioma-bfs-v2-p06 | approve | `O(Q * (V + E))` | `unknown` | No algorithm-label correction; see recorded input assumptions. |
| axioma-bfs-v2-p07 | revise | `O(V + E)` | `unknown` | Specify O(1) iterator creation, O(deg(node)) iteration, and no hidden full-graph scans. |
| axioma-bfs-v2-p08 | approve | `O(V^2 + E)` | `unknown` | No algorithm-label correction; see recorded input assumptions. |
| axioma-bfs-v2-p09 | approve | `O(V + E)` | `unknown` | No algorithm-label correction; see recorded input assumptions. |
| axioma-bfs-v2-p10 | approve | `O(N)` | `unknown` | No algorithm-label correction; see recorded input assumptions. |
| axioma-bfs-v2-p11 | approve | `O(R * C)` | `estimate` | Approve; component-sweep estimate supported by existing recognizer/test inspection; non-empty rectangular grid; no start coordinate. |
| axioma-bfs-v2-p12 | approve | `O(R * C)` | `unknown` | No algorithm-label correction; see recorded input assumptions.; ; grid is non-empty and rectangular (R >= 1, C >= 1); starting coordinate is in bounds (0 <= row < R, 0 <= col < C) |
| axioma-bfs-v2-p13 | approve | `O((R * C)^2)` | `unknown` | No algorithm-label correction; see recorded input assumptions.; ; grid is non-empty and rectangular (R >= 1, C >= 1); starting coordinate is in bounds (0 <= row < R, 0 <= col < C) |
| axioma-bfs-v2-p14 | approve | `O((V + E) * log(V + E))` | `unknown` | No algorithm-label correction; see recorded input assumptions. |

### Requested input contracts recorded

- **J04 and P04:** Vertex IDs are dense integers in `[0,V)`; all neighbor IDs and the starting vertex are valid and within visited-array/list bounds.
- **J05 and P05:** The matrix is square and non-empty; the source vertex is valid.
- **J11, J12, J13, P11, P12, and P13:** The grid is non-empty and rectangular. For cases with an explicit starting coordinate, it is in bounds. P11 is a full component sweep and has no supplied start coordinate.

### J08 correction

J08 allocates `boolean[n] seen` (O(n)), then dequeues at most V vertices and scans E edge records for each (O(VE)). Given `n = V`, total time is O(V + VE) = O(V(E + 1)); when E >= 1, O(VE) is the common simplified form. Expected analyzer response remains `unknown`.

### P11 recognizer determination

P11 retains expected response `estimate`. The current Python `_is_grid_bfs` implementation and existing `test_grid_bfs_supports_rectangular_ranges_and_reports_dimensions` regression test cover the component-sweep structure. This is source/test inspection only, not an analyzer run on this packet.

### P14 clarification

The accepted label remains O((V + E) log(V + E)); O(V + E log(E + 1)) is a tighter explanatory bound for the described lazy heap under its assumptions. Expected analyzer response remains `unknown`.

### Confirmation gate

All 28 source hashes match the original packet. The proposed labels remain unapproved and unfrozen; analyzer execution remains paused.
