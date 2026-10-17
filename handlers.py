import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_IDS, CHANNEL_ID, FORCE_SUB_CHANNELS
import database as db
from keyboards import category_keyboard, movie_keyboard, admin_home_keyboard, category_admin_keyboard

router = Router()
PERMISSIONS = {"movies": "movies_manage", "broadcast": "broadcast", "users": "users_manage", "stats": "stats"}

class AddMovie(StatesGroup):
    category=State(); video=State(); title=State(); year=State(); genre=State(); description=State()
class AddCategory(StatesGroup):
    name=State(); emoji=State(); description=State()
class EditMovie(StatesGroup):
    movie_id=State(); title=State(); year=State(); genre=State(); description=State()
class Broadcast(StatesGroup):
    text=State()
class AdminAdd(StatesGroup):
    user_id=State(); label=State(); permissions=State()
class UserBlock(StatesGroup):
    user_id=State()

def is_superadmin(user_id):
    return user_id in ADMIN_IDS

async def has_permission(user_id, permission):
    if is_superadmin(user_id):
        return True
    return permission in await db.admin_permissions(user_id)

async def is_blocked_user(user_id):
    p = await db.get_pool()
    async with p.acquire() as c:
        return bool(await c.fetchval("SELECT is_blocked FROM users WHERE user_id=$1", user_id))

async def subscription_missing(bot, user_id):
    missing=[]
    for channel in FORCE_SUB_CHANNELS:
        try:
            member=await bot.get_chat_member(channel, user_id)
            if member.status in ("left","kicked"):
                missing.append(channel)
        except Exception:
            missing.append(channel)
    return missing

async def prompt_sub(message, missing):
    rows=[]
    for channel in missing:
        url=channel if channel.startswith("https://") else "https://t.me/"+channel.lstrip("@")
        rows.append([InlineKeyboardButton(text=f"📢 Obuna: {channel}", url=url)])
    rows.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="sub:check")])
    await message.answer("Botdan foydalanish uchun quyidagi kanal(lar)ga obuna bo‘ling:",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.message(CommandStart())
async def start(message: Message, bot: Bot):
    await db.upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    if await is_blocked_user(message.from_user.id):
        await message.answer("⛔ Botdan foydalanishingiz cheklangan.")
        return
    missing=await subscription_missing(bot,message.from_user.id)
    if missing:
        await prompt_sub(message,missing); return
    await message.answer(
        "🇺🇿 <b>O‘zbek kinolari</b>\n\nKategoriyani tanlang yoki kino nomi, janri yoxud yilini yozing.",
        reply_markup=category_keyboard(await db.categories()), parse_mode="HTML"
    )

@router.callback_query(F.data=="sub:check")
async def sub_check(call: CallbackQuery, bot: Bot):
    missing=await subscription_missing(bot,call.from_user.id)
    if missing:
        await call.answer("Hali barcha kanallarga obuna bo‘lmagansiz.",show_alert=True); return
    await call.message.edit_text("🇺🇿 O‘zbek kinolari\nKategoriyani tanlang yoki kino qidiring.",
                                 reply_markup=category_keyboard(await db.categories()))
    await call.answer()

@router.message(Command("admin"))
async def admin(message: Message):
    if await has_permission(message.from_user.id,"movies_manage") or await has_permission(message.from_user.id,"stats"):
        await message.answer("👑 <b>ADMIN BOSHQARUV MARKAZI</b>",reply_markup=admin_home_keyboard(),parse_mode="HTML")
    else:
        await message.answer("Sizda admin paneliga kirish huquqi yo‘q.")

@router.callback_query(F.data.startswith("cat:"))
async def show_category(call: CallbackQuery, bot: Bot):
    if await subscription_missing(bot,call.from_user.id):
        await call.answer("Avval majburiy kanallarga obuna bo‘ling.",show_alert=True); return
    cat_id=int(call.data.split(":")[1])
    rows=await db.movies_list(cat_id,limit=30)
    await call.message.answer("Bu kategoriyada hozircha kino yo‘q." if not rows else "🎬 Kinoni tanlang:",
                              reply_markup=None if not rows else movie_keyboard(rows))
    await call.answer()

@router.message(StateFilter(None), F.text & ~F.text.startswith("/"))
async def search(message: Message, bot: Bot):
    if await is_blocked_user(message.from_user.id):
        await message.answer("⛔ Botdan foydalanishingiz cheklangan.")
        return
    if await subscription_missing(bot,message.from_user.id):
        await message.answer("Avval majburiy kanallarga obuna bo‘ling."); return
    query=message.text.strip()
    if len(query)<2:
        await message.answer("Qidirish uchun kamida 2 ta belgi kiriting."); return
    rows=await db.movie_search(query)
    if not rows:
        await message.answer("😕 Kino topilmadi."); return
    await message.answer("🔎 Topilgan kinolar:",reply_markup=movie_keyboard(rows))

@router.callback_query(F.data.startswith("movie:"))
async def send_movie(call: CallbackQuery, bot: Bot):
    if await is_blocked_user(call.from_user.id):
        await call.answer("Botdan foydalanishingiz cheklangan.", show_alert=True)
        return
    movie=await db.movie_get(int(call.data.split(":")[1]))
    if not movie or not movie["is_visible"]:
        await call.answer("Kino topilmadi.",show_alert=True); return
    await db.movie_view(movie["id"])
    caption=f"🎬 <b>{movie['title']}</b>"
    if movie["year"]: caption+=f"\n📅 Yil: {movie['year']}"
    if movie["genre"]: caption+=f"\n🎭 Janr: {movie['genre']}"
    if movie["description"]: caption+=f"\n\n{movie['description']}"
    try:
        if movie["channel_id"] and movie["channel_message_id"]:
            await bot.copy_message(call.from_user.id,movie["channel_id"],movie["channel_message_id"],
                                   caption=caption,parse_mode="HTML")
        elif movie["file_id"]:
            await bot.send_video(call.from_user.id,movie["file_id"],caption=caption,parse_mode="HTML")
        else:
            await call.message.answer(caption+"\n\n⚠️ Video manbasi topilmadi.",parse_mode="HTML")
    except Exception:
        await call.message.answer(caption+"\n\n⚠️ Videoni yuborib bo‘lmadi. Kanal ruxsatlarini tekshiring.",parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data=="adm:stats")
async def stats(call: CallbackQuery):
    if not await has_permission(call.from_user.id,"stats"):
        await call.answer("Ruxsat yo‘q.",show_alert=True); return
    s=await db.stats()
    top="\n".join(f"• {r['title']} — {r['views']} marta" for r in s["top_movies"]) or "Hali ko‘rish yo‘q"
    await call.message.answer(
        f"📊 <b>STATISTIKA</b>\n👥 Jami foydalanuvchi: {s['users']}\n"
        f"🟢 So‘nggi 7 kun faol: {s['active_users_7d']}\n🎬 Jami kino: {s['movies']}\n"
        f"👁 Kino yuborilgan: {s['views']}\n📂 Kategoriyalar: {s['categories']}\n\n🔥 TOP KINOLAR\n{top}",
        parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data=="adm:categories")
async def categories_admin(call: CallbackQuery):
    if not await has_permission(call.from_user.id,"movies_manage"):
        await call.answer("Ruxsat yo‘q.",show_alert=True); return
    await call.message.answer("📂 Kategoriyalar. O‘chirish kategoriyadagi kinolarni ham o‘chiradi.",
                              reply_markup=category_admin_keyboard(await db.categories()))
    await call.answer()

@router.callback_query(F.data=="adm:catadd")
async def category_add_start(call: CallbackQuery,state: FSMContext):
    if not await has_permission(call.from_user.id,"movies_manage"): return
    await state.set_state(AddCategory.name); await call.message.answer("Yangi kategoriya nomini yuboring:"); await call.answer()

@router.message(AddCategory.name)
async def category_add_name(message: Message,state: FSMContext):
    if not await has_permission(message.from_user.id,"movies_manage"): return
    await state.update_data(name=message.text.strip()); await state.set_state(AddCategory.emoji)
    await message.answer("Emoji yuboring (masalan 🎞️):")

@router.message(AddCategory.emoji)
async def category_add_emoji(message: Message,state: FSMContext):
    await state.update_data(emoji=message.text.strip()[:12] or "🎬")
    await state.set_state(AddCategory.description); await message.answer("Kategoriya tavsifi (bo‘lmasa -):")

@router.message(AddCategory.description)
async def category_add_description(message: Message,state: FSMContext):
    d=await state.get_data()
    try:
        await db.category_create(d["name"],d["emoji"],"" if message.text.strip()=="-" else message.text.strip())
        await db.audit(message.from_user.id,"category_create",d["name"])
        await message.answer("✅ Kategoriya yaratildi.")
    except Exception:
        await message.answer("❌ Kategoriya yaratilmadi. Nom takrorlangan bo‘lishi mumkin.")
    await state.clear()

@router.callback_query(F.data.startswith("adm:catdel:"))
async def category_delete(call: CallbackQuery):
    if not await has_permission(call.from_user.id,"movies_manage"): return
    cat_id=int(call.data.split(":")[2]); cat=await db.category_by_id(cat_id)
    if not cat: await call.answer("Topilmadi.",show_alert=True); return
    await db.category_delete(cat_id); await db.audit(call.from_user.id,"category_delete",cat["name"])
    await call.message.answer(f"🗑 {cat['name']} va uning kinolari bazadan o‘chirildi.")
    await call.answer()

@router.callback_query(F.data=="adm:add_movie")
async def add_movie_start(call: CallbackQuery,state: FSMContext):
    if not await has_permission(call.from_user.id,"movies_manage"): return
    await state.set_state(AddMovie.category)
    await call.message.answer("Kino qo‘shiladigan kategoriyani tanlang:",reply_markup=category_keyboard(await db.categories(),"pickcat"))
    await call.answer()

@router.callback_query(AddMovie.category,F.data.startswith("pickcat:"))
async def add_movie_cat(call: CallbackQuery,state: FSMContext):
    await state.update_data(category_id=int(call.data.split(":")[1]))
    await state.set_state(AddMovie.video); await call.message.answer("Kino videosini yuboring:"); await call.answer()

@router.message(AddMovie.video,F.video)
async def add_movie_video(message: Message,state: FSMContext,bot: Bot):
    file_id=message.video.file_id; channel_id=CHANNEL_ID or None; channel_msg=None
    if channel_id:
        try:
            sent=await bot.copy_message(channel_id,message.chat.id,message.message_id)
            channel_msg=sent.message_id
        except Exception:
            await message.answer("⚠️ Kanalga joylab bo‘lmadi. Bot kanal admini va post yuborish huquqiga ega ekanini tekshiring. Video file_id orqali saqlanadi.")
            channel_id=None
    await state.update_data(file_id=file_id,channel_id=channel_id,channel_message_id=channel_msg)
    await state.set_state(AddMovie.title); await message.answer("Kino nomini yozing:")

@router.message(AddMovie.video)
async def add_movie_need_video(message: Message):
    await message.answer("Iltimos, video yuboring.")

@router.message(AddMovie.title)
async def add_movie_title(message: Message,state: FSMContext):
    await state.update_data(title=message.text.strip()); await state.set_state(AddMovie.year)
    await message.answer("Chiqqan yilini yozing (noma'lum bo‘lsa 0):")

@router.message(AddMovie.year)
async def add_movie_year(message: Message,state: FSMContext):
    try:
        y=int(message.text.strip())
        if y and not 1888<=y<=2100: raise ValueError()
    except ValueError:
        await message.answer("Yilni raqamda kiriting, masalan 1991 yoki 0."); return
    await state.update_data(year=y or None); await state.set_state(AddMovie.genre)
    await message.answer("Janrini yozing (masalan komediya, drama):")

@router.message(AddMovie.genre)
async def add_movie_genre(message: Message,state: FSMContext):
    await state.update_data(genre=message.text.strip()); await state.set_state(AddMovie.description)
    await message.answer("Tavsif yozing yoki - yuboring:")

@router.message(AddMovie.description)
async def add_movie_description(message: Message,state: FSMContext):
    d=await state.get_data()
    try:
        await db.movie_create(d["category_id"],d["title"],d["year"],d["genre"],
            "" if message.text.strip()=="-" else message.text.strip(),d["file_id"],
            d.get("channel_id"),d.get("channel_message_id"),message.from_user.id)
        await db.audit(message.from_user.id,"movie_create",d["title"])
        await message.answer(f"✅ <b>{d['title']}</b> qo‘shildi.",parse_mode="HTML")
    except Exception:
        await message.answer("❌ Kino saqlanmadi. Baza yoki kategoriya holatini tekshiring.")
    await state.clear()

async def ask_movie_selection(message, prefix):
    rows=await db.movies_list(limit=30,include_hidden=True)
    if not rows: await message.answer("Kinolar yo‘q.")
    else: await message.answer("Kinoni tanlang:",reply_markup=movie_keyboard(rows,prefix))

@router.callback_query(F.data=="adm:delete_movie")
async def delete_movie_start(call: CallbackQuery):
    if not await has_permission(call.from_user.id,"movies_manage"): return
    await ask_movie_selection(call.message,"delmovie"); await call.answer()

@router.callback_query(F.data.startswith("delmovie:"))
async def delete_movie(call: CallbackQuery):
    if not await has_permission(call.from_user.id,"movies_manage"): return
    movie=await db.movie_get(int(call.data.split(":")[1]))
    if movie:
        await db.movie_delete(movie["id"]); await db.audit(call.from_user.id,"movie_delete",movie["title"])
        await call.message.answer(f"🗑 {movie['title']} bazadan o‘chirildi. Kanal postining o‘zi qoladi.")
    await call.answer()

@router.callback_query(F.data=="adm:visibility")
async def visibility_start(call: CallbackQuery):
    if not await has_permission(call.from_user.id,"movies_manage"): return
    rows=await db.movies_list(limit=30,include_hidden=True)
    await call.message.answer("Ko‘rinishini almashtirmoqchi bo‘lgan kinoni tanlang:",
                              reply_markup=movie_keyboard(rows,"vismovie"))
    await call.answer()

@router.callback_query(F.data.startswith("vismovie:"))
async def visibility_toggle(call: CallbackQuery):
    if not await has_permission(call.from_user.id,"movies_manage"): return
    m=await db.movie_get(int(call.data.split(":")[1]))
    if m:
        await db.movie_update(m["id"],m["title"],m["year"],m["genre"],m["description"],
                              visible=not m["is_visible"])
        await db.audit(call.from_user.id,"movie_visibility",f"{m['title']} -> {not m['is_visible']}")
        await call.message.answer(f"Ko‘rinishi yangilandi: {m['title']} — {'ko‘rinadi' if not m['is_visible'] else 'yashirildi'}.")
    await call.answer()

@router.callback_query(F.data=="adm:edit_movie")
async def edit_movie_start(call: CallbackQuery,state: FSMContext):
    if not await has_permission(call.from_user.id,"movies_manage"): return
    rows=await db.movies_list(limit=30,include_hidden=True)
    await call.message.answer("Tahrirlash uchun kinoni tanlang:",reply_markup=movie_keyboard(rows,"editmovie"))
    await call.answer()

@router.callback_query(F.data.startswith("editmovie:"))
async def edit_movie_pick(call: CallbackQuery,state: FSMContext):
    if not await has_permission(call.from_user.id,"movies_manage"): return
    movie=await db.movie_get(int(call.data.split(":")[1]))
    if not movie: await call.answer("Topilmadi.",show_alert=True); return
    await state.update_data(movie_id=movie["id"],title=movie["title"],year=movie["year"],
                            genre=movie["genre"],description=movie["description"])
    await state.set_state(EditMovie.title)
    await call.message.answer(f"Joriy nom: {movie['title']}\nYangi nomni yozing (o‘zgarmasa -):")
    await call.answer()

@router.message(EditMovie.title)
async def edit_title(message: Message,state: FSMContext):
    d=await state.get_data()
    await state.update_data(title=d["title"] if message.text.strip()=="-" else message.text.strip())
    await state.set_state(EditMovie.year); await message.answer("Yangi yil (o‘zgarmasa -, noma'lum 0):")

@router.message(EditMovie.year)
async def edit_year(message: Message,state: FSMContext):
    d=await state.get_data(); t=message.text.strip()
    if t=="-": y=d["year"]
    else:
        try:
            y=int(t)
            if y and not 1888<=y<=2100: raise ValueError()
            y=y or None
        except ValueError:
            await message.answer("Yilni 1888–2100 oralig‘ida yoki 0, - shaklida kiriting."); return
    await state.update_data(year=y); await state.set_state(EditMovie.genre)
    await message.answer("Yangi janr (o‘zgarmasa -):")

@router.message(EditMovie.genre)
async def edit_genre(message: Message,state: FSMContext):
    d=await state.get_data()
    await state.update_data(genre=d["genre"] if message.text.strip()=="-" else message.text.strip())
    await state.set_state(EditMovie.description); await message.answer("Yangi tavsif (o‘zgarmasa -):")

@router.message(EditMovie.description)
async def edit_description(message: Message,state: FSMContext):
    d=await state.get_data(); desc=d["description"] if message.text.strip()=="-" else ("" if message.text.strip()=="0" else message.text.strip())
    await db.movie_update(d["movie_id"],d["title"],d["year"],d["genre"],desc)
    await db.audit(message.from_user.id,"movie_edit",d["title"])
    await message.answer("✅ Kino ma'lumotlari tahrirlandi."); await state.clear()

@router.callback_query(F.data=="adm:logs")
async def logs(call: CallbackQuery):
    if not await has_permission(call.from_user.id,"stats"): return
    rows=await db.audit_recent(15)
    lines=[f"#{r['id']} | {r['actor_id']} | {r['action']} | {r['details']}" for r in rows]
    await call.message.answer("📜 <b>So‘nggi amallar</b>\n\n"+"\n".join(lines) if lines else "Hozircha log yo‘q.",parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data=="adm:broadcast")
async def broadcast_start(call: CallbackQuery,state: FSMContext):
    if not await has_permission(call.from_user.id,"broadcast"):
        await call.answer("Ommaviy xabar yuborish huquqi yo‘q.",show_alert=True); return
    await state.set_state(Broadcast.text)
    await call.message.answer("Yuboriladigan matnni kiriting. Bu versiyada matnli xabar qo‘llanadi:")
    await call.answer()

@router.message(Broadcast.text)
async def broadcast_send(message: Message,state: FSMContext,bot: Bot):
    if not await has_permission(message.from_user.id,"broadcast"): return
    users=await db.user_ids(); sent=0; failed=0
    status=await message.answer(f"📢 Yuborish boshlandi: {len(users)} foydalanuvchi.")
    for row in users:
        try:
            await bot.send_message(row["user_id"],message.text)
            sent+=1
        except Exception:
            failed+=1
        await asyncio.sleep(0.05)
    await db.audit(message.from_user.id,"broadcast",f"sent={sent}; failed={failed}")
    await status.edit_text(f"✅ Yakunlandi.\n📨 Yuborildi: {sent}\n⚠️ Yuborilmadi: {failed}")
    await state.clear()

@router.callback_query(F.data=="adm:admins")
async def admins_start(call: CallbackQuery,state: FSMContext):
    if not is_superadmin(call.from_user.id):
        await call.answer("Faqat superadmin.",show_alert=True); return
    await state.set_state(AdminAdd.user_id)
    await call.message.answer("Qo‘shiladigan adminning Telegram ID raqamini yuboring:")
    await call.answer()

@router.message(AdminAdd.user_id)
async def admin_user_id(message: Message,state: FSMContext):
    if not is_superadmin(message.from_user.id): return
    try: uid=int(message.text.strip())
    except ValueError:
        await message.answer("ID faqat raqam bo‘lishi kerak."); return
    await state.update_data(user_id=uid); await state.set_state(AdminAdd.label)
    await message.answer("Admin uchun izoh/ism kiriting:")

@router.message(AdminAdd.label)
async def admin_label(message: Message,state: FSMContext):
    await state.update_data(label=message.text.strip()); await state.set_state(AdminAdd.permissions)
    await message.answer("Ruxsatlarni vergul bilan yozing: movies_manage,broadcast,users_manage,stats")

@router.message(AdminAdd.permissions)
async def admin_permissions_save(message: Message,state: FSMContext):
    if not is_superadmin(message.from_user.id): return
    allowed={"movies_manage","broadcast","users_manage","stats"}
    perms=[p.strip() for p in message.text.split(",") if p.strip() in allowed]
    d=await state.get_data()
    await db.admin_set(d["user_id"],d["label"],perms,message.from_user.id)
    await db.audit(message.from_user.id,"admin_set",f"{d['user_id']}:{perms}")
    await message.answer(f"✅ Admin saqlandi. Ruxsatlar: {', '.join(perms) or 'hech biri'}")
    await state.clear()

@router.callback_query(F.data=="adm:block_user")
async def block_start(call: CallbackQuery,state: FSMContext):
    if not await has_permission(call.from_user.id,"users_manage"):
        await call.answer("Foydalanuvchilarni boshqarish huquqi yo‘q.",show_alert=True); return
    await state.set_state(UserBlock.user_id)
    await call.message.answer("Bloklash uchun foydalanuvchi ID sini yuboring:")
    await call.answer()

@router.message(UserBlock.user_id)
async def block_user(message: Message,state: FSMContext):
    if not await has_permission(message.from_user.id,"users_manage"): return
    try: uid=int(message.text.strip())
    except ValueError:
        await message.answer("ID raqam bo‘lishi kerak."); return
    await db.user_block(uid,True); await db.audit(message.from_user.id,"user_block",str(uid))
    await message.answer(f"⛔ {uid} bloklandi (foydalanuvchi jadvalda bo‘lsa).")
    await state.clear()
