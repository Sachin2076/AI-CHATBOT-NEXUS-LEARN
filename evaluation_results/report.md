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

## Programming vs Non-Programming Quality

| Category | Avg Structural Score | Avg Plan Completeness |
|----------|---------------------|-----------------------|
| Programming | 83% | 7/7 days |
| Non-Programming | 80% | 6/7 days |

---

## Key Findings

- The model generated valid weekly plans for **9/10** topics.
- Of 27 MCQ questions generated, **27 (100%)** had correct structure (4 options + valid answer letter).
- Average response latency was **195.7s** per topic on `llama3`.
- Raw LLM outputs saved in `evaluation_results/raw_outputs/` for manual factual review.

## Manual Review Required

The automated evaluation above checks **structural validity** only.
For **factual accuracy**, manually review the MCQ questions in `raw_outputs/`
and complete `evaluation_results/manual_grading.csv`.

Suggested sample: grade 5 MCQs per topic = 25 questions total.