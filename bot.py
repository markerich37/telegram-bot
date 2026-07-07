import asyncio
import json
import re
import logging
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatMemberStatus
from aiogram.client.session.aiohttp import AiohttpSession

# ---------- НАСТРОЙКИ ----------
TELEGRAM_TOKEN = "8632849180:AAGnfTomy83JDvsDBFVeervQWADgbHk97ig"
DEEPSEEK_API_KEY = "sk-53069d0334fb436dae64ac02eefa14d9"
ADMIN_ID = 8002402807  # Твой Telegram ID
SOURCE_CHANNEL = "@wbpoisktovar"

# MTProto прокси (публичный, бесплатный)
# Если этот не сработает — заменим на другой
PROXY_URL = "http://t.me/proxy?server=mtproto.telegram.org.ru&port=443&secret=ee11223344556677889900aabbccddeeff"

# ----------------------------------------

# Для MTProto прокси нужно преобразовать
# Проще использовать готовый HTTP/SOCKS5 прокси для MTProto
# Вот список публичных MTProto прокси (будем пробовать):
MT_PROXY = {
    "server": "mtproto.telegram.org.ru",
    "port": 443,
    "secret": "ee11223344556677889900aabbccddeeff"
}

# Но aiogram не поддерживает MTProto напрямую.
# Поэтому используем socks5 прокси вместо MTProto.

# Публичный SOCKS5 прокси (может не работать, тогда заменим)
SOCKS5_PROXY = "socks5://telegramproxy:proxy@tgproxy.xyz:1080"

# Создаём сессию с прокси
try:
    session = AiohttpSession(proxy=SOCKS5_PROXY)
    bot = Bot(token=TELEGRAM_TOKEN, session=session)
except:
    # Без прокси, если не сработал
    bot = Bot(token=TELEGRAM_TOKEN)

dp = Dispatcher(storage=MemoryStorage())
deepseek = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
logging.basicConfig(level=logging.INFO)

# ---------- ФАЙЛЫ ----------
CHANNELS_FILE = "channels.json"
POSTS_FILE = "posts.json"
STATS_FILE = "stats.json"

def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_channels():
    return load_json(CHANNELS_FILE, [])

def save_channels(channels):
    save_json(CHANNELS_FILE, channels)

def load_posts():
    return load_json(POSTS_FILE, [])

def save_posts(posts):
    save_json(POSTS_FILE, posts)

def load_stats():
    return load_json(STATS_FILE, {})

def save_stats(stats):
    save_json(STATS_FILE, stats)

# ---------- ПРОВЕРКА ПОДПИСКИ ----------
async def check_subscription(user_id: int) -> tuple:
    channels = load_channels()
    not_subscribed = []
    for channel in channels:
        try:
            chat_member = await bot.get_chat_member(chat_id=channel["id"], user_id=user_id)
            if chat_member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
                not_subscribed.append(channel)
        except:
            continue
    return len(not_subscribed) == 0, not_subscribed

def get_channels_keyboard():
    channels = load_channels()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for channel in channels:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"📢 {channel['name']}", url=channel["link"])
        ])
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")
    ])
    return keyboard

# ---------- FSM ----------
class AdminStates(StatesGroup):
    waiting_for_channel_id = State()
    waiting_for_channel_name = State()
    waiting_for_channel_link = State()

class SearchStates(StatesGroup):
    waiting_for_price = State()

# ---------- ЦВЕТА И КАТЕГОРИИ ----------
RAINBOW_COLORS = [
    "🔴 Красный", "🟠 Оранжевый", "🟡 Жёлтый", "🟢 Зелёный",
    "🔵 Голубой", "🔷 Синий", "🟣 Фиолетовый", "⚫ Чёрный",
    "⚪ Белый", "🩷 Розовый", "🩶 Серый", "🟤 Коричневый"
]

CATEGORIES = {
    "outfit": "👔 Аутфит", "tshirt": "👕 Футболка", "shorts": "🩳 Шорты",
    "pants": "👖 Штаны", "jacket": "🧥 Куртка", "shirt": "👔 Рубашка"
}

# ---------- ПАРСИНГ ПОСТОВ ИЗ КАНАЛА ----------
@dp.channel_post()
async def handle_channel_post(message: types.Message):
    if message.chat.username == SOURCE_CHANNEL.replace("@", ""):
        posts = load_posts()
        text = message.text or message.caption or ""
        articles = re.findall(r'\b(\d{8,9})\b', text)
        prices = re.findall(r'(\d+)\s*[₽р]', text)
        rating_match = re.search(r'⭐\s*(\d+[.,]?\d*)', text)
        owner_rating = rating_match.group(1) if rating_match else "Не указана"
        
        color_found = None
        for color in ["красный", "синий", "зелёный", "чёрный", "белый", "жёлтый",
                       "оранжевый", "фиолетовый", "голубой", "розовый", "серый", "коричневый"]:
            if color in text.lower():
                color_found = color
                break
        
        post_data = {
            "message_id": message.message_id,
            "text": text,
            "articles": articles,
            "prices": [int(p) for p in prices],
            "color": color_found,
            "owner_rating": owner_rating,
            "link": f"https://t.me/{SOURCE_CHANNEL.replace('@', '')}/{message.message_id}",
            "date": message.date.isoformat(),
            "has_photo": bool(message.photo),
            "photo_id": message.photo[-1].file_id if message.photo else None
        }
        
        if not any(p["message_id"] == post_data["message_id"] for p in posts):
            posts.append(post_data)
            save_posts(posts)

# ---------- КОМАНДЫ ----------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Начать", callback_data="start_button")]
    ])
    await message.answer(
        "👋 Добро пожаловать в бот по подбору одежды!\n\n"
        "🔍 Я помогу найти лучшие товары с Wildberries из канала @wbpoisktovar.\n\n"
        "⚠️ Для работы необходимо подписаться на каналы.",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "start_button")
async def start_button_handler(callback: types.CallbackQuery):
    is_subscribed, not_subscribed = await check_subscription(callback.from_user.id)
    if not is_subscribed:
        await callback.message.edit_text(
            "👋 Привет! Чтобы пользоваться ботом, нужно подписаться на каналы ниже ⚠️",
            reply_markup=get_channels_keyboard()
        )
    else:
        await callback.message.edit_text(
            "✅ Отлично! Ты подписан на все каналы.\n\n"
            "📋 Доступные команды:\n"
            "🔍 /поиск — подобрать одежду\n"
            "ℹ️ /help — справка"
        )
    await callback.answer()

@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: types.CallbackQuery):
    is_subscribed, not_subscribed = await check_subscription(callback.from_user.id)
    if is_subscribed:
        await callback.message.edit_text("✅ Ты подписан! Доступ открыт.\n🔍 /поиск — подобрать одежду")
    else:
        channels_text = "\n".join([f"• {ch['name']}" for ch in not_subscribed])
        await callback.answer(f"❌ Не подписан на:\n{channels_text}", show_alert=True)
    await callback.answer()

@dp.message(Command("поиск"))
async def cmd_search(message: types.Message):
    is_subscribed, not_subscribed = await check_subscription(message.from_user.id)
    if not is_subscribed:
        await message.answer("⚠️ Подпишись на каналы!", reply_markup=get_channels_keyboard())
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👔 Аутфит", callback_data="cat_outfit")],
        [InlineKeyboardButton(text="👕 Футболка", callback_data="cat_tshirt")],
        [InlineKeyboardButton(text="🩳 Шорты", callback_data="cat_shorts")],
        [InlineKeyboardButton(text="👖 Штаны", callback_data="cat_pants")],
        [InlineKeyboardButton(text="🧥 Куртка", callback_data="cat_jacket")],
        [InlineKeyboardButton(text="👔 Рубашка", callback_data="cat_shirt")],
    ])
    await message.answer("🔍 Выбери категорию:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("cat_"))
async def category_chosen(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.replace("cat_", "")
    await state.update_data(category=category)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Цвет", callback_data="choose_color")],
        [InlineKeyboardButton(text="💰 Цена", callback_data="choose_price")],
    ])
    await callback.message.edit_text(f"📋 Категория: {CATEGORIES.get(category, category)}\nЧто дальше?", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "choose_color")
async def choose_color(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for i in range(0, len(RAINBOW_COLORS), 2):
        row = [InlineKeyboardButton(text=RAINBOW_COLORS[i], callback_data=f"color_{i}")]
        if i + 1 < len(RAINBOW_COLORS):
            row.append(InlineKeyboardButton(text=RAINBOW_COLORS[i + 1], callback_data=f"color_{i+1}"))
        keyboard.inline_keyboard.append(row)
    await callback.message.edit_text("🎨 Выбери цвет:", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("color_"))
async def color_chosen(callback: types.CallbackQuery, state: FSMContext):
    color_name = RAINBOW_COLORS[int(callback.data.replace("color_", ""))].split(" ", 1)[1]
    data = await state.get_data()
    data["color"] = color_name
    await state.set_data(data)
    if "price" not in data:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💲 Указать цену", callback_data="choose_price")],
            [InlineKeyboardButton(text="🔍 Найти без цены", callback_data="search_no_price")],
        ])
        await callback.message.edit_text(f"🎨 Цвет: {color_name}\nУказать цену?", reply_markup=keyboard)
    else:
        await start_search(callback.message, state)
    await callback.answer()

@dp.callback_query(F.data == "choose_price")
async def choose_price(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("💰 Введи максимальную цену (только число):")
    await state.set_state(SearchStates.waiting_for_price)
    await callback.answer()

@dp.message(StateFilter(SearchStates.waiting_for_price))
async def price_entered(message: types.Message, state: FSMContext):
    try:
        price = int(message.text.strip())
        await state.update_data(price=price)
        await start_search(message, state)
    except ValueError:
        await message.answer("❌ Введи число:")

@dp.callback_query(F.data == "search_no_price")
async def search_without_price(callback: types.CallbackQuery, state: FSMContext):
    await start_search(callback.message, state)
    await callback.answer()

async def start_search(message: types.Message, state: FSMContext):
    data = await state.get_data()
    category = data.get("category", "")
    color = data.get("color", "")
    price = data.get("price", None)
    category_name = CATEGORIES.get(category, category)
    
    await message.answer(f"🔍 Ищу: {category_name} | 🎨 {color if color else 'Любой'} | 💰 до {price}₽" if price else f"🔍 Ищу: {category_name} | 🎨 {color if color else 'Любой'}")
    await bot.send_chat_action(message.chat.id, "typing")
    
    posts = load_posts()
    if not posts:
        await message.answer("❌ База пуста. Жди посты из @wbpoisktovar.")
        await state.clear()
        return
    
    color_keywords = {
        "Красный": ["красный", "красная", "красное", "алый"],
        "Оранжевый": ["оранжевый", "оранжевая", "рыжий"],
        "Жёлтый": ["жёлтый", "жёлтая", "желтый", "желтая"],
        "Зелёный": ["зелёный", "зелёная", "зеленый"],
        "Голубой": ["голубой", "голубая"],
        "Синий": ["синий", "синяя"],
        "Фиолетовый": ["фиолетовый", "фиолетовая"],
        "Чёрный": ["чёрный", "чёрная", "черный"],
        "Белый": ["белый", "белая"],
        "Розовый": ["розовый", "розовая"],
        "Серый": ["серый", "серая"],
        "Коричневый": ["коричневый", "коричневая"]
    }
    category_keywords = {
        "outfit": ["аутфит", "комплект", "набор", "образ", "костюм", "лук"],
        "tshirt": ["футболка", "майка", "топ"],
        "shorts": ["шорты"],
        "pants": ["штаны", "брюки", "джинсы"],
        "jacket": ["куртка", "ветровка", "пуховик"],
        "shirt": ["рубашка", "блузка", "поло"]
    }
    
    cat_keys = category_keywords.get(category, [])
    color_keys = color_keywords.get(color, [])
    
    filtered = []
    for post in posts:
        text_lower = post["text"].lower()
        if cat_keys and not any(kw in text_lower for kw in cat_keys):
            continue
        if color_keys and not any(kw in text_lower for kw in color_keys):
            continue
        if price and post["prices"] and sum(post["prices"]) > price:
            continue
        filtered.append(post)
    
    if not filtered:
        await message.answer("😔 Ничего не найдено. /поиск")
        await state.clear()
        return
    
    top = filtered[:20]
    posts_text = ""
    for i, p in enumerate(top, 1):
        posts_text += f"\nПост {i}: {p['text'][:300]}\nАртикулы: {', '.join(p['articles'])}\nЦены: {', '.join(str(pr)+'₽' for pr in p['prices'])}\nОценка: {p['owner_rating']}\nСсылка: {p['link']}\n---\n"
    
    prompt = f"""Найди лучшие варианты:
Категория: {category_name}
Цвет: {color or 'Любой'}
Цена до: {price}₽

База:
{posts_text}

Верни ТОЛЬКО JSON:
{{"found":true,"items":[{{"link":"url","articles":["арт"],"prices":[100],"total_price":100,"color":"цвет","owner_rating":"5","ai_rating":8,"comment":"коммент"}}]}}"""

    try:
        response = await deepseek.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role":"user","content":prompt}],
            temperature=0.3
        )
        answer = response.choices[0].message.content
        json_match = re.search(r'\{.*\}', answer, re.DOTALL)
        result = json.loads(json_match.group() if json_match else answer)
        
        if not result.get("items"):
            await message.answer("😔 Ничего. /поиск")
            await state.clear()
            return
        
        items = sorted(result["items"], key=lambda x: x.get("ai_rating", 0), reverse=True)
        await message.answer(f"🎯 Нашёл {len(items)} вариантов!")
        
        for idx, item in enumerate(items[:10], 1):
            text = f"""
{'='*30}
🔹 #{idx}
⭐ Оценка владельца: {item.get('owner_rating','—')}
🤖 Оценка ИИ: {item.get('ai_rating','—')}/10
🎨 Цвет: {item.get('color','—')}
📦 Артикулы: {', '.join(item.get('articles',[]))}
💰 Цены: {' + '.join(str(p)+'₽' for p in item.get('prices',[]))}
💵 Общая: {item.get('total_price','—')}₽
🔗 {item.get('link','')}
{'='*30}"""
            await message.answer(text)
        
        await message.answer("✨ Для нового поиска: /поиск")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("❌ Ошибка. Попробуй позже: /поиск")
    
    await state.clear()

# ---------- АДМИНКА ----------
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Нет доступа.")
        return
    channels = load_channels()
    channels_list = "\n".join([f"• {ch['name']} ({ch['id']})" for ch in channels]) if channels else "❌ Нет каналов"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить канал", callback_data="admin_add_channel")],
        [InlineKeyboardButton(text="➖ Удалить канал", callback_data="admin_delete_channel")],
    ])
    await message.answer(f"🔧 Админ-панель\n\n📢 Каналы:\n{channels_list}", reply_markup=keyboard)

@dp.callback_query(F.data == "admin_add_channel")
async def add_channel_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📝 Введи ID канала (@name или -100...):")
    await state.set_state(AdminStates.waiting_for_channel_id)
    await callback.answer()

@dp.message(StateFilter(AdminStates.waiting_for_channel_id))
async def add_channel_id(message: types.Message, state: FSMContext):
    await state.update_data(channel_id=message.text.strip())
    await message.answer("📝 Название канала:")
    await state.set_state(AdminStates.waiting_for_channel_name)

@dp.message(StateFilter(AdminStates.waiting_for_channel_name))
async def add_channel_name(message: types.Message, state: FSMContext):
    await state.update_data(channel_name=message.text.strip())
    await message.answer("🔗 Ссылка (https://t.me/...):")
    await state.set_state(AdminStates.waiting_for_channel_link)

@dp.message(StateFilter(AdminStates.waiting_for_channel_link))
async def add_channel_link(message: types.Message, state: FSMContext):
    data = await state.get_data()
    channels = load_channels()
    channels.append({"id": data["channel_id"], "name": data["channel_name"], "link": message.text.strip()})
    save_channels(channels)
    await message.answer(f"✅ Канал '{data['channel_name']}' добавлен!")
    await state.clear()

@dp.callback_query(F.data == "admin_delete_channel")
async def delete_channel_start(callback: types.CallbackQuery):
    channels = load_channels()
    if not channels:
        await callback.message.edit_text("❌ Нет каналов.")
        await callback.answer()
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ch["name"], callback_data=f"del_{ch['id']}")] for ch in channels
    ])
    await callback.message.edit_text("🗑 Выбери канал:", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("del_"))
async def delete_channel_confirm(callback: types.CallbackQuery):
    channel_id = callback.data[4:]
    channels = load_channels()
    channels = [ch for ch in channels if ch["id"] != channel_id]
    save_channels(channels)
    await callback.message.edit_text("✅ Удалён!")
    await callback.answer()

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("ℹ️ /поиск — подобрать одежду\n🔍 Категории, цвет, цена\n🤖 DeepSeek подбирает из @wbpoisktovar")

@dp.message()
async def handle_any_message(message: types.Message):
    await message.answer("🤔 Используй /поиск или /help")

# ---------- ЗАПУСК ----------
async def main():
    if not load_channels():
        save_channels([])
    if not load_posts():
        save_posts([])
    if not load_stats():
        save_stats({})
    
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())