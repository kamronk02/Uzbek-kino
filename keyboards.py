from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def category_keyboard(rows, prefix="cat"):
    b = InlineKeyboardBuilder()
    for r in rows:
        b.button(text=f"{r['emoji']} {r['name']}", callback_data=f"{prefix}:{r['id']}")
    b.adjust(1)
    return b.as_markup()

def movie_keyboard(rows, prefix="movie"):
    b = InlineKeyboardBuilder()
    for r in rows:
        year = f" ({r['year']})" if r["year"] else ""
        b.button(text=f"🎬 {r['title']}{year}", callback_data=f"{prefix}:{r['id']}")
    b.adjust(1)
    return b.as_markup()

def admin_home_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Kino qo‘shish", callback_data="adm:add_movie"),
         InlineKeyboardButton(text="📝 Kino tahrirlash", callback_data="adm:edit_movie")],
        [InlineKeyboardButton(text="🗑 Kino o‘chirish", callback_data="adm:delete_movie"),
         InlineKeyboardButton(text="📂 Kategoriyalar", callback_data="adm:categories")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="adm:stats"),
         InlineKeyboardButton(text="📜 Harakatlar tarixi", callback_data="adm:logs")],
        [InlineKeyboardButton(text="📢 Ommaviy xabar", callback_data="adm:broadcast"),
         InlineKeyboardButton(text="👥 Adminlar", callback_data="adm:admins")],
        [InlineKeyboardButton(text="👤 Foydalanuvchini bloklash", callback_data="adm:block_user"),
         InlineKeyboardButton(text="♻️ Kino ko‘rinishini almashtirish", callback_data="adm:visibility")]
    ])

def category_admin_keyboard(rows):
    b = InlineKeyboardBuilder()
    for r in rows:
        b.button(text=f"🗑 {r['name']}", callback_data=f"adm:catdel:{r['id']}")
    b.button(text="➕ Kategoriya yaratish", callback_data="adm:catadd")
    b.adjust(1)
    return b.as_markup()

def permissions_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Kino boshqarish", callback_data="perm:movies")],
        [InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="perm:broadcast")],
        [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="perm:users")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="perm:stats")],
    ])
