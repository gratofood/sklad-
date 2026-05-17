import os
import json
import re
import logging
import telebot
from dotenv import load_dotenv

# =============================================
# 📋 LOGGING — Xatolarni kuzatish tizimi
# =============================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# =============================================
# ⚙️ SOZLAMALAR — .env fayldan o'qiladi
# =============================================
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError(
        "❌ TELEGRAM_TOKEN topilmadi!\n"
        "   .env faylga haqiqiy tokeningizni yozing.\n"
        "   Tokenni @BotFather dan olishingiz mumkin."
    )

SKLAD_FILE = "sklad.json"

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Groq klient — faqat ovozli xabar uchun kerak (ixtiyoriy)
groq_client = None
if GROQ_API_KEY:
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_API_KEY)
        logger.info("✅ Groq API ulandi — ovozli xabarlar ishlaydi")
    except Exception as e:
        logger.warning(f"⚠️ Groq API ulanmadi: {e}")
else:
    logger.warning("⚠️ GROQ_API_KEY topilmadi. Ovozli xabarlar ishlamaydi.")


# =============================================
# 📂 SKLAD FAYL OPERATSIYALARI
# =============================================
def load_sklad():
    """Sklad ma'lumotlarini fayldan o'qish"""
    try:
        if os.path.exists(SKLAD_FILE):
            with open(SKLAD_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"❌ sklad.json o'qishda xato: {e}")
    return {}


def save_sklad(sklad):
    """Sklad ma'lumotlarini faylga saqlash"""
    try:
        with open(SKLAD_FILE, "w", encoding="utf-8") as f:
            json.dump(sklad, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"❌ sklad.json saqlashda xato: {e}")


# =============================================
# 🎤 OVOZ → MATN (Groq Whisper)
# =============================================
def voice_to_text(file_path):
    """Ovozli xabarni matnga aylantirish"""
    if not groq_client:
        raise RuntimeError("GROQ_API_KEY sozlanmagan — ovozli xabar ishlamaydi")
    with open(file_path, "rb") as audio_file:
        transcript = groq_client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=audio_file,
            language="uz"
        )
    return transcript.text


# =============================================
# 🧠 BUYRUQ TAHLILI
# =============================================
KIRIM_WORDS = [
    "kirim", "kiritildi", "keldi", "qo'shildi", "qoshildi",
    "qo'sh", "qosh", "kirgiz", "kirdi", "olib keldi"
]
CHIQIM_WORDS = [
    "sotdim", "sotildi", "chiqim", "chiqdi", "berildi",
    "olindi", "yuborildi", "ketdi", "chiqarildi"
]
STOP_WORDS = KIRIM_WORDS + CHIQIM_WORDS + [
    "ta", "dona", "kg", "litr", "kilo", "gramm"
]


def extract_product_name(text):
    """Matndan mahsulot nomini ajratib olish"""
    name = text
    name = re.sub(r"\d+", "", name)  # Sonlarni olib tashlash
    # Uzun so'zlarni avval olib tashlash (masalan "kiritildi" → "kirim" emas)
    for word in sorted(STOP_WORDS, key=len, reverse=True):
        name = re.sub(r"\b" + re.escape(word) + r"\b", "", name)
    name = re.sub(r"\s{2,}", " ", name).strip()
    return name


def parse_command(text):
    """Foydalanuvchi xabarini tahlil qilish va buyruqni aniqlash"""
    t = text.strip().lower()

    # Sklad ko'rish
    if any(w in t for w in ["sklad", "nechta", "qancha", "ko'rish", "ombor", "список"]):
        return ("sklad", None, None)

    # "nima bor" — sklad ko'rish
    if re.search(r"\bnima\b.*\bbor\b", t):
        return ("sklad", None, None)

    # Tozalash
    if any(w in t for w in ["tozala", "clear", "o'chir hammasi"]):
        return ("tozala", None, None)

    # Yordam
    if any(w in t for w in ["yordam", "help"]):
        return ("yordam", None, None)

    # Son topish
    qty_match = re.search(r"(\d+)", t)
    qty = int(qty_match.group(1)) if qty_match else None

    # Mahsulot nomini tozalash
    name = extract_product_name(t)

    # Kirim
    if any(w in t for w in KIRIM_WORDS):
        return ("kirim", name, qty)

    # Chiqim
    if any(w in t for w in CHIQIM_WORDS):
        return ("chiqim", name, qty)

    # Son va nom bor lekin amal noaniq
    if qty and name:
        return ("noaniq", name, qty)

    return ("noaniq", None, None)


def find_product(sklad, name):
    """Skladdan mahsulotni topish (aniq va fuzzy)"""
    if not name:
        return None

    # 1. Aniq moslik
    if name in sklad:
        return name

    # 2. Fuzzy moslik — kamida 3 harf bo'lishi kerak
    if len(name) >= 3:
        for k in sklad:
            if name in k:
                return k
        for k in sklad:
            if k in name:
                return k

    return None


# =============================================
# 📝 ASOSIY HANDLER
# =============================================
def handle_text(message, text):
    """Asosiy buyruqlarni bajarish"""
    sklad = load_sklad()
    action, name, qty = parse_command(text)

    if action == "sklad":
        if not sklad:
            reply = "📦 Sklad bo'sh."
        else:
            lines = ["📦 *Sklad holati:*\n"]
            for n, q in sorted(sklad.items()):
                icon = "🟢" if q > 20 else "🟡" if q > 5 else "🔴"
                lines.append(f"{icon} {n}: *{q} dona*")
            lines.append(f"\n📊 Jami: *{sum(sklad.values())} dona, {len(sklad)} tur*")
            reply = "\n".join(lines)

    elif action == "tozala":
        save_sklad({})
        reply = "🗑️ Sklad tozalandi! Barcha tovarlar o'chirildi."

    elif action == "yordam":
        reply = (
            "🤖 *Sklad Bot — Yordam*\n\n"
            "📥 *Kirim:* kirim 50ta guruch\n"
            "📤 *Sotuv:* sotdim 10ta non\n"
            "📦 *Ko'rish:* sklad\n"
            "🗑️ *Tozalash:* tozala\n"
            "🎤 *Ovozli xabar ham ishlaydi!*"
        )

    elif action == "kirim":
        if not name or not qty:
            reply = "❗ Masalan: *kirim 50ta guruch*"
        else:
            sklad[name] = sklad.get(name, 0) + qty
            save_sklad(sklad)
            reply = f"✅ *{qty} dona {name}* qo'shildi.\nJami: *{sklad[name]} dona*"

    elif action == "chiqim":
        if not name or not qty:
            reply = "❗ Masalan: *sotdim 10ta guruch*"
        else:
            real = find_product(sklad, name)
            if not real:
                reply = f"❌ *{name}* skladda topilmadi."
            elif sklad[real] < qty:
                reply = f"⚠️ *{real}* — faqat *{sklad[real]} dona* bor!"
            else:
                sklad[real] -= qty
                if sklad[real] == 0:
                    del sklad[real]
                save_sklad(sklad)
                left = f"Qoldi: *{sklad[real]} dona*" if real in sklad else "Skladda tugadi."
                reply = f"✅ *{qty} dona {real}* sotildi. {left}"

    else:
        reply = "🤔 Tushunmadim.\n*yordam* deb yozing."

    bot.reply_to(message, reply, parse_mode="Markdown")


# =============================================
# 🤖 TELEGRAM HANDLERLAR
# =============================================
@bot.message_handler(commands=["start"])
def start(m):
    bot.reply_to(m,
        "👋 Salom! Men *Sklad Botiman* 📦\n\n"
        "Tovar kiritish, chiqarish va sklad holatini ko'rish uchun xabar yuboring.\n"
        "🎤 Ovozli xabar ham ishlaydi!\n\n"
        "*yordam* deb yozing.",
        parse_mode="Markdown"
    )


@bot.message_handler(commands=["sklad"])
def cmd_sklad(m):
    handle_text(m, "sklad")


@bot.message_handler(commands=["yordam", "help"])
def cmd_yordam(m):
    handle_text(m, "yordam")


@bot.message_handler(content_types=["text"])
def text_handler(m):
    handle_text(m, m.text)


@bot.message_handler(content_types=["voice"])
def voice_handler(m):
    if not groq_client:
        bot.reply_to(m, "⚠️ Ovozli xabar funksiyasi hozir ishlamaydi.\nIltimos, matn yozing.")
        return

    bot.reply_to(m, "🎤 Ovoz qabul qilindi, tahlil qilinmoqda...")
    path = f"voice_{m.message_id}.ogg"
    try:
        file_info = bot.get_file(m.voice.file_id)
        downloaded = bot.download_file(file_info.file_path)
        with open(path, "wb") as f:
            f.write(downloaded)
        text = voice_to_text(path)
        bot.reply_to(m, f"🗣 Eshitildi: _{text}_", parse_mode="Markdown")
        handle_text(m, text)
    except Exception as e:
        logger.error(f"Ovozli xabar xatosi: {e}", exc_info=True)
        bot.reply_to(m, f"❌ Xatolik: {str(e)}")
    finally:
        # Vaqtinchalik faylni har doim o'chirish
        if os.path.exists(path):
            os.remove(path)


# =============================================
# 🚀 BOTNI ISHGA TUSHIRISH
# =============================================
if __name__ == "__main__":
    # Bot buyruqlarini ro'yxatdan o'tkazish
    try:
        bot.set_my_commands([
            telebot.types.BotCommand("start", "Botni boshlash"),
            telebot.types.BotCommand("sklad", "Sklad holati"),
            telebot.types.BotCommand("yordam", "Yordam"),
        ])
        logger.info("✅ Bot buyruqlari ro'yxatdan o'tkazildi")
    except Exception as e:
        logger.warning(f"Bot buyruqlarini ro'yxatdan o'tkazishda xato: {e}")

    logger.info("✅ Sklad bot ishga tushdi!")
    print("✅ Sklad bot ishga tushdi!")
    bot.infinity_polling()
