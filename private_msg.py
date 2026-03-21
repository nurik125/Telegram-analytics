from config import ( AUGMENTING_MODEL, MODEL, SYSTEM_PROMPT, HEAD_PROMPT, OLLAMA_URL )

# Model Related
import ollama
from ollama import chat

async def augment_prompt(model: str, prompt: str) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
    }

    resp = await client.post(OLLAMA_URL, json=payload)
    resp.raise_for_status()
    data = resp.json()
    return data["message"]["content"]

async def ask_ollama(client: httpx.AsyncClient, model: str, message: List[Dict]) -> str:
    payload = {
        "model": model,
        "messages": message
    }

    resp = await client.post(OLLAMA_URL, json=payload)
    resp.raise_for_status()
    data = resp.json()
    return data["message"]["content"]

async def take_the_request(event):
    print("Ollama handling the response...")

    prompt = HEAD_PROMPT + event.raw_text
    message = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": await augment_prompt(AUGMENTING_MODEL, prompt)}
    ]

    await ask_ollama(MODEL, message)
