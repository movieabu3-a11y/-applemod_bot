import asyncio
import logging
import random
import sqlite3
import os
from dotenv import load_dotenv
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

load_dotenv()

TOKEN = os.getenv("TOKEN") 
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# --- BAZA BILAN ISHLASH ---
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

# Foydalanuvchilar jadvali
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT)")
# Sozlamalar jadvali (Kanal sozlamalari uchun)
cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
conn.commit()

# Baza uchun boshlang'ich sozlamalar (agar mavjud bo'lmasa)
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('channel_id', '-100123456789')")
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('channel_url', 'https://t.me/Sizning_Kanalingiz')")
conn.commit()

# --- STATE (HOLAT)LAR ---
class AdminStates(StatesGroup):
    waiting_for_ad_text = State()
    waiting_for_channel_id = State()
    waiting_for_channel_url = State()

class GameStates(StatesGroup):
    playing = State()

# --- ODDIY FUNKSIYALAR ---
def get_channel_settings():
    cursor.execute("SELECT value FROM settings WHERE key='channel_id'")
    ch_id = int(cursor.fetchone()[0])
    cursor.execute("SELECT value FROM settings WHERE key='channel_url'")
    ch_url = cursor.fetchone()[0]
    return ch_id, ch_url

async def check_subscription(user_id: int) -> bool:
    channel_id, _ = get_channel_settings()
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR]
    except Exception as e:
        logging.error(f"Kanal a'zoligini tekshirishda xatolik: {e}")
        return True # Xatolik bo'lsa bot to'xtab qolmasligi uchun True qaytaramiz

# --- KLAVIATURALAR ---
def get_main_keyboard(user_id):
    buttons = [[KeyboardButton(text="🍎 Apple Game boshlash")]]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="🔐 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_game_keyboard(step):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=f"🎲 {step}-bosqich raqamini olish")]],
        resize_keyboard=True
    )

def get_restart_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔄 Qaytadan o'ynash")]],
        resize_keyboard=True
    )

def get_admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="✉️ Xabar yuborish")],
            [KeyboardButton(text="⚙️ Kanal ID sozlash"), KeyboardButton(text="⚙️ Kanal Link sozlash")],
            [KeyboardButton(text="⬅️ Bosh menyuga qaytish")]
        ],
        resize_keyboard=True
    )

# --- HANDLERLAR ---

@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    _, channel_url = get_channel_settings()
    
    try:
        cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", 
                       (message.from_user.id, message.from_user.username))
        conn.commit()
    except Exception as e:
        logging.error(f"Baza xatoligi: {e}")

    if await check_subscription(message.from_user.id):
        await message.answer("Xush kelibsiz! O'yinni boshlash uchun quyidagi tugmani bosing:", reply_markup=get_main_keyboard(message.from_user.id))
    else:
        await message.answer(
            "⚠️ Botdan foydalanish uchun kanalga a'zo bo'ling!", 
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=channel_url)], 
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

# --- BOSQICHMA-BOSQICH O'YIN LOGIKASI ---

@dp.message(F.text == "🍎 Apple Game boshlash")
async def start_game_handler(message: Message, state: FSMContext):
    if not await check_subscription(message.from_user.id):
        return
    
    await state.set_state(GameStates.playing)
    await state.update_data(current_step=1, steps_log="")
    await message.answer("O'yin boshlandi! 1-bosqich raqamini olish uchun tugmani bosing👇", reply_markup=get_game_keyboard(1))

@dp.message(GameStates.playing, F.text.regexp(r"^🎲 \d+-bosqich raqamini olish$"))
async def play_step_handler(message: Message, state: FSMContext):
    if not await check_subscription(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    step = data.get("current_step", 1)
    steps_log = data.get("steps_log", "")

    # Random raqam (1 dan 5 gacha)
    num = random.randint(1, 5)
    new_log = steps_log + f"{step}-bosqich: <b>{num}</b>\n"
    
    # Random raqam xabari
    await message.answer(f"🍎 <b>Apple Game Natijalari:</b>\n\n{new_log}")
    
    # Har doim ortidan keladigan majburiy ogohlantirish xabari
    await message.answer(
        "<b>Ogohlantirish 🔴</b>\n\n"
        "Ushbu bot faqat https://t.me/kazino_apklari kanalidagi ilovalarda ishlaydi."
    )

    if step < 10:
        # Keyingi bosqich tugmasini chiqarish
        next_step = step + 1
        await state.update_data(current_step=next_step, steps_log=new_log)
        await message.answer(f"{next_step}-bosqichni boshlash uchun bosing:", reply_markup=get_game_keyboard(next_step))
    else:
        # 10-bosqich yakunlandi, promo-kod beramiz va qayta o'ynash tugmasi chiqadi
        await state.clear()
        promo_code = random.randint(100000, 999999)
        await message.answer(
            f"🎉 <b>Tabriklaymiz! Siz 10 ta bosqichdan muvaffaqiyatli o'tdingiz!</b>\n\n"
            f"Sizning maxsus kodingiz: <code>{promo_code}</code>\n\n"
            "Yangi o'yin boshlash uchun pastdagi tugmani bosing 👇",
            reply_markup=get_restart_keyboard()
        )

@dp.message(F.text == "🔄 Qaytadan o'ynash")
async def restart_handler(message: Message):
    await message.answer("Bosh menyudasiz. Yangi o'yinni boshlang:", reply_markup=get_main_keyboard(message.from_user.id))

# --- ADMIN PANEL ---

@dp.message(F.text == "🔐 Admin Panel")
async def admin_panel_handler(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🛠 Admin Panelga xush kelibsiz! Kerakli bo'limni tanlang:", reply_markup=get_admin_keyboard())

@dp.message(F.text == "⬅️ Bosh menyuga qaytish")
async def back_handler(message: Message):
    await message.answer("Bosh menyuga qaytdingiz.", reply_markup=get_main_keyboard(message.from_user.id))

@dp.message(F.text == "📊 Statistika")
async def stat_handler(message: Message):
    if message.from_user.id == ADMIN_ID:
        cursor.execute("SELECT COUNT(*) FROM users")
        await message.answer(f"📊 Bot foydalanuvchilari soni: <b>{cursor.fetchone()[0]}</b> ta")

# --- KANAL ID SOZLASH (ADMIN) ---
@dp.message(F.text == "⚙️ Kanal ID sozlash")
async def set_channel_id_start(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        ch_id, _ = get_channel_settings()
        await message.answer(f"Hozirgi Kanal ID: <code>{ch_id}</code>\n\nYangi kanal ID raqamini kiriting (masalan: -100123456789):")
        await state.set_state(AdminStates.waiting_for_channel_id)

@dp.message(AdminStates.waiting_for_channel_id)
async def set_channel_id_save(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        new_id = message.text.strip()
        cursor.execute("UPDATE settings SET value=? WHERE key='channel_id'", (new_id,))
        conn.commit()
        await state.clear()
        await message.answer(f"✅ Kanal ID muvaffaqiyatli o'zgartirildi: <code>{new_id}</code>", reply_markup=get_admin_keyboard())

# --- KANAL LINK SOZLASH (ADMIN) ---
@dp.message(F.text == "⚙️ Kanal Link sozlash")
async def set_channel_url_start(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        _, ch_url = get_channel_settings()
        await message.answer(f"Hozirgi Kanal Link: {ch_url}\n\nYangi kanal havolasini yuboring (masalan: https://t.me/...):")
        await state.set_state(AdminStates.waiting_for_channel_url)

@dp.message(AdminStates.waiting_for_channel_url)
async def set_channel_url_save(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        new_url = message.text.strip()
        cursor.execute("UPDATE settings SET value=? WHERE key='channel_url'", (new_url,))
        conn.commit()
        await state.clear()
        await message.answer(f"✅ Kanal havolasi muvaffaqiyatli o'zgartirildi: {new_url}", reply_markup=get_admin_keyboard())

# --- USERLARGA REKLAMA XABARI YUBORISH (ADMIN) ---
@dp.message(F.text == "✉️ Xabar yuborish")
async def broadcast_start(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Foydalanuvchilarga yuboriladigan xabar matnini (rasm yoki video ham bo'lishi mumkin) yuboring:")
        await state.set_state(AdminStates.waiting_for_ad_text)

@dp.message(AdminStates.waiting_for_ad_text)
async def broadcast_send(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        count = 0
        for user in users:
            try:
                await message.copy_to(user[0])
                count += 1
            except:
                pass
        await state.clear()
        await message.answer(f"✅ Xabar muvaffaqiyatli {count} ta foydalanuvchiga yuborildi!", reply_markup=get_admin_keyboard())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
