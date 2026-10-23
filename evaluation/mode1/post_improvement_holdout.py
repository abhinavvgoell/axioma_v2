"""Post-improvement diagnostic set; do not use these cases to tune the analyzer."""

from pathlib import Path
import sys

sys.path.extend([
    str(Path(__file__).resolve().parents[2] / "services" / "api" / "src"),
    str(Path(__file__).resolve().parents[2] / "services" / "worker" / "src"),
])

from axioma_worker.python_complexity import analyze_python_complexity


CASES = [
    ("01", "linear", "def solve(nums,target):\n s=set()\n for x in nums:\n  if target-x in s:return True\n  s.add(x)\n return False"),
    ("02", "linear", "def solve(nums,queries):\n p=[0]\n for x in nums:p.append(p[-1]+x)\n return [p[r]-p[l] for l,r in queries]"),
    ("03", "quadratic", "def solve(nums):\n for i in range(len(nums)):\n  m=i\n  for j in range(i+1,len(nums)):\n   if nums[j]<nums[m]:m=j\n  nums[i],nums[m]=nums[m],nums[i]\n return nums"),
    ("04", "n_log_n", "def solve(nums):\n nums.sort()\n l,r=0,len(nums)-1\n while l<r:\n  t=nums[l]+nums[r]\n  if t==0:return True\n  if t<0:l+=1\n  else:r-=1\n return False"),
    ("05", "constant", "def solve():\n c=0\n for row in range(8):\n  for col in range(8):c+=row^col\n return c"),
    ("06", "linear", "def solve(nums,limit):\n left=total=best=0\n for right,value in enumerate(nums):\n  total+=value\n  while total>limit:\n   total-=nums[left];left+=1\n  best=max(best,right-left+1)\n return best"),
    ("07", "linear", "def solve(nums):\n answer=[-1]*len(nums);stack=[]\n for i,value in enumerate(nums):\n  while stack and nums[stack[-1]]<value:answer[stack.pop()]=value\n  stack.append(i)\n return answer"),
    ("08", "linear", "from collections import deque\ndef solve(nums,width):\n q=deque();ans=[]\n for i,value in enumerate(nums):\n  while q and q[0]<=i-width:q.popleft()\n  while q and nums[q[-1]]<=value:q.pop()\n  q.append(i)\n  if i>=width-1:ans.append(nums[q[0]])\n return ans"),
    ("09", "logarithmic", "def solve(nums,target):\n l,r=0,len(nums)\n while l<r:\n  mid=(l+r)//2\n  if nums[mid]<target:l=mid+1\n  else:r=mid\n return l"),
    ("10", "logarithmic", "def solve(left,right,score):\n while right-left>2:\n  third=(right-left)//3;first=left+third;second=right-third\n  if score(first)<score(second):left=first\n  else:right=second\n return max(range(left,right+1),key=score)"),
    ("11", "n_log_n", "import heapq\ndef solve(nums,k):\n h=nums[:];heapq.heapify(h);result=[]\n for _ in range(min(k,len(h))):result.append(heapq.heappop(h))\n return result"),
    ("12", "linear", "def solve(head):\n slow=fast=head\n while fast and fast.next:\n  slow=slow.next;fast=fast.next.next\n  if slow is fast:return True\n return False"),
    ("13", "linear", "def solve(root):\n if root is None:return 0\n return 1+solve(root.left)+solve(root.right)"),
    ("14", "conditional_tree", "def solve(root,target):\n if root is None or root.value==target:return root\n if target<root.value:return solve(root.left,target)\n return solve(root.right,target)"),
    ("15", "graph", "from collections import deque\ndef solve(graph,start):\n seen={start};q=deque([start]);order=[]\n while q:\n  node=q.popleft();order.append(node)\n  for neighbor in graph[node]:\n   if neighbor not in seen:seen.add(neighbor);q.append(neighbor)\n return order"),
    ("16", "graph", "def solve(graph,start):\n seen=set()\n def visit(node):\n  if node in seen:return\n  seen.add(node)\n  for neighbor in graph[node]:visit(neighbor)\n visit(start)\n return seen"),
    ("17", "graph", "from collections import deque\ndef solve(graph,indegree):\n q=deque(i for i,d in enumerate(indegree) if d==0);order=[]\n while q:\n  node=q.popleft();order.append(node)\n  for neighbor in graph[node]:\n   indegree[neighbor]-=1\n   if indegree[neighbor]==0:q.append(neighbor)\n return order"),
    ("18", "heap_graph", "import heapq\ndef solve(graph,start):\n dist={start:0};h=[(0,start)]\n while h:\n  cost,node=heapq.heappop(h)\n  if cost!=dist[node]:continue\n  for neighbor,weight in graph[node]:\n   new=cost+weight\n   if new<dist.get(neighbor,float('inf')):dist[neighbor]=new;heapq.heappush(h,(new,neighbor))\n return dist"),
    ("19", "union_find", "def solve(n,edges):\n parent=list(range(n));size=[1]*n\n def find(x):\n  while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]\n  return x\n for a,b in edges:\n  ra,rb=find(a),find(b)\n  if ra!=rb:\n   if size[ra]<size[rb]:ra,rb=rb,ra\n   parent[rb]=ra;size[ra]+=size[rb]\n return len({find(i) for i in range(n)})"),
    ("20", "linear", "def solve(costs):\n if not costs:return 0\n previous,current=0,costs[0]\n for cost in costs[1:]:previous,current=current,cost+min(previous,current)\n return current"),
    ("21", "quadratic", "from functools import cache\ndef solve(text,pattern):\n @cache\n def match(i,j):\n  if j==len(pattern):return i==len(text)\n  first=i<len(text) and pattern[j] in (text[i],'?')\n  if j+1<len(pattern) and pattern[j+1]=='*':return match(i,j+2) or (first and match(i+1,j))\n  return first and match(i+1,j+1)\n return match(0,0)"),
    ("22", "quadratic", "def solve(first,second):\n rows,cols=len(first),len(second);table=[[0]*(cols+1) for _ in range(rows+1)]\n for i in range(rows+1):table[i][0]=i\n for j in range(cols+1):table[0][j]=j\n for i in range(1,rows+1):\n  for j in range(1,cols+1):table[i][j]=min(table[i-1][j]+1,table[i][j-1]+1,table[i-1][j-1]+(first[i-1]!=second[j-1]))\n return table[rows][cols]"),
    ("23", "factorial", "def solve(nums):\n result=[];used=[False]*len(nums);path=[]\n def build():\n  if len(path)==len(nums):result.append(path[:]);return\n  for i,value in enumerate(nums):\n   if not used[i]:used[i]=True;path.append(value);build();path.pop();used[i]=False\n build();return result"),
    ("24", "exponential", "def solve(nums,target):\n def search(index,total):\n  if index==len(nums):return total==target\n  return search(index+1,total) or search(index+1,total+nums[index])\n return search(0,0)"),
    ("25", "quadratic", "def solve(matrix):\n total=0\n for row in matrix:\n  for value in row:total+=value\n return total"),
    ("26", "linear", "def solve(matrix,target):\n if not matrix or not matrix[0]:return False\n row,col=0,len(matrix[0])-1\n while row<len(matrix) and col>=0:\n  value=matrix[row][col]\n  if value==target:return True\n  if value>target:col-=1\n  else:row+=1\n return False"),
    ("27", "linear", "def solve(words):\n root={}\n for word in words:\n  node=root\n  for char in word:node=node.setdefault(char,{})\n  node['']=True\n return root"),
    ("28", "linear", "def solve(text):\n n=len(text);z=[0]*n;left=right=0\n for i in range(1,n):\n  if i<=right:z[i]=min(right-i+1,z[i-left])\n  while i+z[i]<n and text[z[i]]==text[i+z[i]]:z[i]+=1\n  if i+z[i]-1>right:left,right=i,i+z[i]-1\n return z"),
    ("29", "n_log_log_n", "def solve(n):\n prime=[True]*(n+1)\n if n>=0:prime[0]=False\n if n>=1:prime[1]=False\n p=2\n while p*p<=n:\n  if prime[p]:\n   for multiple in range(p*p,n+1,p):prime[multiple]=False\n  p+=1\n return [i for i,value in enumerate(prime) if value]"),
    ("30", "logarithmic", "def solve(values,left,right):\n total=0\n while left>0:left-=left&-left;total+=values[left]\n while right>0:right-=right&-right;total+=values[right]\n return total"),
]


def bucket(estimate: str) -> str:
    if estimate.startswith("O(1)"):
        return "constant"
    if estimate == "O(log n)":
        return "logarithmic"
    if estimate in {"O(n)", "O(m + n)"}:
        return "linear"
    if estimate == "O(n log n)":
        return "n_log_n"
    if estimate == "O(n^2)":
        return "quadratic"
    if estimate.startswith("O(2^n)"):
        return "exponential"
    if estimate == "O(V + E)":
        return "graph"
    if estimate == "O((V + E) log V)":
        return "heap_graph"
    return "unknown"


for identifier, expected, code in CASES:
    result = analyze_python_complexity(code, "solve")
    predicted = bucket(result.estimate)
    print(f"{identifier}\t{expected}\t{predicted}\t{result.estimate}\t{result.method}")
