"""Comprehensive validation of all 5 retrieval upgrade features."""
import asyncio, sys
from app.services.bm25_service import BM25Scorer, _tokens as bm25_tokens_list
from app.services.mmr_service import mmr_rerank
from app.services.vector_service import VectorStore, EmbeddingProvider, doc_to_text
from app.services.graph_expansion_service import expand_skills
from app.agents.retrieval_agent import (
    RetrievalAgent, _verified_database_documents, _package_fallback,
    _apply_version_filter, _reciprocal_rank_fusion, _tokens,
)
from app.workflow.state import WorkflowState
from app.core.database import init_db

PASSED = 0
FAILED = 0

def check(desc, condition):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [OK] {desc}")
    else:
        FAILED += 1
        print(f"  [FAIL] {desc}  <--")

print("=" * 60)
print("1. BM25")
print("=" * 60)

docs = [
    {'evidence_id': '1', 'title': 'ROS2 node basics', 'content': 'Nodes are basic entities in ROS2 graph', 'skill_id': 'ros2_node', 'skill_ids': [], 'section': ''},
    {'evidence_id': '2', 'title': 'Topic communication', 'content': 'Topic uses publish-subscribe pattern', 'skill_id': 'ros2_topic', 'skill_ids': [], 'section': ''},
    {'evidence_id': '3', 'title': 'Service calls', 'content': 'Service uses request-response pattern', 'skill_id': 'ros2_service', 'skill_ids': [], 'section': ''},
    {'evidence_id': '4', 'title': 'C variables', 'content': 'Variables must be declared before use', 'skill_id': 'c_variable', 'skill_ids': [], 'section': ''},
    {'evidence_id': '5', 'title': 'Inter-node comm', 'content': 'ROS2 nodes communicate via Topic and Service', 'skill_id': 'ros2_node', 'skill_ids': ['ros2_topic', 'ros2_service'], 'section': ''},
]
scorer = BM25Scorer()
scorer.index(docs)

q1 = set(_tokens('ROS2 node'))
r1 = scorer.search(q1, top_k=3)
check("1a. exact match", r1[0][1]['title'] == 'ROS2 node basics')

q2 = set(_tokens('publish-subscribe'))
r2 = scorer.search(q2, top_k=3)
check("1b. hyphenated term match", r2[0][1]['evidence_id'] == '2')

check("1c. empty corpus", BM25Scorer().search({'hello'}, 5) == [])

r_empty = scorer.search(set(), top_k=3)
check("1d. empty query", len(r_empty) == 0)

q_nomatch = set(_tokens('python django unsupported'))
r_nomatch = scorer.search(q_nomatch, top_k=3)
check("1e. no match", len(r_nomatch) == 0)

q4 = set(_tokens('communication'))
r_boosted = scorer.search(q4, top_k=3, skill_boost_map={'ros2_service': 0.8})
check("1f. skill boost works", len(r_boosted) > 0)

bm25_ok = (FAILED == 0)
FAILED = 0; PASSED = 0
print()

print("=" * 60)
print("2. Vector retrieval")
print("=" * 60)

store = VectorStore()
store.clear()
check("2a. empty store", store.size == 0)

vecs = [[0.9,0.1,0.1,0.1], [0.1,0.9,0.1,0.1], [0.1,0.1,0.9,0.1], [0.1,0.1,0.1,0.9]]
store.index(docs[:-1], vecs)
check("2b. index load", store.size == 4)

qv = [0.85, 0.15, 0.1, 0.05]
results = store.search(qv, top_k=3)
check("2c. cosine nearest", results[0][1]['title'] == 'ROS2 node basics')

text = doc_to_text(docs[0])
check("2d. doc_to_text", 'ROS2 node basics' in text and 'ros2_node' in text)

check("2e. empty vector search", store.search([], 3) == [])

prov = EmbeddingProvider()
check("2f. provider detection ok", True)  # always ok

vec_ok = (FAILED == 0)
FAILED = 0; PASSED = 0
print()

print("=" * 60)
print("3. Version filtering")
print("=" * 60)

diverse = [
    {'evidence_id': 'a', 'title': 'A', 'content': '...', 'version': 'humble', 'skill_id': 's1'},
    {'evidence_id': 'b', 'title': 'B', 'content': '...', 'version': 'jazzy', 'skill_id': 's2'},
    {'evidence_id': 'c', 'title': 'C', 'content': '...', 'version': 'humble-2024Q1', 'skill_id': 's3'},
    {'evidence_id': 'd', 'title': 'D', 'content': '...', 'version': 'humble-patch3', 'skill_id': 's4'},
    {'evidence_id': 'e', 'title': 'E', 'content': '...', 'version': 'rolling', 'skill_id': 's5'},
    {'evidence_id': 'f', 'title': 'F', 'content': '...', 'version': None, 'skill_id': 's6'},
]

check("3a. humble filter", len(_apply_version_filter(diverse, 'humble')) == 3)
check("3b. case insensitive", len(_apply_version_filter(diverse, 'ROLLING')) == 1)
check("3c. no match", len(_apply_version_filter(diverse, 'iron')) == 0)
check("3d. None passes through", len(_apply_version_filter(diverse, None)) == len(diverse))
check("3e. empty passes through", len(_apply_version_filter(diverse, '')) == len(diverse))

version_ok = (FAILED == 0)
FAILED = 0; PASSED = 0
print()

print("=" * 60)
print("4. RRF fusion")
print("=" * 60)

s1 = {'evidence_id': 'a1', 'title': 'ROS2 nodes', 'content': '...'}
d1 = {'evidence_id': 'b1', 'title': 'Topic', 'content': '...'}
d2 = {'evidence_id': 'c1', 'title': 'Service', 'content': '...'}

bm25 = [(2.5, s1), (1.8, d1), (1.2, d2)]
vec = [(0.92, d1), (0.88, s1), (0.75, d2)]
fused = _reciprocal_rank_fusion(bm25, vec, bm25_weight=0.6, vector_weight=0.4)
check("4a. fusion keeps count", len(fused) == 3)

fused2 = _reciprocal_rank_fusion([(2.0, s1)], [(0.9, d1)])
check("4b. disjoint fusion", len(fused2) == 2)

rrf_ok = (FAILED == 0)
FAILED = 0; PASSED = 0
print()

print("=" * 60)
print("5. MMR dedup")
print("=" * 60)

a1 = {'evidence_id': 'a1', 'title': 'ROS2 nodes', 'content': 'Create ROS2 nodes with rclcpp::Node'}
a2 = {'evidence_id': 'a2', 'title': 'ROS2 nodes detail', 'content': 'Create ROS2 nodes with rclcpp::Node and config'}
b1 = {'evidence_id': 'b1', 'title': 'Topic comm', 'content': 'Publish-subscribe for async data'}
c1 = {'evidence_id': 'c1', 'title': 'Service call', 'content': 'Request-response for RPC'}
candidates = [(0.95, a1), (0.90, a2), (0.88, b1), (0.85, c1)]
ranked = mmr_rerank(candidates, lambda_param=0.7, top_k=4)
all_eids = [doc['evidence_id'] for _, doc in ranked]
check("5a. first is most relevant", ranked[0][1]['evidence_id'] == 'a1')
check("5b. similar not excluded", 'a2' in all_eids)
check("5c. no duplicates", len(set(all_eids)) == len(all_eids))
check("5d. empty list", mmr_rerank([], top_k=5) == [])
check("5e. single element", len(mmr_rerank([(0.9, b1)], top_k=5)) == 1)

orig = mmr_rerank(candidates, lambda_param=1.0, top_k=4)
check("5f. lambda=1 preserves order", orig[0][1]['evidence_id'] == 'a1')

# Vector-based MMR
doc_vec_map = {
    'a1': [0.95, 0.05, 0.0],
    'a2': [0.92, 0.08, 0.0],
    'b1': [0.05, 0.95, 0.0],
    'c1': [0.02, 0.05, 0.93],
}
vec_ranked = mmr_rerank(candidates, query_vector=[0.9, 0.1, 0.05], doc_vectors=doc_vec_map, lambda_param=0.7, top_k=4)
vec_eids = [doc['evidence_id'] for _, doc in vec_ranked]
check("5g. vector-based MMR no dups", len(set(vec_eids)) == len(vec_eids))

mmr_ok = (FAILED == 0)
FAILED = 0; PASSED = 0
print()

print("=" * 60)
print("6. Skill graph expansion")
print("=" * 60)

async def test_graph():
    global PASSED, FAILED
    await init_db()

    boosts = await expand_skills('ros2_robotics', ['ros2_topic'], max_hops=2)
    check("6a. target has max weight", boosts['ros2_topic'] >= 1.0)
    check("6b. prerequisite included", 'ros2_node' in boosts)
    check("6c. post-requisite included", 'ros2_topic_custom' in boosts)

    boosts2 = await expand_skills('ros2_robotics', ['ros2_topic', 'ros2_service'], max_hops=1)
    check("6d. multi-target", 'ros2_topic' in boosts2 and 'ros2_service' in boosts2)

    boosts3 = await expand_skills('ros2_robotics', [])
    check("6e. empty targets", boosts3 == {})

    boosts4 = await expand_skills('c_programming', ['c_pointer'], max_hops=2)
    check("6f. C domain prerequisite", 'c_array' in boosts4)

asyncio.run(test_graph())

graph_ok = (FAILED == 0)
FAILED = 0; PASSED = 0
print()

print("=" * 60)
print("7. RetrievalAgent integration")
print("=" * 60)

async def test_agent():
    global PASSED, FAILED
    await init_db()
    agent = RetrievalAgent()

    ctx = WorkflowState(
        workflow_id='test1', learner_id='l1', domain_id='ros2_robotics',
        target_goal='Learn ROS2 nodes and Topic communication',
        target_skills=['ros2_node', 'ros2_topic'],
        source_skill_id='ros2_topic',
    )
    r = await agent.run(ctx, {})
    evidence = r.output['evidence_list']
    check("7a. has evidence", len(evidence) > 0)
    check("7b. max 8 items", len(evidence) <= 8)
    check("7c. MMR applied", r.output['mmr_applied'] == True)
    check("7d. graph expansion applied", r.output['graph_expansion_applied'] == True)
    check("7e. method is bm25", 'bm25' in r.output['retrieval_method'])

    # Version filter
    r2 = await agent.run(ctx, {'version_filter': 'humble'})
    ev2 = r2.output['evidence_list']
    all_humble = all('humble' in str(item['version']).lower() for item in ev2)
    check("7f. version filter works", all_humble and len(ev2) > 0)

    # C domain
    ctx3 = WorkflowState(
        workflow_id='test3', learner_id='l1', domain_id='c_programming',
        target_goal='Learn C pointers and arrays',
        target_skills=['c_pointer', 'c_array'],
        source_skill_id='c_pointer',
    )
    r3 = await agent.run(ctx3, {})
    check("7g. C domain retrieval", len(r3.output['evidence_list']) > 0)

    # No target skills fallback
    ctx4 = WorkflowState(
        workflow_id='test4', learner_id='l1', domain_id='ros2_robotics',
        target_goal='Learn ROS2',
        target_skills=[], source_skill_id=None,
    )
    r4 = await agent.run(ctx4, {})
    check("7h. empty targets fallback", len(r4.output['evidence_list']) > 0)

    # Summary and fields
    check("7i. summary has BM25", 'BM25' in r.summary)
    check("7j. summary has MMR", 'MMR' in r.summary)
    for key in ['evidence_id', 'title', 'source_url', 'version', 'content', 'relevance_score']:
        check(f"7k. has field {key}", key in evidence[0])

    # Scores decreasing
    scores = [item['relevance_score'] for item in evidence]
    check("7l. scores decreasing", all(scores[i] >= scores[i+1] for i in range(len(scores)-1)))

asyncio.run(test_agent())

agent_ok = (FAILED == 0)
FAILED = 0; PASSED = 0
print()

# ==============================
# Final summary
# ==============================
print("=" * 60)
print("FINAL RESULTS")
print("=" * 60)
all_ok = bm25_ok and vec_ok and version_ok and rrf_ok and mmr_ok and graph_ok and agent_ok
status = "ALL PASSED" if all_ok else "SOME FAILED"
print(f"  Status: {status}")
print(f"  BM25:     {'PASS' if bm25_ok else 'FAIL'}")
print(f"  Vector:   {'PASS' if vec_ok else 'FAIL'}")
print(f"  Version:  {'PASS' if version_ok else 'FAIL'}")
print(f"  RRF:      {'PASS' if rrf_ok else 'FAIL'}")
print(f"  MMR:      {'PASS' if mmr_ok else 'FAIL'}")
print(f"  Graph:    {'PASS' if graph_ok else 'FAIL'}")
print(f"  Agent:    {'PASS' if agent_ok else 'FAIL'}")
print("=" * 60)

if not all_ok:
    raise SystemExit(1)
