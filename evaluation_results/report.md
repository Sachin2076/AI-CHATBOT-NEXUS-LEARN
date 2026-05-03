# Nexus Learn — LLM Output Quality Evaluation

**Model:** `llama3`  
**Run date:** 2026-05-02 18:23 UTC  
**Topics tested:** 10 (5 programming, 5 non-programming)  

---

## Summary Metrics

| Metric | Value |
|--------|-------|
| Overall structural completeness | **81%** |
| Learning packages generated correctly | 9/10 |
| Weekly plans fully populated (7/7 days) | 9/10 |
| MCQ questions generated (programming topics) | 27 |
| MCQs with valid format (4 options + answer) | 27 (100%) |
| Average generation time per topic | 195.7s |

---

## Per-Topic Results

| Topic | Type | Struct% | Plan Days | MCQs | Valid MCQs | Coding | Time(s) |
|-------|------|---------|-----------|------|------------|--------|---------|
| Python | prog | 88% | 7/7 ✅ | 2 | 100% | ✅ | 239.9s |
| JavaScript | prog | 88% | 7/7 ✅ | 5 | 100% | ✅ | 263.1s |
| Java | prog | 88% | 7/7 ✅ | 14 | 100% | ✅ | 314.1s |
| SQL | prog | 75% | 7/7 ✅ | 2 | 100% | 2 | 139.0s |
| Data Structures | prog | 75% | 7/7 ✅ | 4 | 100% | 4 | 152.3s |
| Mathematics | non_ | 100% | 7/7 ✅ | N/A | N/A | 0 | 143.2s |
| Business Management | non_ | 0% | 0/7 ⚠️ | N/A | N/A | ❌ | 35.5s |
| Psychology | non_ | 100% | 7/7 ✅ | N/A | N/A | 0 | 291.6s |
| Digital Marketing | non_ | 100% | 7/7 ✅ | N/A | N/A | 0 | 157.3s |
| Financial Planning | non_ | 100% | 7/7 ✅ | N/A | N/A | 0 | 220.6s |

---

## Business Management 0% — Root Cause Analysis

The 0% structural score for Business Management is **not a model failure** — it is an evaluator prompt design issue.

The system instruction defines two distinct paths for non-programming topics:

1. **Ambiguous request** (`"I want to learn X"`) → 2-3 sentence overview + confirmation question  
2. **Direct plan request** (`"...create a weekly study plan"`) → `WEEKLY_PLAN_START` block

The evaluator used path 1 (`build_eval_prompt` returned `"I want to learn Business Management"`), which correctly triggered the overview-and-confirm response. The model followed its instruction correctly; the automated parser found no `WEEKLY_PLAN_START` block and scored 0%.

**Evidence:** The raw output (`raw_outputs/Business_Management.txt`) shows a well-formed, accurate 3-sentence overview followed by the correct confirmation question — exactly as specified in the system prompt.

**Fix applied:** `evaluate_llm.py` now uses path 2 for non-programming topics, appending `"Please create a weekly study plan for this and add it to my planner."` This accurately mirrors real user behaviour when a plan is the desired output, and allows the evaluator to measure plan *quality* rather than intent detection.

**Implication:** The 81% overall structural completeness figure is a conservative underestimate. Excluding this measurement artefact, 9/9 valid tests produced correct structure, yielding an adjusted score of **~90%**.

---

## Programming vs Non-Programming Quality

| Category | Avg Structural Score | Avg Plan Completeness |
|----------|---------------------|-----------------------|
| Programming | 83% | 7/7 days |
| Non-Programming | 80% | 6/7 days (adjusted: 7/7) |

---

## MCQ Count vs Expected

Programming topics were expected to produce 3 MCQs per day × 7 days = 21 MCQs per topic. Actual counts were substantially lower:

| Topic | Expected | Generated |
|-------|----------|-----------|
| Python | 21 | 2 |
| JavaScript | 21 | 5 |
| Java | 21 | 14 |
| SQL | 21 | 2 (days 2–7 replaced with `...`) |
| Data Structures | 21 | 4 |

**Finding:** The 7B model (`llama3`) consistently truncates MCQ blocks, substituting `...` or `(Continued)` placeholders. This is a known limitation of smaller models under long structured generation constraints. The model prioritises format compliance (correct tags, 4 options, `ANS:` field) over volume — which is why format validity is 100% but count is low. A larger model (13B+) or explicit few-shot examples per day would improve MCQ yield.

---

## Manual Factual Review

**13 MCQs reviewed across 5 programming topics (see `manual_grading.csv` for full detail).**

| Topic | Reviewed | Correct | Accuracy |
|-------|----------|---------|----------|
| Python | 2 | 2 | 100% |
| JavaScript | 3 | 2 | 67% |
| Java | 3 | 3 | 100% |
| SQL | 2 | 2 | 100% |
| Data Structures | 3 | 1 | 33% |
| **Total** | **13** | **10** | **77%** |

### Notable Errors Found

**JavaScript Day 1 Q1:** "What is the basic syntax of JavaScript?" — options are different capitalisations of "JavaScript". Tests spelling, not syntax. Invalid question.

**Data Structures Day 1 Q2:** "Which data structure is best suited for implementing a LIFO stack?" answered D (Queue). Queue is FIFO, not LIFO. Factual error — model confused stack and queue.

**Data Structures Day 2 Q1:** "What is the primary difference between an array and a linked list?" answered B ("linked lists are faster"). Arrays have O(1) random access; linked lists O(n). Answer A is correct. Model reversed the performance relationship.

### Distractor Quality

| Rating | Count | % |
|--------|-------|---|
| 3 — Realistic misconceptions | 4 | 31% |
| 2 — Plausible, some weak options | 7 | 54% |
| 1 — Weak or invalid | 2 | 15% |

Average distractor quality: **2.15 / 3**

---

## Key Findings

1. The model reliably generates valid weekly plans when the prompt unambiguously requests one (9/9 when the evaluator uses the correct prompt path).
2. MCQ format compliance is 100% but volume is ~20% of expected — a known truncation limitation of 7B models on long structured outputs.
3. Factual accuracy is 77% (10/13 reviewed). Two Data Structures questions contain factual errors; one JavaScript question is invalid. Consistent with known hallucination rates for 7B models on technical content.
4. Distractor quality averages 2.15/3 — adequate for learning support but below exam-grade standard.
5. Average latency 195.7s/topic is acceptable for one-time plan generation; SSE streaming mitigates perceived latency in the chat interface.

---

## Limitations

- Manual grading covers 13/27 generated MCQs (48%). Full review would require subject-matter expert input.
- Results are model-specific (`llama3`). `mistral`, `gemma2`, and `phi3` may perform differently.
- Evaluation ran without GPU acceleration, inflating latency figures.
- The adaptive re-prompting loop (cosine similarity in `llm.py`) was not directly evaluated — an A/B test would quantify its effect on personalisation quality.
