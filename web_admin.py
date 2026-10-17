import asyncio
import html
import secrets
from aiohttp import web
from config import WEB_ADMIN_PASSWORD, WEB_ADMIN_USERNAME, ADMIN_IDS
import database as db

STYLE = """
<style>
body{font-family:Arial,sans-serif;background:#101827;color:#e8eef8;margin:0}
header{padding:22px 5%;background:#17243a;border-bottom:1px solid #30415c}
main{max-width:1100px;margin:24px auto;padding:0 16px}
a{color:#7dd3fc} .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}
.card{background:#1b2940;border:1px solid #30415c;border-radius:12px;padding:18px;margin-bottom:14px}
input,textarea,select,button{width:100%;box-sizing:border-box;padding:10px;margin:6px 0;border-radius:7px;border:1px solid #455873;background:#101827;color:#fff}
button{background:#087eaa;border:0;cursor:pointer;font-weight:bold}table{width:100%;border-collapse:collapse}
td,th{text-align:left;padding:8px;border-bottom:1px solid #30415c}small{color:#a8bad1}
</style>
"""

def page(title, body):
    return web.Response(text=f"<!doctype html><html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title>{STYLE}<header><h1>🇺🇿 O‘zbek Kino — Admin</h1><nav><a href='/'>Dashboard</a> · <a href='/movies'>Kinolar</a> · <a href='/categories'>Kategoriyalar</a> · <a href='/logs'>Harakatlar tarixi</a> · <a href='/logout'>Chiqish</a></nav></header><main>{body}</main></html>", content_type="text/html")

def authenticated(request):
    return request.cookies.get("kino_admin_session") == request.app["session_token"]

def require_auth(handler):
    async def wrapped(request):
        if not authenticated(request):
            raise web.HTTPFound("/login")
        return await handler(request)
    return wrapped

def create_web_app(bot, dp):
    app = web.Application()
    app["session_token"] = secrets.token_urlsafe(32)
    app["bot"] = bot

    async def login(request):
        if request.method == "POST":
            data = await request.post()
            if data.get("username") == WEB_ADMIN_USERNAME and secrets.compare_digest(data.get("password",""),WEB_ADMIN_PASSWORD):
                response = web.HTTPFound("/")
                response.set_cookie("kino_admin_session",app["session_token"],httponly=True,samesite="Strict",secure=True)
                raise response
            return page("Login","<div class='card'><h2>Kirish rad etildi</h2><a href='/login'>Qayta urinish</a></div>")
        return page("Login","<div class='card'><h2>Veb-admin kirish</h2><form method='post'><input name='username' placeholder='Login' required><input name='password' type='password' placeholder='Parol' required><button>Kirish</button></form></div>")

    async def logout(request):
        response=web.HTTPFound("/login")
        response.del_cookie("kino_admin_session")
        raise response

    @require_auth
    async def dashboard(request):
        s=await db.stats()
        return page("Dashboard",f"""
        <div class='grid'>
          <div class='card'><small>Foydalanuvchilar</small><h2>{s['users']}</h2><small>7 kunda faol: {s['active_users_7d']}</small></div>
          <div class='card'><small>Kinolar</small><h2>{s['movies']}</h2><small>Ko‘rinadigan: {s['visible_movies']}</small></div>
          <div class='card'><small>Kategoriyalar</small><h2>{s['categories']}</h2></div>
          <div class='card'><small>Kino yuborishlar</small><h2>{s['views']}</h2></div>
        </div>
        <div class='card'><h2>Eng ko‘p tanlangan kinolar</h2><ul>{''.join(f"<li>{html.escape(r['title'])}: {r['views']} ko‘rish</li>" for r in s['top_movies'])}</ul></div>
        """)

    @require_auth
    async def categories_page(request):
        rows=await db.categories()
        body="<div class='card'><h2>Kategoriya yaratish</h2><form method='post' action='/categories/add'><input name='name' placeholder='Kategoriya nomi' required><input name='emoji' placeholder='Emoji' value='🎬'><input name='description' placeholder='Tavsif'><button>Yaratish</button></form></div>"
        body+="<div class='card'><h2>Mavjud kategoriyalar</h2><table><tr><th>ID</th><th>Nomi</th><th>Emoji</th><th>Amal</th></tr>"
        for r in rows:
            body+=f"<tr><td>{r['id']}</td><td>{html.escape(r['name'])}</td><td>{html.escape(r['emoji'])}</td><td><form method='post' action='/categories/delete'><input type='hidden' name='id' value='{r['id']}'><button>O‘chirish</button></form></td></tr>"
        body+="</table><small>Kategoriyani o‘chirish uning kinolarini ham o‘chiradi.</small></div>"
        return page("Kategoriyalar",body)

    @require_auth
    async def category_add(request):
        data=await request.post()
        try:
            await db.category_create(data.get("name",""),data.get("emoji","🎬"),data.get("description",""))
            await db.audit(0,"web_category_create",data.get("name",""))
        except Exception:
            pass
        raise web.HTTPFound("/categories")

    @require_auth
    async def category_delete(request):
        data=await request.post()
        try:
            cid=int(data.get("id","0"))
            await db.category_delete(cid)
            await db.audit(0,"web_category_delete",str(cid))
        except Exception:
            pass
        raise web.HTTPFound("/categories")

    @require_auth
    async def movies_page(request):
        rows=await db.movies_list(limit=100,include_hidden=True)
        cats=await db.categories()
        body="<div class='card'><h2>Kinolar</h2><form method='get'><input name='q' placeholder='Nom, janr yoki yil bo‘yicha qidirish'><button>Qidirish</button></form></div>"
        q=request.query.get("q","").strip()
        if q:
            rows=await db.movie_search(q,limit=100)
        body+="<div class='card'><table><tr><th>ID</th><th>Nomi</th><th>Kategoriya</th><th>Yil</th><th>Ko‘rish</th><th>Holat</th></tr>"
        for r in rows:
            body+=f"<tr><td>{r['id']}</td><td>{html.escape(r['title'])}</td><td>{html.escape(r['category_name'])}</td><td>{r['year'] or ''}</td><td>{r['views']}</td><td>{'Ko‘rinadi' if r['is_visible'] else 'Yashirilgan'}</td></tr>"
        body+="</table></div><div class='card'><h2>Yangi kino metama'lumotini kiritish</h2><small>Video Telegram botdagi /admin orqali yuklanadi. Bu yerda mavjud kino metama'lumotlarini boshqarish ko‘rsatiladi.</small></div>"
        return page("Kinolar",body)

    @require_auth
    async def logs_page(request):
        rows=await db.audit_recent(100)
        body="<div class='card'><h2>Oxirgi amallar</h2><table><tr><th>Vaqt</th><th>Admin ID</th><th>Amal</th><th>Tafsilot</th></tr>"
        for r in rows:
            body+=f"<tr><td>{r['created_at']}</td><td>{r['actor_id']}</td><td>{html.escape(r['action'])}</td><td>{html.escape(r['details'] or '')}</td></tr>"
        body+="</table></div>"
        return page("Loglar",body)

    app.router.add_get("/login",login)
    app.router.add_post("/login",login)
    app.router.add_get("/logout",logout)
    app.router.add_get("/",dashboard)
    app.router.add_get("/categories",categories_page)
    app.router.add_post("/categories/add",category_add)
    app.router.add_post("/categories/delete",category_delete)
    app.router.add_get("/movies",movies_page)
    app.router.add_get("/logs",logs_page)
    return app
