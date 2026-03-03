"""
Test script for the 3-tier hybrid semantic router with 4 agents.

Tests routing across all tiers for:
  Retrieval, API, Helpdesk (NEW), and Workflow agents

Run: python router/test_semantic_router.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router.graph import route_query

def check(query: str, expected: str, tier: str):
    state  = {"query": query, "answer": "", "agent_used": "", "sources": []}
    result = route_query(state)
    status = "✅ PASS" if result == expected else f"❌ FAIL (got: {result})"
    print(f"  {status}  [{tier}] \"{query[:65]}\"")
    return result == expected


print("\n" + "=" * 65)
print("  KPMG Router — 4-Agent Hybrid Routing Tests")
print("=" * 65)

passed = 0
total  = 0

# ── Tier 1: Keyword tests ─────────────────────────────────────
print("\n📌 Tier 1: Keyword Matching")
tests_t1 = [
    ("Raise a ticket for the broken login",         "helpdesk"),
    ("Check status of ticket INC0010001",           "helpdesk"),
    ("My laptop is not working",                    "helpdesk"),
    ("Send an email to the project manager",        "workflow"),
    ("Approve the budget change request",           "workflow"),
    ("Add a risk to the RAID log",                  "workflow"),
    ("What is the KPI for Q4?",                     "api"),
    ("Show me the budget burn rate",                "api"),
    ("Show me the Jira sprint data",                "api"),
    ("Summarise the SOP for data handling",         "retrieval"),
    ("Find the policy on remote work",              "retrieval"),
]
for query, expected in tests_t1:
    total  += 1
    passed += check(query, expected, "T1-keyword")

# ── Tier 2: Semantic (no keywords) ────────────────────────────
print("\n🧠 Tier 2: Embedding Similarity (paraphrased)")
tests_t2 = [
    ("How fast are we progressing on milestones?",        "api"),
    ("Give me a summary of the third quarter findings",   "retrieval"),
    ("What's the project health looking like numerically?","api"),
    ("I can't connect to the company network from home",  "helpdesk"),
]
for query, expected in tests_t2:
    total  += 1
    passed += check(query, expected, "T2-semantic")

# ── Summary ───────────────────────────────────────────────────
print("\n" + "=" * 65)
print(f"  Result: {passed}/{total} passed")
if passed == total:
    print("  🎉 All tests passed!")
else:
    print(f"  ⚠️  {total - passed} test(s) failed — check routing logic")
print("=" * 65 + "\n")
