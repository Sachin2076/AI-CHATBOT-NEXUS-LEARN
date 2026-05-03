import os
import json
import requests

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
Q: [question]
A) [option]
B) [option]
C) [option]
D) [option]
ANS: [letter]
...
MCQ_END

CODING_START
DAY:1
TASK: [beginner task]
HINT: [hint]
...
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
"""


def build_adaptive_context(weak_topics: list, topic_avgs: dict) -> str:
    """
    Build a prompt section describing the student's past quiz performance.
    Injected after the system instruction so the LLM tailors difficulty
    and focus areas to the individual learner.
    """
    if not weak_topics and not topic_avgs:
        return ""

    lines = ["\n[STUDENT PERFORMANCE CONTEXT]"]
    lines.append(
        "The student has completed practice quizzes. "
        "Adjust responses to focus on weak areas and skip re-explaining mastered content."
    )

    if weak_topics:
        lines.append(
            "Topics needing more attention (score < 70%): " + ", ".join(weak_topics)
        )
        lines.append(
            "For these topics: increase explanation depth, add extra examples, "
            "and suggest targeted practice exercises."
        )

    if topic_avgs:
        strong = [t for t, s in topic_avgs.items() if s >= 80]
        if strong:
            lines.append(
                "Topics with strong understanding (>= 80%): "
                + ", ".join(strong)
                + ". Build on these without re-explaining basics."
            )

    lines.append("[END PERFORMANCE CONTEXT]\n")
    return "\n".join(lines)


def _build_prompt(
    history: list,
    user_message: str,
    performance_context: str = "",
) -> str:
    parts = [f"[SYSTEM INSTRUCTION]\n{SYSTEM_INSTRUCTION.strip()}\n"]

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


def ask_ollama(
    history: list,
    user_message: str,
    performance_context: str = "",
) -> str:
    """Blocking call — returns the complete reply as a string."""
    prompt = _build_prompt(history, user_message, performance_context)
    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.5, "top_p": 0.9, "num_predict": 2048},
    }
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate", json=payload, timeout=500
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Cannot connect to Ollama. Make sure Ollama is running: ollama serve"
        )
    except requests.exceptions.Timeout:
        raise RuntimeError("Ollama timed out. Please try again.")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Ollama API error: {e}")


def stream_ollama(
    history: list,
    user_message: str,
    performance_context: str = "",
):
    """
    Generator that yields text tokens from Ollama's streaming API.
    """
    prompt = _build_prompt(history, user_message, performance_context)
    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": True,
        "options": {"temperature": 0.5, "top_p": 0.9, "num_predict": 2048},
    }
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