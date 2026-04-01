import os
import json
import asyncio
import re
from dotenv import load_dotenv
 
# Сначала загружаем переменные окружения!
load_dotenv() 
 
# И только потом импортируем локальные модули
from telethon import TelegramClient, events
from telethon.utils import get_peer_id
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.errors import FloodWaitError, ChannelPrivateError, UsernameNotOccupiedError
 
from utils import qr_auth, GroqService
from config import MODEL, AUGMENTING_MODEL
from tracker import TrackedChannel, add_channel, get_channel
from bot import bot, start_bot, pending_requests
 
 
api_id = int(os.getenv("CLIENT_API"))
api_hash = os.getenv("CLIENT_API_HASH")
 
SESSION_PATH = os.getenv("SESSION_PATH", os.path.join(os.path.dirname(__file__), "bot_session"))
 
# ─── Parse LLM JSON Response ──────────────────────────────────────────────────
 
def parse_llm_response(text: str) -> dict:
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
 
# ─── Обработка запроса пользователя ──────────────────────────────────────────
 
async def process_user_request(client, groq_client, user_id: int, request_text: str):
    print(f"[USERBOT] Обрабатываю запрос от {user_id}: {request_text}")
 
    try:
        augmented = await groq_client.augment_prompt(request_text)
        response = await groq_client.ask(augmented)
        data = parse_llm_response(response)
    except Exception as e:
        print(f"[USERBOT] Ошибка Groq API: {e}")
        await bot.send_message(user_id, "❌ Ошибка связи с ИИ. Попробуй позже.")
        return
 
    if not data:
        await bot.send_message(user_id, "❌ Не удалось распознать каналы или цель мониторинга.")
        return
 
    if data.get("ambiguous") and data.get("clarification_needed"):
        await bot.send_message(user_id, data["clarification_needed"])
        return
 
    channels = data.get("channels", [])
    goal = data.get("goal", "monitor")
    keywords = data.get("keywords", [])
    cadence = data.get("cadence", "immediate")
 
    if not channels:
        await bot.send_message(user_id, "❌ В запросе не указаны каналы для мониторинга.")
        return
 
    results = []
    for ch in channels:
        username = ch.lstrip("@").split('/')[-1]
        try:
            entity = await client.get_entity(username)
            entity_id = get_peer_id(entity)
            await client(JoinChannelRequest(entity))
 
            tracked = TrackedChannel(
                channel_id=entity_id,
                username=username,
                goal=goal,
                keywords=keywords,
                owner_id=user_id,
                cadence=cadence
            )
 
            if add_channel(tracked):
                results.append(f"✅ @{username} — добавлен")
            else:
                results.append(f"⚠️ @{username} — уже в списке")
 
        except FloodWaitError as e:
            print(f"[USERBOT] FloodWait {e.seconds}s для @{username}")
            await asyncio.sleep(e.seconds)
            results.append(f"⏳ @{username} — задержка Telegram, попробуй позже")
 
        except ChannelPrivateError:
            results.append(f"🔒 @{username} — приватный канал, нет доступа")
 
        except UsernameNotOccupiedError:
            results.append(f"❓ @{username} — канал не найден")
 
        except Exception as e:
            results.append(f"❌ @{username} — ошибка: {str(e)}")
        
        else:
            await asyncio.sleep(1)  # Защита от флуд-бана между успешными запросами
 
    await bot.send_message(user_id, "Настройка завершена:\n\n" + "\n".join(results))
 
# ─── Опрос очереди запросов ───────────────────────────────────────────────────
 
async def poll_pending_requests(client, groq_client):
    while True:
        if pending_requests:
            # Безопасно вытаскиваем и удаляем по одному — не очищаем весь словарь разом
            current_batch = list(pending_requests.keys())
            for user_id in current_batch:
                req = pending_requests.pop(user_id, None)
                if req:
                    await process_user_request(client, groq_client, user_id, req["text"])
        await asyncio.sleep(2)
 
# ─── Обёртка с логированием ошибок для задач ─────────────────────────────────
 
async def safe_task(name: str, coro):
    try:
        await coro
    except asyncio.CancelledError:
        print(f"[MAIN] Задача '{name}' отменена")
        raise
    except Exception as e:
        print(f"[MAIN] Задача '{name}' упала с ошибкой: {e}")
        raise
 
# ─── Основная функция ─────────────────────────────────────────────────────────
 
async def main():
    client = TelegramClient(SESSION_PATH, api_id, api_hash)
    groq_client = GroqService()
 
    await client.connect()
 
    if not await client.is_user_authorized():
        await qr_auth(client)
 
    print("[MAIN] Userbot авторизован.")
 
    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_channel))
    async def handle_channel_post(event):
        print("HANDLING")
 
        tracked = get_channel(event.chat_id)
        if not tracked or not event.raw_text:
            return
 
        print(f"[USERBOT] Анализирую пост в @{tracked.username}")
 
        relevance_prompt = (
            f"Goal: {tracked.goal}\n"
            f"Keywords: {tracked.keywords}\n"
            f"Post: {event.raw_text}\n\n"
            "Is this relevant? Reply ONLY 'YES: <reason>' or 'NO'."
        )
 
        try:
            verdict = await groq_client.ask(relevance_prompt)
            if verdict.strip().upper().startswith("YES"):
                # Обрезаем пост до 500 символов чтобы не превышать лимит сообщения
                post_preview = event.raw_text[:500] + ("..." if len(event.raw_text) > 500 else "")
                reason = verdict[4:].strip()
 
                # Отправляем без parse_mode — текст поста может содержать * _ ` [ которые ломают Markdown
                await bot.send_message(
                    tracked.owner_id,
                    f"🔔 Найдено соответствие в @{tracked.username}\n\n"
                    f"{post_preview}\n\n"
                    f"💡 Почему: {reason}"
                )
        except Exception as e:
            print(f"[USERBOT] Ошибка анализа: {e}")
 
    print("[MAIN] Lumo запущен и готов к работе!")
 
    try:
        await asyncio.gather(
            safe_task("bot", start_bot()),
            safe_task("poll", poll_pending_requests(client, groq_client)),
            safe_task("userbot", client.run_until_disconnected()),
        )
    finally:
        await groq_client.close()
        await client.disconnect()
 
 
if __name__ == "__main__":
    asyncio.run(main())
