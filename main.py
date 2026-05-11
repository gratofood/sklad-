import os
import json
import re
import telebot
from groq import Groq

TELEGRAM_TOKEN = 
GROQ_API_KEY = 

SKLAD_FILE = "sklad.json"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)


def load_sklad():
    if os.path.exists(SKLAD_FILE):
        with open(SKLAD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_sklad(sklad):
    with open(SKLAD_FILE, "w", encoding="utf-8") as f:
        json.dump(sklad, f, ensure_ascii=False, indent=2)


def voice_to_text(file_path):
    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=audio_file,
            language="uz"
        )
    return transcript.text


def parse_command(text):
    t = text.strip().lower()

    if any(w in t for w in ["sklad", "nechta", "qancha", "ko'rish", "bor", "ombor", "список"]):
        return ("sklad", None, None)

    if any(w in t for w in ["tozala", "clear", "nol", "o'chir hammasi"]):
        return ("tozala", None, None)

    if any(w in t for w in ["yordam", "help"]):
        return ("yordam", None, None)

    qty_match = re.search(r"(\d+)", t)
    qty = int(qty_match.group(1)) if qty_match else None

    stop_words = r"kirim|kiritildi|keldi|qo.shildi|qo.sh|kirgiz|sotdim|sotildi|chiqim|chiqdi|berildi|olindi|yuborildi|ta|dona|kg|litr"
    name = re.sub(stop_words, "", t)
    name = re.sub(r"\d+", "", name).strip()
    name = re.sub(r"\s{2,}", " ", name).strip()

    if any(w in t for w in ["kirim", "kiritildi", "keldi", "qo'shildi", "qoshildi", "kirgiz"]):
        return ("kirim", name, qty)

    if any(w in t for w in ["sotdim", "sotildi", "chiqim", "chiqdi", "berildi", "olindi"]):
        return ("chiqim", name, qty)

    if qty and name:
        return ("unknown", name, qty)

    return ("unknown", None, None)


def handle_text(message, text):
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
            real = name if name in sklad else next((k for k in sklad if name in k or k in name), None)
            if not real:
                reply = f"❌ *{name}* skladdda topilmadi."
            elif sklad[real] < qty:
                reply = f"⚠️ Faqat *{sklad[real]} dona* bor!"
            else:
                sklad[real] -= qty
                if sklad[real] == 0:
                    del sklad[real]
                save_sklad(sklad)
                left = f"Qoldi: *{sklad[real]} dona*" if real in sklad else "Sklad bo'shadi."
                reply = f"✅ *{qty} dona {real}* sotildi. {left}"
    else:
        reply = "🤔 Tushunmadim.\n*yordam* deb yozing."

    bot.reply_to(message, reply, parse_mode="Markdown")


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
    bot.reply_to(m, "🎤 Ovoz qabul qilindi, tahlil qilinmoqda...")
    try:
        file_info = bot.get_file(m.voice.file_id)
        downloaded = bot.download_file(file_info.file_path)
        path = f"voice_{m.message_id}.ogg"
        with open(path, "wb") as f:
            f.write(downloaded)
        text = voice_to_text(path)
        os.remove(path)
        bot.reply_to(m, f"🗣 Eshitildi: _{text}_", parse_mode="Markdown")
        handle_text(m, text)
    except Exception as e:
        bot.reply_to(m, f"❌ Xatolik: {str(e)}")


if __name__ == "__main__":
    print("✅ Sklad bot ishga tushdi!")
    bot.infinity_polling()
