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

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY, 
    username TEXT,
    is_premium INTEGER DEFAULT 0
)""")

cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
conn.commit()

cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('channel_id', '-100123456789')")
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('channel_url', 'https://t.me/Sizning_Kanalingiz')")
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('premium_info', 'https://t.me/kazino_apklari')")
conn.commit()

# --- SIZ BERGAN PREMIUM STIKER ID-LARI ---
APPLE_GAME_EMOJI_ID = "5291842511210304612"  # Apple Game boshlash va Natija uchun
STEP_EMOJI_ID = "5775937998948404844"        # Bosqich tugmasi uchun
WARNING_EMOJI_ID = "5274099962655816924"     # Ogohlantirish xabari uchun

# Start tugmalari uchun siz bergan ID-lar:
OBUNA_EMOJI_ID = "5460656136355069089"       # Obuna bo'lish uchun
TEKSHIRISH_EMOJI_ID = "5461053708592759113"   # Tekshirish uchun
PREMIUM_EMOJI_ID = "5271998448042785916"      # PREMIUM sotib olish uchun

# --- STATE (HOLAT)LAR ---
class AdminStates(StatesGroup):
    waiting_for_ad_text = State()
    waiting_for_channel_id = State()
    waiting_for_channel_url = State()
    waiting_give_premium = State()
    waiting_take_premium = State()

class GameStates(StatesGroup):
    playing = State()

# --- YORDAMCHI FUNKSIYALAR ---
def get_settings():
    cursor.execute("SELECT value FROM settings WHERE key='channel_id'")
    ch_id = int(cursor.fetchone()[0])
    cursor.execute("SELECT value FROM settings WHERE key='channel_url'")
    ch_url = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key='premium_info'")
    p_info = cursor.fetchone()[0]
    return ch_id, ch_url, p_info

async def check_subscription(user_id: int) -> bool:
    cursor.execute("SELECT is_premium FROM users WHERE user_id=?", (user_id,))
    res = cursor.fetchone()
    if res and res[0] == 1:
        return True

    channel_id, _, _ = get_settings()
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR]
    except Exception as e:
        logging.error(f"A'zolik tekshirishda xato: {e}")
        return True 

# --- KLAVIATURALAR ---
def get_main_keyboard(user_id):
    buttons = [[KeyboardButton(text="🍏 Apple Game boshlash")]]
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
            [KeyboardButton(text="💎 Premium berish"), KeyboardButton(text="❌ Premium olib qo'yish")],
            [KeyboardButton(text="⬅️ Bosh menyuga qaytish")]
        ],
        resize_keyboard=True
    )

# --- HANDLERLAR ---

@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    _, channel_url, p_info = get_settings()
    
    cursor.execute("SELECT user_id FROM users WHERE user_id=?", (message.from_user.id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, username, is_premium) VALUES (?, ?, 0)", 
                       (message.from_user.id, message.from_user.username))
        conn.commit()

    if await check_subscription(message.from_user.id):
        await message.answer(
            f"Xush kelibsiz! O'yinni boshlash uchun pastdagi <tg-emoji emoji-id=\"{APPLE_GAME_EMOJI_ID}\">🍏</tg-emoji> <b>Apple Game boshlash</b> tugmasini bosing:", 
            reply_markup=get_main_keyboard(message.from_user.id)
        )
    else:
        # Majburiy obuna inline tugmalari
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛡️ Obuna bo'lish", url=channel_url)],
            [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")],
            [InlineKeyboardButton(text="💎 «PREMIUM» olish", url=p_info)]
        ])
        
        # Siz bergan 3 ta maxsus stikerni matn ichida tugmalarga moslab chiqaramiz:
        await message.answer(
            f"⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling!</b>\n\n"
            f"<tg-emoji emoji-id=\"{OBUNA_EMOJI_ID}\">📢</tg-emoji> — Pastdagi tugma orqali a'zo bo'ling\n"
            f"<tg-emoji emoji-id=\"{TEKSHIRISH_EMOJI_ID}\">✅</tg-emoji> — Keyin a'zolikni tekshiring\n"
            f"<tg-emoji emoji-id=\"{PREMIUM_EMOJI_ID}\">💎</tg-emoji> — Yoki cheklovlarni butunlay olib tashlang!", 
            reply_markup=markup,
            parse_mode="HTML"
        )

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: CallbackQuery):
    if await check_subscription(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer("Rahmat! Endi cheklovlarsiz o'ynashingiz mumkin. 🎉", reply_markup=get_main_keyboard(callback.from_user.id))
    else:
        await callback.answer("❌ Hali kanalga a'zo bo'lmadingiz yoki Premium emassiz!", show_alert=True)

# --- BOSQICHMA-BOSQICH O'YIN LOGIKASI ---

@dp.message(F.text == "🍏 Apple Game boshlash")
async def start_game_handler(message: Message, state: FSMContext):
    if not await check_subscription(message.from_user.id):
        return
    
    await state.set_state(GameStates.playing)
    await state.update_data(current_step=1, steps_log="")
    
    await message.answer(
        f"O'yin boshlandi! 1-bosqich raqamini olish uchun pastdagi <tg-emoji emoji-id=\"{STEP_EMOJI_ID}\">🎲</tg-emoji> tugmasini bosing👇", 
        reply_markup=get_game_keyboard(1)
    )

@dp.message(GameStates.playing, F.text.regexp(r"^🎲 \d+-bosqich raqamini olish$"))
async def play_step_handler(message: Message, state: FSMContext):
    if not await check_subscription(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    step = data.get("current_step", 1)
    steps_log = data.get("steps_log", "")

    num = random.randint(1, 5)
    new_log = steps_log + f"{step}-bosqich: <b>{num}</b>\n"
    
    # 1. Natijalar xabari (Boshida premium stiker bilan)
    await message.answer(
        f"<tg-emoji emoji-id=\"{APPLE_GAME_EMOJI_ID}\">🍏</tg-emoji> <b>Apple Game Natijalari:</b>\n\n{new_log}"
    )
    
    # 2. Ogohlantirish xabari (Boshida premium ogohlantirish stikeri bilan)
    await message.answer(
        f"<tg-emoji emoji-id=\"{WARNING_EMOJI_ID}\">🔴</tg-emoji> <b>Ogohlantirish</b>\n\n"
        f"Ushbu bot faqat https://t.me/kazino_apklari kanalidagi ilovalarda ishlaydi."
    )

    if step < 10:
        next_step = step + 1
        await state.update_data(current_step=next_step, steps_log=new_log)
        await message.answer(
            f"Keyingi <tg-emoji emoji-id=\"{STEP_EMOJI_ID}\">🎲</tg-emoji> {next_step}-bosqichni boshlash uchun pastdagi tugmani bosing:", 
            reply_markup=get_game_keyboard(next_step)
        )
    else:
        await state.clear()
        promo_code = random.randint(100000, 999999)
        await message.answer(
            f"🎉 <b>Tabriklaymiz! Siz 10 ta bosqichdan muvaffaqiyatli o'tdingiz!</b>\n\n"
            f"Sizning maxsus kodingiz: <code>{promo_code}</code>\n\n"
            f"Yangi o'yin boshlash uchun pastdagi tugmani bosing 👇",
            reply_markup=get_restart_keyboard()
        )

@dp.message(F.text == "🔄 Qaytadan o'ynash")
async def restart_handler(message: Message):
    await message.answer("Bosh menyudasiz. Yangi o'yinni boshlang:", reply_markup=get_main_keyboard(message.from_user.id))

# --- ADMIN PANEL ---

@dp.message(F.text == "🔐 Admin Panel")
async def admin_panel_handler(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🛠 Admin Panel:", reply_markup=get_admin_keyboard())

@dp.message(F.text == "⬅️ Bosh menyuga qaytish")
async def back_handler(message: Message):
    await message.answer("Bosh menyuga qaytdingiz.", reply_markup=get_main_keyboard(message.from_user.id))

@dp.message(F.text == "📊 Statistika")
async def stat_handler(message: Message):
    if message.from_user.id == ADMIN_ID:
        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium=1")
        premiums = cursor.fetchone()[0]
        await message.answer(
            f"📊 <b>Bot Statistikasi:</b>\n\n"
            f"👤 Jami foydalanuvchilar: <b>{total}</b> ta\n"
            f"💎 Premium a'zolar: <b>{premiums}</b> ta"
        )

# --- KANAL VA PREMIUM LINK SOZLASH (ADMIN) ---
@dp.message(F.text == "⚙️ Kanal ID sozlash")
async def set_channel_id_start(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        ch_id, _, _ = get_settings()
        await message.answer(f"Hozirgi Kanal ID: <code>{ch_id}</code>\n\nYangi ID kiriting (masalan: -100123456789):")
        await state.set_state(AdminStates.waiting_for_channel_id)

@dp.message(AdminStates.waiting_for_channel_id)
async def set_channel_id_save(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        new_id = message.text.strip()
        cursor.execute("UPDATE settings SET value=? WHERE key='channel_id'", (new_id,))
        conn.commit()
        await state.clear()
        await message.answer(f"✅ Kanal ID o'zgardi: <code>{new_id}</code>", reply_markup=get_admin_keyboard())

@dp.message(F.text == "⚙️ Kanal Link sozlash")
async def set_channel_url_start(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        _, ch_url, _ = get_settings()
        await message.answer(f"Hozirgi Kanal Link: {ch_url}\n\nYangi link yuboring:")
        await state.set_state(AdminStates.waiting_for_channel_url)

@dp.message(AdminStates.waiting_for_channel_url)
async def set_channel_url_save(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        new_url = message.text.strip()
        cursor.execute("UPDATE settings SET value=? WHERE key='channel_url'", (new_url,))
        conn.commit()
        await state.clear()
        await message.answer(f"✅ Kanal havolasi o'zgardi: {new_url}", reply_markup=get_admin_keyboard())

# --- PREMIUM BERISH / OLISH (ADMIN) ---
@dp.message(F.text == "💎 Premium berish")
async def give_premium_start(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Premium beriladigan foydalanuvchining shaxsiy Telegram ID raqamini yuboring:")
        await state.set_state(AdminStates.waiting_give_premium)

@dp.message(AdminStates.waiting_give_premium)
async def give_premium_save(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        target_id = message.text.strip()
        try:
            cursor.execute("UPDATE users SET is_premium=1 WHERE user_id=?", (target_id,))
            conn.commit()
            await state.clear()
            await message.answer(f"✅ Foydalanuvchiga (ID: {target_id}) muvaffaqiyatli <b>Premium</b> maqomi berildi!", reply_markup=get_admin_keyboard())
            try:
                await bot.send_message(chat_id=target_id, text="🎉 <b>Tabriklaymiz! Sizga botda PREMIUM maqomi berildi!</b>\nEndi botdan kanallarga a'zo bo'lmasdan foydalana olasiz.")
            except:
                pass
        except Exception as e:
            await message.answer(f"❌ Xato yuz berdi: {e}")

@dp.message(F.text == "❌ Premium olib qo'yish")
async def take_premium_start(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Premium maqomi olib qo'yiladigan foydalanuvchining Telegram ID raqamini kiriting:")
        await state.set_state(AdminStates.waiting_take_premium)

@dp.message(AdminStates.waiting_take_premium)
async def take_premium_save(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        target_id = message.text.strip()
        try:
            cursor.execute("UPDATE users SET is_premium=0 WHERE user_id=?", (target_id,))
            conn.commit()
            await state.clear()
            await message.answer(f"✅ Foydalanuvchidan (ID: {target_id}) Premium maqomi muvaffaqiyatli olib qo'yildi.", reply_markup=get_admin_keyboard())
        except Exception as e:
            await message.answer(f"❌ Xato yuz berdi: {e}")

# --- BROADCAST (REKLAMA) ---
@dp.message(F.text == "✉️ Xabar yuborish")
async def broadcast_start(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Reklama xabarini (matn, rasm, video) yuboring:")
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
        await message.answer(f"✅ Xabar {count} ta foydalanuvchiga muvaffaqiyatli yuborildi!", reply_markup=get_admin_keyboard())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
