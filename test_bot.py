"""
Sklad Bot — Unit Testlar
parse_command va find_product funksiyalarini test qilish
(TeleBot dan mustaqil — faqat logika testlari)
"""
import re

passed = 0
failed = 0

# =============================================
# Funksiyalarni to'g'ridan-to'g'ri kiritamiz
# (main.py dan import qilmasdan, chunki TeleBot kerak)
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
    name = text
    name = re.sub(r"\d+", "", name)
    for word in sorted(STOP_WORDS, key=len, reverse=True):
        name = re.sub(r"\b" + re.escape(word) + r"\b", "", name)
    name = re.sub(r"\s{2,}", " ", name).strip()
    return name


def parse_command(text):
    t = text.strip().lower()

    if any(w in t for w in ["sklad", "nechta", "qancha", "ko'rish", "ombor", "список"]):
        return ("sklad", None, None)

    if re.search(r"\bnima\b.*\bbor\b", t):
        return ("sklad", None, None)

    if any(w in t for w in ["tozala", "clear", "o'chir hammasi"]):
        return ("tozala", None, None)

    if any(w in t for w in ["yordam", "help"]):
        return ("yordam", None, None)

    qty_match = re.search(r"(\d+)", t)
    qty = int(qty_match.group(1)) if qty_match else None

    name = extract_product_name(t)

    if any(w in t for w in KIRIM_WORDS):
        return ("kirim", name, qty)

    if any(w in t for w in CHIQIM_WORDS):
        return ("chiqim", name, qty)

    if qty and name:
        return ("noaniq", name, qty)

    return ("noaniq", None, None)


def find_product(sklad, name):
    if not name:
        return None
    if name in sklad:
        return name
    if len(name) >= 3:
        for k in sklad:
            if name in k:
                return k
        for k in sklad:
            if k in name:
                return k
    return None


# =============================================
# TEST FUNKSIYASI
# =============================================
def test(name, actual, expected):
    global passed, failed
    if actual == expected:
        print(f"  ✅ {name}")
        passed += 1
    else:
        print(f"  ❌ {name}")
        print(f"     Kutilgan: {expected}")
        print(f"     Natija:   {actual}")
        failed += 1


print("=" * 50)
print("🧪 SKLAD BOT TESTLARI")
print("=" * 50)

# --- parse_command testlari ---
print("\n📋 parse_command testlari:")

test("sklad ko'rish", parse_command("sklad")[0], "sklad")
test("nechta bor", parse_command("nechta bor")[0], "sklad")
test("ombor", parse_command("ombor")[0], "sklad")
test("nima bor", parse_command("nima bor")[0], "sklad")
test("nima bor?", parse_command("nima bor?")[0], "sklad")

test("tozala", parse_command("tozala")[0], "tozala")
test("clear", parse_command("clear")[0], "tozala")

test("yordam", parse_command("yordam")[0], "yordam")
test("help", parse_command("help")[0], "yordam")

# Kirim
action, name, qty = parse_command("kirim 50ta guruch")
test("kirim - action", action, "kirim")
test("kirim - qty", qty, 50)
test("kirim - name", name, "guruch")

action, name, qty = parse_command("100 dona un keldi")
test("keldi - action", action, "kirim")
test("keldi - qty", qty, 100)
test("keldi - name contains 'un'", "un" in name, True)

action, name, qty = parse_command("guruch 200ta kirim")
test("kirim teskari tartib - action", action, "kirim")
test("kirim teskari tartib - qty", qty, 200)
test("kirim teskari tartib - name", name, "guruch")

# Chiqim
action, name, qty = parse_command("sotdim 10ta non")
test("chiqim - action", action, "chiqim")
test("chiqim - qty", qty, 10)
test("chiqim - name", name, "non")

action, name, qty = parse_command("20 dona shakar berildi")
test("berildi - action", action, "chiqim")
test("berildi - qty", qty, 20)
test("berildi - name contains 'shakar'", "shakar" in name, True)

# Noaniq
test("noaniq", parse_command("salom")[0], "noaniq")
test("noaniq raqamsiz", parse_command("abc")[0], "noaniq")

# --- extract_product_name testlari ---
print("\n📋 extract_product_name testlari:")

test("guruch ajratish", extract_product_name("kirim 50ta guruch"), "guruch")
test("non ajratish", extract_product_name("sotdim 10ta non"), "non")
test("shakar ajratish", extract_product_name("20 dona shakar berildi"), "shakar")
test("ikki so'zli", extract_product_name("kirim 5ta qora choy"), "qora choy")

# --- find_product testlari ---
print("\n📋 find_product testlari:")

test_sklad = {"guruch": 50, "non": 30, "shakar": 20, "un": 15}

test("aniq moslik", find_product(test_sklad, "guruch"), "guruch")
test("aniq moslik 2", find_product(test_sklad, "non"), "non")
test("fuzzy moslik", find_product(test_sklad, "gur"), "guruch")
test("topilmadi", find_product(test_sklad, "pomidor"), None)
test("qisqa nom (2 harf) - xavfsizlik", find_product(test_sklad, "no"), None)
test("bo'sh nom", find_product(test_sklad, ""), None)
test("None nom", find_product(test_sklad, None), None)

# --- Natija ---
print("\n" + "=" * 50)
total = passed + failed
print(f"📊 Natija: {passed}/{total} test o'tdi")
if failed == 0:
    print("🎉 Barcha testlar muvaffaqiyatli!")
else:
    print(f"⚠️ {failed} ta test muvaffaqiyatsiz")
print("=" * 50)
