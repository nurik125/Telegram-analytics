import os
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient, events
from utils import qr_auth

from config import MODEL, AUGMENTING_MODEL

load_dotenv()

api_id = os.getenv("CLIENT_API")
api_hash = os.getenv("CLIENT_API_HASH")

from utils import (
    PullTheModel,
    ModelExists,
    OllamaService
)

# Exceptions
from exceptions import ModelNotFoundError, ModelNotSpecifiedError

def model_pulling(model: str):
    if not model:
        raise ModelNotSpecifiedError("Model not specified in .env file")

    try:
        if not ModelExists(model):
            raise ModelNotFoundError("Model not pulled")

    except ModelNotFoundError:
        PullTheModel(model)

async def main():
    model_pulling(MODEL)
    model_pulling(AUGMENTING_MODEL)

    client = TelegramClient("my_session", api_id, api_hash)
    ollama_client = OllamaService()

    await client.connect()

    if not await client.is_user_authorized():
        await qr_auth(client)

    me = await client.get_me()
    print(f"Logged in as: {me.first_name} | id={me.id}")

    @client.on(events.NewMessage(incoming=True))
    async def incoming_message(event):
        chat = await event.get_chat()
        sender = await event.get_sender()

        print("NEW MESSAGE FROM", end=" ")

        if event.is_private:
            print(f"Personal chat: {chat.first_name}")
            print("Ollama handling the response...")
            prompt = await ollama_client.augment_prompt(event.raw_text)
            response = await ollama_client.ask(prompt)
            print(response)

        elif event.is_channel:
            print(f"Channel / megagroup: {getattr(chat, 'title', None)}")

        elif event.is_group:
            print(f"Group chat: {getattr(chat, 'title', None)}")

        print("chat_id:", event.chat_id)
        print("sender_id:", event.sender_id)
        print("text:", repr(event.raw_text))
        print("-"*50)

    print("Listening for messages...")
    await client.run_until_disconnected()
    await ollama_client.close()

if __name__ == "__main__":
    asyncio.run(main())
