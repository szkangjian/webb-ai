"""
WebbGPT automated test runner.
Reads test_questions.json, runs each through the RAG pipeline,
and saves results to test_results.json and test_results.md.
"""

import json
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rag.query import answer

TEST_FILE = os.path.join(os.path.dirname(__file__), "test_questions.json")
RESULT_FILE = os.path.join(os.path.dirname(__file__), "test_results.json")


def run_tests():
    with open(TEST_FILE, encoding="utf-8") as f:
        test_data = json.load(f)

    results = []
    total = sum(len(cat["questions"]) for cat in test_data["categories"])
    current = 0

    for cat in test_data["categories"]:
        print(f"\n{'='*60}")
        print(f"📂 {cat['name']} ({cat['category']})")
        print(f"{'='*60}")

        for q in cat["questions"]:
            current += 1
            print(f"\n[{current}/{total}] {q['id']}: {q['question'][:50]}...")

            start = time.time()
            try:
                resp = answer(q["question"])
                elapsed = round(time.time() - start, 1)
                ans = resp["answer"]
                sources = resp["sources"]

                # Check which expected topics appear in the answer
                # Topics use "|" to separate bilingual synonyms (any match counts)
                found_topics = []
                missing_topics = []
                ans_lower = ans.lower()
                for topic in q.get("expect_topics", []):
                    synonyms = [s.strip().lower() for s in topic.split("|")]
                    if any(syn in ans_lower for syn in synonyms):
                        found_topics.append(topic)
                    else:
                        missing_topics.append(topic)

                coverage = len(found_topics) / len(q["expect_topics"]) * 100 if q["expect_topics"] else -1

                result = {
                    "id": q["id"],
                    "category": cat["category"],
                    "question": q["question"],
                    "language": q["language"],
                    "difficulty": q["difficulty"],
                    "answer": ans,
                    "sources": sources,
                    "time_seconds": elapsed,
                    "expect_topics": q["expect_topics"],
                    "found_topics": found_topics,
                    "missing_topics": missing_topics,
                    "coverage_pct": round(coverage, 1),
                    "status": "ok",
                }

                # Print summary
                cov_str = f"{coverage:.0f}%" if coverage >= 0 else "N/A (edge case)"
                status = "✅" if coverage >= 70 or coverage < 0 else "⚠️" if coverage >= 40 else "❌"
                print(f"  {status} Coverage: {cov_str} | Time: {elapsed}s | Sources: {len(sources)}")
                if missing_topics:
                    print(f"  ⚠️  Missing: {', '.join(missing_topics)}")

            except Exception as e:
                elapsed = round(time.time() - start, 1)
                result = {
                    "id": q["id"],
                    "category": cat["category"],
                    "question": q["question"],
                    "answer": None,
                    "time_seconds": elapsed,
                    "status": "error",
                    "error": str(e),
                }
                print(f"  ❌ ERROR: {e}")

            results.append(result)

    # Summary
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print(f"{'='*60}")

    ok_results = [r for r in results if r["status"] == "ok" and r.get("coverage_pct", -1) >= 0]
    if ok_results:
        avg_coverage = sum(r["coverage_pct"] for r in ok_results) / len(ok_results)
        avg_time = sum(r["time_seconds"] for r in results) / len(results)
        high = sum(1 for r in ok_results if r["coverage_pct"] >= 70)
        mid = sum(1 for r in ok_results if 40 <= r["coverage_pct"] < 70)
        low = sum(1 for r in ok_results if r["coverage_pct"] < 40)
        errors = sum(1 for r in results if r["status"] == "error")

        print(f"Total questions: {len(results)}")
        print(f"Average coverage: {avg_coverage:.1f}%")
        print(f"Average time: {avg_time:.1f}s")
        print(f"✅ Good (≥70%): {high}")
        print(f"⚠️  Medium (40-69%): {mid}")
        print(f"❌ Low (<40%): {low}")
        if errors:
            print(f"💥 Errors: {errors}")

    # Save results
    output = {
        "test_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_questions": len(results),
        "results": results,
    }
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {RESULT_FILE}")


if __name__ == "__main__":
    run_tests()
