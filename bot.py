import asyncio
import logging
import os
import math
import json
import urllib.request
from datetime import datetime
import pytz
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# === НАСТРОЙКИ ===
# Для локального теста впишите токен сюда, для облака он берется из переменных окружения
TOKEN = os.getenv("BOT_TOKEN", "8724200206:AAH8LsWxfSFSzP0EooAGUYygsVStjYtAHTg")

WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))
WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET = "my-secret-string-123"

# URL вашего облачного приложения (Railway/Render выдаст его после создания)
BASE_WEBHOOK_URL = os.getenv("BASE_WEBHOOK_URL", "")

dp = Dispatcher()

# --- ИНСТРУМЕНТЫ (ФУНКЦИИ) ---

def get_weather(city: str) -> str:
    try:
        encoded_city = urllib.parse.quote(city)
        url = f"https://wttr.in/{encoded_city}?format=j1"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            temp = data['current_condition'][0]['temp_C']
            desc = data['current_condition'][0]['weatherDesc'][0]['value']
            return f"В городе {city} сейчас {temp}°C, {desc}."
    except Exception as e:
        return f"Не удалось узнать погоду для {city}. Ошибка."

def get_time(timezone: str) -> str:
    try:
        tz = pytz.timezone(timezone)
        current_time = datetime.now(tz).strftime("%H:%M:%S")
        return f"Текущее время в зоне {timezone}: {current_time}"
    except pytz.UnknownTimeZoneError:
        return f"Неизвестный часовой пояс: {timezone}. Попробуйте Europe/Moscow."

def calculate(expression: str) -> str:
    try:
        safe_expression = expression.replace("^", "**")
        result = eval(safe_expression, {"__builtins__": None}, {"math": math})
        return f"Результат: {result}"
    except Exception:
        return "Ошибка вычисления. Введите простое математическое выражение."

# --- ОБРАБОТЧИКИ ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я умный бот, работаю в облаке.\n"
        "Примеры запросов:\n"
        "1. 'Погода в Москве'\n"
        "2. 'Время в Токио'\n"
        "3. 'Посчитай 2+2*2'"
    )

@dp.message()
async def handle_message(message: types.Message):
    if not message.text:
        return

    text = message.text.lower()

    # Простая логика определения намерения (Intent)
    if "погода" in text or "weather" in text:
        # Пытаемся вытащить город
        words = text.split()
        city = "Москва" # По умолчанию
        if "в" in words:
            idx = words.index("в")
            if idx + 1 < len(words):
                city = words[idx + 1].capitalize()
        elif len(words) > 1:
             city = words[-1].capitalize()
             
        await message.answer("🌤️ Узнаю погоду...")
        res = await asyncio.to_thread(get_weather, city)
        await message.answer(res)

    elif "время" in text or "time" in text:
        # Пытаемся вытащить город/зону
        words = text.split()
        tz = "Europe/Moscow"
        if "в" in words:
            idx = words.index("в")
            if idx + 1 < len(words):
                city_name = words[idx + 1].lower()
                # Очень примитивный маппинг городов в зоны
                if "токио" in city_name: tz = "Asia/Tokyo"
                elif "лондон" in city_name: tz = "Europe/London"
                elif "нью-йорк" in city_name: tz = "America/New_York"
                
        await message.answer("🕒 Смотрю время...")
        res = await asyncio.to_thread(get_time, tz)
        await message.answer(res)

    elif "посчитай" in text or "сколько будет" in text:
        # Извлекаем математическое выражение (все, что похоже на цифры и знаки)
        expr = text.replace("посчитай", "").replace("сколько будет", "").strip()
        res = await asyncio.to_thread(calculate, expr)
        await message.answer(res)

    else:
        await message.answer("Я не понял запрос. Попробуйте спросить про погоду, время или попросите посчитать пример.")

# --- НАСТРОЙКА ВЕБХУКА ДЛЯ ОБЛАКА ---

async def on_startup(bot: Bot):
    if BASE_WEBHOOK_URL:
        await bot.set_webhook(f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}", secret_token=WEBHOOK_SECRET)
        print(f"Webhook установлен на {BASE_WEBHOOK_URL}{WEBHOOK_PATH}")
    else:
        print("ВНИМАНИЕ: BASE_WEBHOOK_URL не задан. Бот не сможет получать сообщения в облаке.")

async def main():
    logging.basicConfig(level=logging.INFO)
    session = AiohttpSession(proxy=None)
    bot = Bot(token=TOKEN, session=session)
    
    dp.startup.register(on_startup)

    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    print(f"Запуск веб-сервера на {WEB_SERVER_HOST}:{WEB_SERVER_PORT}")
    await web._run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == "__main__":
    asyncio.run(main())
