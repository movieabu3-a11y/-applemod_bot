import asyncio
import logging
import random
import sqlite3
import os
from dotenv import load_dotenv # .env faylidan ma'lumotlarni o'qish uchun
from aiogram import Bot, Dispatcher, html, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, KeyboardButton, ReplyKeyboardMarkup, 
    InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# .env faylini yuklaymiz
load_dotenv()

# --- SOZLAMALAR (XAVFSIZ USUL) ---
# Token va ID-raqamlar hosting panelidan yoki .env faylidan o'qiladi
TOKEN = os.getenv("TOKEN") 
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/Sizning_Kanalingiz")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# --- BAZA VA FSM ---
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT)")
conn.commit()

class AdminStates(StatesGroup):
    waiting_for_ad_text = State()

# --- KLAVIATURALAR ---
def get_main_keyboard(user_id):
    buttons = [[KeyboardButton(text="🍎 Apple Game raqam")]]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="🔐 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_restart_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔄 Qaytadan boshlash")]],
        resize_keyboard=True
    )

def get_admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="✉️ Xabar yuborish")],
            [KeyboardButton(text="⬅️ Bosh menyuga qaytish")]
        ],
        resize_keyboard=True
    )

# --- FUNKSIYALAR ---
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR]
    except:
        return True 

# --- HANDLERLAR ---
@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    
    try:
        cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", 
                       (message.from_user.id, message.from_user.username))
        conn.commit()
    except Exception as e:
        logging.error(f"Baza xatoligi: {e}")

    if await check_subscription(message.from_user.id):
        await message.answer("Xush kelibsiz! O'yinni boshlash uchun tugmani bosing:", reply_markup=get_main_keyboard(message.from_user.id))
    else:
        await message.answer(
            "⚠️ Botdan foydalanish uchun kanalga a'zo bo'ling!", 
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=CHANNEL_URL)], 
                [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")]
            ])
        )

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: CallbackQuery):
    if await check_subscription(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer("Rahmat! Endi o'ynashingiz mumkin.", reply_markup=get_main_keyboard(callback.from_user.id))
    else:
        await callback.answer("❌ Hali a'zo bo'lmadingiz!", show_alert=True)

# --- O'YIN LOGIKASI ---
@dp.message(F.text == "🍎 Apple Game raqam")
async def apple_game_handler(message: Message):
    if not await check_subscription(message.from_user.id):
        return
    
    numbers = [random.randint(1, 5) for _ in range(10)]
    result_text = "🍎 <b>Apple Game Natijalari:</b>\n\n"
    for i, num in enumerate(numbers, 1):
        result_text += f"{i}-bos
