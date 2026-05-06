import os
import json
import re
import requests
from rag import retrieve_context

OLLAMA_URL   = os.environ.get("OLLAMA_URL",   "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

SYSTEM_INSTRUCTION = """
You are Nexus, a structured AI study assistant designed to help students learn effectively, stay consistent, and stay motivated.

Your slogan is: "Fragmented hurts, not the technology." — meaning consistent structured learning beats random studying.

STRICT FORMATTING RULES:
- NEVER use HTML tags like <strong>, <br>, <ul>, <li>, <h1>, <p> or any other HTML
- NEVER output raw HTML tags under any circumstances
- Use **bold** for key terms using markdown only
- Use numbered lists (1. 2. 3.) for steps
- Use bullet points (-) for related items
- Wrap all code in backtick code blocks
- Avoid long unnecessary text
- Never repeat the question back to the user

PERSONALITY:
- Smart, calm, and mentor-like
- Encouraging and supportive
- Never condescending
- Always focused on the student's learning goals

PROGRAMMING TOPIC DETECTION:
When user wants to learn a PROGRAMMING topic (Java, Python, C++, JavaScript, etc.):
Generate a full learning package in this EXACT format:

LEARNING_PACKAGE_START

PLAN_START
Monday: [Day 1 task]
Tuesday: [Day 2 task]
Wednesday: [Day 3 task]
Thursday: [Day 4 task]
Friday: [Day 5 task]
Saturday: [Day 6 task]
Sunday: [Day 7 task]
PLAN_END

MCQ_START
DAY:1
Q: [question 1 related to day 1 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 2 related to day 1 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 3 related to day 1 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 4 related to day 1 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 5 related to day 1 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
DAY:2
Q: [question 1 related to day 2 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 2 related to day 2 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 3 related to day 2 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 4 related to day 2 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 5 related to day 2 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
DAY:3
Q: [question 1 related to day 3 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 2 related to day 3 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 3 related to day 3 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 4 related to day 3 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 5 related to day 3 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
DAY:4
Q: [question 1 related to day 4 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 2 related to day 4 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 3 related to day 4 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 4 related to day 4 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 5 related to day 4 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
DAY:5
Q: [question 1 related to day 5 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 2 related to day 5 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 3 related to day 5 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 4 related to day 5 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 5 related to day 5 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
DAY:6
Q: [question 1 related to day 6 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 2 related to day 6 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 3 related to day 6 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 4 related to day 6 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 5 related to day 6 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
DAY:7
Q: [question 1 related to day 7 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 2 related to day 7 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 3 related to day 7 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 4 related to day 7 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
Q: [question 5 related to day 7 topic]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
MCQ_END

CODING_START
DAY:1
TASK: [beginner coding task for day 1 topic]
HINT: [helpful hint]
DAY:2
TASK: [coding task for day 2 topic]
HINT: [helpful hint]
DAY:3
TASK: [coding task for day 3 topic]
HINT: [helpful hint]
DAY:4
TASK: [coding task for day 4 topic]
HINT: [helpful hint]
DAY:5
TASK: [coding task for day 5 topic]
HINT: [helpful hint]
DAY:6
TASK: [coding task for day 6 topic]
HINT: [helpful hint]
DAY:7
TASK: [coding task for day 7 topic]
HINT: [helpful hint]
CODING_END

MOTIVATION_START
TOPIC: [language name]
STORY: [2-3 paragraph real-world success story]
DAILY_TIP: [one short powerful tip]
MOTIVATION_END

LEARNING_PACKAGE_END

NON-PROGRAMMING TOPIC RULES:
When user wants to learn a NON-programming topic:
If user says "I want to learn [topic]" WITHOUT asking for a plan:
- Give a 2-3 sentence overview only
- Ask: "Would you like me to create a weekly study plan for this and add it to your planner?"
- Wait for confirmation

If user DIRECTLY asks for a plan:
- Generate using WEEKLY_PLAN_START and WEEKLY_PLAN_END blocks:

WEEKLY_PLAN_START
Monday: [task]
...
WEEKLY_PLAN_END

CONCEPT EXPLANATION RULES:
**Quick Answer:** one or two sentences
**Explanation:** simple with analogy
**Step-by-Step:** numbered steps
**Example:** practical
**Tips:** one or two suggestions

BEHAVIOR RULES:
When user asks for CODING help: explain logic first, then give code with comments, suggest improvements.
When unclear: ask one clarifying question.

STRICT RULES:
- Only help with learning, studying, coding, academic topics
- NEVER use HTML tags in any response
- Never give one sentence answers
- Always be structured and practical
- Slogan: Fragmented hurts, not the technology
- CRITICAL: For MCQ_START...MCQ_END, you MUST generate exactly 5 questions for EACH of the 7 days (DAY:1 through DAY:7). Total = 35 questions. Never skip a day.
- CRITICAL: For CODING_START...CODING_END, you MUST generate exactly 1 coding task for EACH of the 7 days (DAY:1 through DAY:7). Total = 7 tasks. Never skip a day.
- CRITICAL: Each MCQ question must include all 4 options (A, B, C, D) and an ANS line. Incomplete questions break the app.
- CRITICAL: Each day's questions must be relevant to that specific day's topic from the weekly plan.
"""


def build_adaptive_context(weak_topics: list, topic_avgs: dict) -> str:
    """
    Build a prompt section describing the student's past quiz performance.
    Injected after the system instruction so the LLM tailors difficulty
    and focus areas to the individual learner.

    weak_topics : list of strings like ["Python (55%)", "SQL (48%)"]
    topic_avgs  : dict of {topic: avg_score} for all topics
    """
    if not weak_topics and not topic_avgs:
        return ""

    lines = ["\n[STUDENT PERFORMANCE CONTEXT]"]
    lines.append(
        "The student has completed practice quizzes. "
        "Adjust responses to focus on weak areas and skip re-explaining mastered content."
    )

    # Build structured user model from args for richer LLM context
    weak_model   = [
        {"topic": t.rsplit(" (", 1)[0].strip(),
         "avg_score": topic_avgs.get(t.rsplit(" (", 1)[0].strip(), 0)}
        for t in weak_topics
    ]
    strong_names = [t for t, s in topic_avgs.items() if s >= 80]
    strong_model = [{"topic": t, "avg_score": topic_avgs[t]} for t in strong_names]
    user_model   = {
        "weak_topics":   weak_model,
        "strong_topics": strong_model,
        "review_due":    [],
    }
    lines.append(json.dumps(user_model, indent=2))

    if weak_topics:
        lines.append(
            "Topics needing more attention (score < 70%): " + ", ".join(weak_topics)
        )
        lines.append(
            "For these topics: increase explanation depth, add extra examples, "
            "and suggest targeted practice exercises."
        )

    if strong_names:
        lines.append(
            "Topics with strong understanding (>= 80%): "
            + ", ".join(strong_names)
            + ". Build on these without re-explaining basics."
        )

    lines.append("[END PERFORMANCE CONTEXT]\n")
    return "\n".join(lines)


def _build_prompt(
    history: list,
    user_message: str,
    performance_context: str = "",
    rag_context: str = "",
) -> str:
    parts = [f"[SYSTEM INSTRUCTION]\n{SYSTEM_INSTRUCTION.strip()}\n"]

    if rag_context:
        parts.append(
            f"Relevant knowledge:\n{rag_context}\n\nUse the above to inform your response."
        )

    if performance_context:
        parts.append(performance_context)

    if history:
        parts.append("[CONVERSATION HISTORY]")
        for msg in history:
            role = "Student" if msg["role"] == "user" else "Nexus"
            parts.append(f"{role}: {msg['content']}")
        parts.append("")

    parts.append(f"[CURRENT QUESTION]\nStudent: {user_message}\nNexus:")
    prompt = "\n".join(parts)

    prompt += """

REMINDER — BEFORE YOU REPLY CHECK THESE RULES:
1. Programming topic → generate full LEARNING_PACKAGE_START block immediately
2. Non-programming "I want to learn X" → 2-3 sentence overview then ask about plan
3. Direct plan request → generate WEEKLY_PLAN_START block immediately
4. NEVER use HTML tags
5. Always follow the exact format specified
"""
    return prompt


def _extract_weak_topic_names(performance_context: str) -> list[str]:
    """
    Parse the weak topic names out of a performance_context string.
    Returns a list of lowercase topic name strings, e.g. ['python', 'sql'].
    """
    if not performance_context:
        return []
    # Match lines like: Topics needing more attention (score < 70%): Python (55%), SQL (48%)
    m = re.search(r"Topics needing more attention[^:]*:\s*(.+)", performance_context)
    if not m:
        return []
    raw = m.group(1)
    # Strip percentage annotations: "Python (55%)" → "python"
    names = []
    for part in raw.split(","):
        name = re.sub(r"\s*\(\d+%\)", "", part).strip().lower()
        if name:
            names.append(name)
    return names


def _response_addresses_weak_topics(reply: str, weak_topics: list[str]) -> bool:
    """
    Check whether the reply semantically addresses the student's weak topics.

    Strategy (two-tier):
      1. Cosine similarity — embed the reply and each weak-topic description,
         compute cosine similarity. If any topic scores >= SIMILARITY_THRESHOLD
         the reply is considered on-topic. Uses the SentenceTransformer model
         already loaded in rag.py, so no extra dependency is added.
      2. Keyword fallback — if the embedding model is unavailable (cold start,
         import error) we fall back to the original substring check so the
         adaptive loop never breaks silently.

    Why cosine over keyword match:
      A reply that thoroughly explains "variables and loops" for a student weak
      in Python will score high similarity to "Python programming" even without
      the word "Python" appearing. The keyword check would incorrectly flag this
      as non-personalised and trigger an unnecessary re-prompt.
    """
    if not weak_topics:
        return True   # No weak topics → always acceptable

    SIMILARITY_THRESHOLD = 0.35   # tuned for sentence-transformers/all-MiniLM-L6-v2

    try:
        from rag import _model as _st_model   # SentenceTransformer already loaded
        import numpy as np

        reply_vec  = _st_model.encode([reply])[0]
        reply_norm = reply_vec / (np.linalg.norm(reply_vec) + 1e-9)

        for topic in weak_topics:
            topic_desc  = f"learning and studying {topic} programming concepts"
            topic_vec   = _st_model.encode([topic_desc])[0]
            topic_norm  = topic_vec / (np.linalg.norm(topic_vec) + 1e-9)
            similarity  = float(np.dot(reply_norm, topic_norm))
            if similarity >= SIMILARITY_THRESHOLD:
                return True

        return False   # No weak topic reached similarity threshold → trigger re-prompt

    except Exception:
        # Fallback: original keyword substring check
        reply_lower = reply.lower()
        return any(topic in reply_lower for topic in weak_topics)


def _build_reprompt(
    history: list,
    user_message: str,
    performance_context: str,
    rag_context: str,
    weak_topics: list[str],
) -> str:
    """
    Build a second prompt explicitly instructing the model to address weak topics.
    Called only when the first response failed the adaptive check.
    """
    topic_list = ", ".join(weak_topics)
    reprompt_instruction = (
        f"\n[ADAPTIVE REPROMPT — STRICT]\n"
        f"Your previous response did not address the student's weak topics: {topic_list}.\n"
        f"Rewrite your response. You MUST explicitly mention and explain concepts related to: {topic_list}.\n"
        f"Tie your answer back to these areas. This is required for personalised learning.\n"
        f"[END REPROMPT]\n"
    )
    base = _build_prompt(history, user_message, performance_context, rag_context)
    return base + reprompt_instruction


def ask_ollama(
    history: list,
    user_message: str,
    performance_context: str = "",
) -> str:
    """
    Blocking call — returns the complete reply as a string.

    Adaptive loop:
      1. Generate a first response.
      2. Check whether it addresses the student's weak topics.
      3. If not, re-prompt once with an explicit instruction to cover those topics.
      4. Return whichever response is returned (first pass or re-prompt).
    """
    rag_context = retrieve_context(user_message)
    prompt = _build_prompt(history, user_message, performance_context, rag_context)
    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.5, "top_p": 0.9, "num_predict": 8192},
    }
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate", json=payload, timeout=500
        )
        resp.raise_for_status()
        first_reply = resp.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Cannot connect to Ollama. Make sure Ollama is running: ollama serve"
        )
    except requests.exceptions.Timeout:
        raise RuntimeError("Ollama timed out. Please try again.")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Ollama API error: {e}")

    # ── Adaptive loop check ──────────────────────────────────────────────────
    weak_topics = _extract_weak_topic_names(performance_context)
    if weak_topics and not _response_addresses_weak_topics(first_reply, weak_topics):
        reprompt = _build_reprompt(
            history, user_message, performance_context, rag_context, weak_topics
        )
        reprompt_payload = {**payload, "prompt": reprompt}
        try:
            r2 = requests.post(
                f"{OLLAMA_URL}/api/generate", json=reprompt_payload, timeout=500
            )
            r2.raise_for_status()
            second_reply = r2.json().get("response", "").strip()
            if second_reply:
                return second_reply
        except Exception:
            pass  # Fall back to first reply if re-prompt fails

    return first_reply


def stream_ollama(
    history: list,
    user_message: str,
    performance_context: str = "",
):
    """
    Generator that yields text tokens from Ollama's streaming API.

    Adaptive loop:
      Streams the first response token-by-token.
      After streaming completes, checks whether weak topics were addressed.
      If not, yields a separator then streams a re-prompted response.
    """
    rag_context = retrieve_context(user_message)
    prompt = _build_prompt(history, user_message, performance_context, rag_context)
    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": True,
        "options": {"temperature": 0.5, "top_p": 0.9, "num_predict": 8192},
    }

    first_tokens = []

    try:
        with requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            stream=True,
            timeout=600,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("response", "")
                    if token:
                        first_tokens.append(token)
                        yield token
                    if chunk.get("done"):
                        break
                except json.JSONDecodeError:
                    continue
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Cannot connect to Ollama. Make sure Ollama is running: ollama serve"
        )
    except requests.exceptions.Timeout:
        raise RuntimeError("Ollama timed out.")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Ollama API error: {e}")

    # ── Adaptive loop check ──────────────────────────────────────────────────
    first_reply = "".join(first_tokens)
    weak_topics = _extract_weak_topic_names(performance_context)
    if weak_topics and not _response_addresses_weak_topics(first_reply, weak_topics):
        reprompt = _build_reprompt(
            history, user_message, performance_context, rag_context, weak_topics
        )
        reprompt_payload = {**payload, "prompt": reprompt}
        try:
            with requests.post(
                f"{OLLAMA_URL}/api/generate",
                json=reprompt_payload,
                stream=True,
                timeout=600,
            ) as resp2:
                resp2.raise_for_status()
                for line in resp2.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            yield token
                        if chunk.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass  # Silently fall back — first reply already streamed


def check_ollama_status() -> dict:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        r.raise_for_status()
        models       = [m["name"] for m in r.json().get("models", [])]
        model_loaded = any(OLLAMA_MODEL in m for m in models)
        return {"ok": True, "model": OLLAMA_MODEL,
                "model_loaded": model_loaded, "available": models}
    except Exception as e:
        return {"ok": False, "error": str(e)}