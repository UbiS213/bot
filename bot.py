import asyncio
import logging
import os
import math
import json
import urllib.request
import urllib.parse
from datetime import datetime
import pytz
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# === НАСТРОЙКИ ===
TOKEN = os.getenv("BOT_TOKEN", "8724200206:AAH8LsWxfSFSzP0EooAGUYygsVStjYtAHTg")
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))
WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET = "my-secret-string-123"
BASE_WEBHOOK_URL = os.getenv("BASE_WEBHOOK_URL", "")

dp = Dispatcher()

# --- ФУНКЦИИ ---

def get_coordinates(city: str):
    """Получает широту и долготу по названию города через Open-Meteo Geocoding API."""
    try:
        encoded_city = urllib.parse.quote(city)
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_city}&count=1&language=ru&format=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            if "results" in data and len(data["results"]) > 0:
                return data["results"][0]["latitude"], data["results"][0]["longitude"], data["results"][0]["name"]
            else:
                return None, None, None
    except Exception:
        return None, None, None

def get_weather(city: str) -> str:
    """Получает реальную температуру через Open-Meteo API."""
    lat, lon, found_city = get_coordinates(city)
    if lat is None:
        return f"Не удалось найти город {city}. Попробуйте другое название."

    try:
        # Запрашиваем текущую температуру и скорость ветра
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code&timezone=auto"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if "current" in data:
                temp = data["current"]["temperature_2m"]
                # Простое описание по коду погоды (можно расширить)
                weather_code = data["current"].get("weather_code", 0)
                if weather_code in [0, 1]:
                    desc = "ясно"
                elif weather_code in [2, 3]:
                    desc = "облачно"
                elif weather_code in [45, 48]:
                    desc = "туман"
                elif weather_code in [51, 53, 55, 61, 63, 65]:
                    desc = "дождь"
                elif weather_code in [71, 73, 75]:
                    desc = "снег"
                else:
                    desc = "переменная облачность"
                
                return f"В городе {found_city} сейчас {temp}°C, {desc}."
            else:
                return "Не удалось получить данные о погоде."
    except Exception:
        return "Ошибка при запросе к сервису погоды. Попробуйте позже."

def get_time(timezone: str) -> str:
    try:
        tz = pytz.timezone(timezone)
        current_time = datetime.now(tz).strftime("%H:%M:%S")
        return f"Текущее время в зоне {timezone}: {current_time}"
    except pytz.UnknownTimeZoneError:
        return f"Неизвестный часовой пояс: {timezone}."

def calculate(expression: str) -> str:
    try:
        safe_expression = expression.replace("^", "**")
        result = eval(safe_expression, {"__builtins__": None}, {"math": math})
        return f"Результат: {result}"
    except Exception:
        return "Ошибка вычисления."

# --- ОБРАБОТЧИКИ ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я умный бот.\n"
        "1. 'Погода в Москве'\n"
        "2. 'Время в Якутск'\n"
        "3. 'Посчитай 2+2*2'"
    )

@dp.message()
async def handle_message(message: types.Message):
    if not message.text:
        return
    text = message.text.lower()

    if "погода" in text or "weather" in text:
        words = text.split()
        city = "Москва"
        if "в" in words:
            idx = words.index("в")
            if idx + 1 < len(words):
                city = words[idx + 1].capitalize()
        elif len(words) > 1:
             city = words[-1].capitalize()
             
        await message.answer("🌤️ Узнаю реальную погоду...")
        res = await asyncio.to_thread(get_weather, city)
        await message.answer(res)

    elif "время" in text or "time" in text:
        words = text.split()
        tz = "Europe/Moscow"
        if "в" in words:
            idx = words.index("в")
            if idx + 1 < len(words):
                city_name = words[idx + 1].lower()
                if "токио" in city_name: tz = "Asia/Tokyo"
                elif "лондон" in city_name: tz = "Europe/London"
                elif "нью-йорк" in city_name: tz = "America/New_York"
                elif "якутск" in city_name: tz = "Asia/Yakutsk"
                elif "новосибирск" in city_name: tz = "Asia/Novosibirsk"
                elif "екатеринбург" in city_name: tz = "Asia/Yekaterinburg"
                elif "владивосток" in city_name: tz = "Asia/Vladivostok"
                elif "калининград" in city_name: tz = "Europe/Kaliningrad"
                
        await message.answer("🕒 Смотрю время...")
        res = await asyncio.to_thread(get_time, tz)
        await message.answer(res)

    elif "посчитай" in text or "сколько будет" in text:
        expr = text.replace("посчитай", "").replace("сколько будет", "").strip()
        res = await asyncio.to_thread(calculate, expr)
        await message.answer(res)

    else:
        await message.answer("Не понял. Спросите про погоду, время или попросите посчитать.")

# --- ВЕБХУК ---

async def on_startup(bot: Bot):
    if BASE_WEBHOOK_URL:
        await bot.set_webhook(f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}", secret_token=WEBHOOK_SECRET)
        print(f"Webhook установлен на {BASE_WEBHOOK_URL}{WEBHOOK_PATH}")
    else:
        print("ВНИМАНИЕ: BASE_WEBHOOK_URL не задан.")

async def main():
    logging.basicConfig(level=logging.INFO)
    session = AiohttpSession(proxy=None)
    bot = Bot(token=TOKEN, session=session)
    
    dp.startup.register(on_startup)
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    print(f"Запуск на {WEB_SERVER_HOST}:{WEB_SERVER_PORT}")
    await web._run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == "__main__":
    asyncio.run(main())
