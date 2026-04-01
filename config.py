import os
 
# ─── Models ───────────────────────────────────────────────────────────────────
# These are the model IDs exactly as Groq expects them.
# If Groq returns "model not found", check https://console.groq.com/docs/models
MODEL = "llama-3.3-70b-versatile"
AUGMENTING_MODEL = "llama-3.1-8b-instant"
 
# ─── Groq ─────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
 
# ─── System Prompt ────────────────────────────────────────────────────────────
# Kept short and unambiguous so the model reliably returns JSON.
SYSTEM_PROMPT = """
You are a Telegram channel tracking assistant.
 
Read the user's message and extract their intent.
 
Rules:
- Only extract channels that are explicitly mentioned (@username or t.me/link).
- Do NOT invent or guess channel usernames.
- If no channel is mentioned, return an empty channels list.
- If the user is just asking a question (not requesting monitoring), return an empty channels list.
- Extract keywords/topics the user wants to track. If none, return [].
- goal must be one of: "monitor", "digest", "alerts", "summary"
- cadence must be one of: "immediate", "daily", "weekly"
- If channel identity is truly unclear, set ambiguous=true and write a clarification question.
 
You MUST respond with ONLY valid JSON — no markdown, no explanation, no extra text:
{
  "channels": ["@username1", "@username2"],
  "goal": "monitor",
  "keywords": ["keyword1", "keyword2"],
  "cadence": "immediate",
  "ambiguous": false,
  "clarification_needed": ""
}
"""
 
# ─── Augmentation Prompt ──────────────────────────────────────────────────────
# Rewrites the user message into a cleaner, explicit instruction before the
# main classification step. Kept minimal to avoid double-prompting confusion.
HEAD_PROMPT = """Rewrite the following user request into a clear, structured instruction for a Telegram channel tracking assistant.
Do NOT invent channel names. Only clarify and normalize what is already there.
If cadence is not stated, use "immediate". If goal is not stated, use "monitor".
 
User request:
"""
 
If channels are missing or unclear, explicitly mark them as "ambiguous".
 
Return a structured instruction in natural language.
 
User query:
"""
