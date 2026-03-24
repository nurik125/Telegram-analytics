import os
import json
import asyncio
import re
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.functions.channels import JoinChannelRequest

from utils import qr_auth, PullTheModel, ModelExists, OllamaService
from config import MODEL, AUGMENTING_MODEL
from exceptions import ModelNotFoundError, ModelNotSpecifiedError
from tracker import TrackedChannel, add_channel, get_channel, list_channels

load_dotenv()

api_id = int(os.getenv("CLIENT_API"))
api_hash = os.getenv("CLIENT_API_HASH")


def model_pulling(model: str):
    if not model:
        raise ModelNotSpecifiedError("Model not specified in .env file")

    try:
        if not ModelExists(model):
            raise ModelNotFoundError("Model not pulled")

    except ModelNotFoundError:
        PullTheModel(model)

def parse_llm_response(text: str) -> dict:
    """
    Парсит JSON из ответа LLM.
    Если LLM вернул текст с мусором вокруг JSON — вырезаем JSON через regex.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {}
    

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
    MY_ID = me.id

    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
    async def handle_command(event):
        print("-" * 50)
        print(f"[КОМАНДА] {event.raw_text}")

        # Шаг 1: LLM переписывает запрос в структурированный вид
        augmented = await ollama_client.augment_prompt(event.raw_text)
        print(f"[AUGMENTED] {augmented}")

        # Шаг 2: Главный LLM извлекает каналы и цель → возвращает JSON
        response = await ollama_client.ask(augmented)
        print(f"[LLM JSON] {response}")

        # Шаг 3: Парсим JSON
        data = parse_llm_response(response)

        if not data:
            await event.reply("Не смог разобрать запрос. Попробуй ещё раз.")
            return

        # Шаг 4: Если LLM не уверен в канале — спрашиваем у пользователя
        if data.get("ambiguous") and data.get("clarification_needed"):
            await event.reply(data["clarification_needed"])
            return

        channels = data.get("channels", [])
        goal = data.get("goal", "monitor")
        keywords = data.get("keywords", [])

        if not channels:
            await event.reply("Не нашёл каналов в твоём запросе. Укажи @username или ссылку.")
            return

        # Шаг 5: Для каждого канала — вступаем и добавляем в трекер
        results = []
        for ch in channels:
            username = ch.lstrip("@")
            try:
                # Вступаем в канал через Telegram
                entity = await client.get_entity(username)
                await client(JoinChannelRequest(entity))
                print(f"[JOIN] Вступили в @{username}")

                # Сохраняем в tracker.json
                tracked = TrackedChannel(
                    channel_id=entity.id,
                    username=username,
                    goal=goal,
                    keywords=keywords,
                    owner_id=MY_ID
                )
                added = add_channel(tracked)

                if added:
                    results.append(f"✅ @{username} — отслеживается")
                else:
                    results.append(f"⚠️ @{username} — уже отслеживается")

            except Exception as e:
                print(f"[ОШИБКА] @{username}: {e}")
                results.append(f"❌ @{username} — ошибка: {e}")

        # Шаг 6: Отвечаем пользователю
        summary = "\n".join(results)
        await event.reply(
            f"Готово!\n\n{summary}\n\n"
            f"Цель: {goal}\n"
            f"Ключевые слова: {', '.join(keywords) if keywords else 'все посты'}"
        )


    # ─── Канал: мониторим посты ────────────────────────────────────────────────

    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_channel))
    async def handle_channel_post(event):
        # Шаг 1: Проверяем отслеживаем ли этот канал
        tracked = get_channel(event.chat_id)
        if tracked is None:
            return  # не наш канал — игнорируем

        post_text = event.raw_text
        if not post_text:
            return  # пустой пост (фото без подписи и тд)

        print(f"[ПОСТ] @{tracked.username}: {repr(post_text[:80])}")

        # Шаг 2: Спрашиваем LLM релевантен ли пост
        relevance_prompt = (
            f"Tracking goal: {tracked.goal}\n"
            f"Keywords to match: {tracked.keywords}\n"
            f"New post text: {post_text}\n\n"
            f"Is this post relevant to the tracking goal and keywords?\n"
            f"Reply ONLY with YES or NO followed by one sentence explaining why."
        )
        verdict = await ollama_client.ask(relevance_prompt)
        print(f"[РЕЛЕВАНТНОСТЬ] {verdict}")

        # Шаг 3: Если YES — уведомляем пользователя
        if verdict.strip().upper().startswith("YES"):
            await client.send_message(
                MY_ID,
                f"🔔 Новый пост в @{tracked.username}:\n\n"
                f"{post_text}\n\n"
                f"— {verdict}"
            )


    print("Слушаем сообщения...")
    await client.run_until_disconnected()
    await ollama_client.close()


if __name__ == "__main__":
    asyncio.run(main())
