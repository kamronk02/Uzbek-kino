O‘ZBEK KINO PLATFORMASI — KENGAYTIRILGAN BOSHLANG‘ICH VERSIYA
ZIP EMAS: barcha fayllar alohida.

FAYLLAR
- main.py: bot va webhook serverini ishga tushiradi.
- config.py: environment sozlamalari.
- database.py: PostgreSQL sxemasi va ma'lumotlar funksiyalari.
- handlers.py: Telegram bot, kategoriyalar, kino qidirish, admin amallari.
- keyboards.py: Telegram menyulari.
- web_admin.py: veb-admin dashboard, kategoriyalar, kino ro‘yxati, audit log.
- requirements.txt: kutubxonalar.
- render.yaml: Render Blueprint.
- README.txt: ushbu yo‘riqnoma.

ENVIRONMENT VARIABLES
BOT_TOKEN                 BotFather tokeni
ADMIN_IDS                 Superadmin Telegram ID'lari, vergul bilan
DATABASE_URL              PostgreSQL ulanish manzili
CHANNEL_ID                Kino kanali, masalan @uzbekkinolar
FORCE_SUB_CHANNELS        Majburiy kanallar, vergul bilan: @kanal1,@kanal2
WEBHOOK_URL               Render xizmat manzili, masalan https://my-bot.onrender.com
WEB_ADMIN_ENABLED         true/false
WEB_ADMIN_USERNAME        Veb-admin login (standart admin)
WEB_ADMIN_PASSWORD        Kuchli, noyob veb-admin paroli

DEPLOY
1. BotFather orqali bot yarating.
2. Telegram kanal oching, botni admin qiling va post yuborish huquqini bering.
3. Render'da Blueprint yoki Web Service + PostgreSQL yarating.
4. Environment variables qiymatlarini kiriting.
5. WEBHOOK_URL ni Render web-service manziliga yozing. Kod /webhook yo‘lini o‘zi qo‘shadi.
6. Deploy loglarini tekshiring.
7. Telegram'da /start va /admin buyruqlarini sinang.
8. Veb-admin uchun https://<xizmat>.onrender.com/login manziliga kiring.

BOT ADMIN
/admin — Telegram admin paneli.
Superadminlar ADMIN_IDS orqali belgilanadi.
Qo‘shimcha admin qo‘shish: Adminlar bo‘limi orqali user ID va ruxsatlar yoziladi.
Ruxsat nomlari: movies_manage,broadcast,users_manage,stats

KINO QO‘SHISH
Admin paneli → Kino qo‘shish → kategoriya → video → nom → yil → janr → tavsif.
Kino kanalda saqlanishi uchun bot kanal admini bo‘lishi va CHANNEL_ID to‘g‘ri kiritilishi kerak.

MUHIM CHEKLOVLAR
- Bu kengaytirilgan boshlang‘ich versiya, lekin ishlab chiqarish uchun to‘liq audit va xavfsizlik tekshiruvi talab qilinadi.
- Veb-admin hozircha dashboard, kategoriya boshqaruvi, kino ro‘yxati/qidiruvi va loglarni ko‘rsatadi; videoni yuklash/tahrirlash Telegram admin panelida bajariladi.
- Ommaviy xabarlar matn ko‘rinishida yuboriladi va katta auditoriyada Telegram rate limitlariga mos ravishda yanada puxta navbat mexanizmi kerak bo‘lishi mumkin.
- Telegram kanal postini bot bazasidan kino o‘chirilganda avtomatik o‘chirmaydi.
- Kategoriyani o‘chirish unga biriktirilgan kinolarni ham o‘chiradi.
- Majburiy obunani tekshirish uchun bot tegishli kanallarda admin bo‘lishi kerak.
- Foydalanuvchi bloklash funksiyasi bot ichida kirishni cheklash uchun keyingi xavfsizlik bosqichida qo‘shimcha tekshiruv talab qiladi.
- Render tariflari va bepul PostgreSQL cheklovlari o‘zgarishi mumkin. Doimiy ishlash va zaxira nusxalar uchun pulli xizmat talab qilinishi mumkin.
- Faqat tarqatish huquqiga ega bo‘lgan videolarni joylang.
