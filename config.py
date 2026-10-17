import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
WEB_ADMIN_ENABLED = os.getenv("WEB_ADMIN_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
WEB_ADMIN_PASSWORD = os.getenv("WEB_ADMIN_PASSWORD", "").strip()
WEB_ADMIN_USERNAME = os.getenv("WEB_ADMIN_USERNAME", "admin").strip()

ADMIN_IDS = {
    int(v.strip()) for v in os.getenv("ADMIN_IDS", "").split(",")
    if v.strip().isdigit()
}
# Kanal username'lari: @kanal1,@kanal2
FORCE_SUB_CHANNELS = [
    v.strip() for v in os.getenv("FORCE_SUB_CHANNELS", "").split(",") if v.strip()
]
# Qo'shimcha adminlar va ruxsatlar DB'da boshqariladi. ADMIN_IDS — superadminlar.
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN kiritilmagan.")
if not ADMIN_IDS:
    raise RuntimeError("ADMIN_IDS ga kamida bitta Telegram user ID kiriting.")
if WEB_ADMIN_ENABLED and WEBHOOK_URL and not WEB_ADMIN_PASSWORD:
    raise RuntimeError("Veb-admin yoqilgan bo‘lsa, WEB_ADMIN_PASSWORD ni kuchli parolga sozlang.")
