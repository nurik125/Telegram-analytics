import ollama
from ollama import ChatResponse
from typing import Iterator, Sequence
from tqdm import tqdm
from bs4 import BeautifulSoup
import re

def PullTheModel(model: str) -> None:
    progress_bar = None
    current_digest = None

    print(f"Loading {model}")
    for update in ollama.pull(model, stream=True):
        status = update.get("status", "")
        digest = update.get("digest")
        completed = update.get("completed", 0)
        total = update.get("total", 0)

        # If new layer starts → reset progress bar
        if digest != current_digest:
            if progress_bar:
                progress_bar.close()
            progress_bar = None
            current_digest = digest

        if isinstance(completed, (int, float)) and isinstance(total, (int, float)) and total > 0:
            if progress_bar is None:
                progress_bar = tqdm(total=total, unit="B", unit_scale=True)
            progress_bar.n = completed
            progress_bar.set_description(status)
            progress_bar.refresh()
        else:
            print(status)
          
    if progress_bar:
        progress_bar.close()

    print("-" * 50)
    print("Done")
    print(f"{model} is Loaded")
    print("-" * 50)
  
def ModelExists(model: str) -> bool:
    return any(m["model"] == model for m in ollama.list()["models"])

def RemoveTheModel(model: str) -> None:
  if ModelExists(model):
      print(f"Deleting {model}")
      ollama.delete(model=model)
      print(f"{model} deleted")
  else:
      print(f"{model} not found")

async def qr_auth():
    print("You have not authentificated yet!")
    print("Generating QR code...")

    qr_login = await client.qr_login()

    # create QR image
    qr = qrcode.make(qr_login.url)
    qr.save("login_qr.png")

    print("QR saved as login_qr.png")
    print("Open Telegram -> Settings -> Devices -> Link Device -> Scan QR")

    await qr_login.wait()

    print("Logged In")

import httpx
from config import ( OLLAMA_URL, SYSTEM_PROMPT, HEAD_PROMPT, AUGMENTING_MODEL, MODEL )

class OllamaService:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=120.0)
        self.url = OLLAMA_URL

    async def augment_prompt(self, prompt: str) -> str:
        prompt = HEAD_PROMPT + prompt
        r = await self.client.post(
            self.url,
            json={
                "model": AUGMENTING_MODEL,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        r.raise_for_status()
        return r.json()["message"]["content"]

    async def ask(self, prompt: str) -> str:
        r = await self.client.post(
            self.url,
            json={
                "model": MODEL,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
            },
        )
        r.raise_for_status()
        return r.json()["message"]["content"]


    async def close(self):
        await self.client.aclose()


async def take_the_request(event):
    print("Ollama handling the response...")

    prompt = HEAD_PROMPT + event.raw_text
    message = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": await augment_prompt(AUGMENTING_MODEL, prompt)}
    ]

    await ask_ollama(MODEL, message)
