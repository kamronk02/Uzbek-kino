import asyncpg
from config import DATABASE_URL

_pool = None

DEFAULT_CATEGORIES = [
    ("Yangi o‘zbek kinolari", "🆕"),
    ("Retro kinolar", "🎞️"),
    ("Komediya kinolar", "😂"),
    ("Drama kinolar", "🎭"),
]

async def init_db():
    global _pool
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL kiritilmagan. Render PostgreSQL URL'ini kiriting.")
    url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    _pool = await asyncpg.create_pool(url, min_size=1, max_size=8, command_timeout=30)
    async with _pool.acquire() as c:
        await c.execute("""
        CREATE TABLE IF NOT EXISTS users(
          user_id BIGINT PRIMARY KEY, username TEXT, first_name TEXT,
          joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          is_blocked BOOLEAN NOT NULL DEFAULT FALSE
        );
        CREATE TABLE IF NOT EXISTS categories(
          id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE, emoji TEXT NOT NULL DEFAULT '🎬',
          description TEXT DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS movies(
          id SERIAL PRIMARY KEY, category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
          title TEXT NOT NULL, year INTEGER, genre TEXT DEFAULT '', description TEXT DEFAULT '',
          file_id TEXT, channel_id TEXT, channel_message_id BIGINT,
          added_by BIGINT, added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), views BIGINT NOT NULL DEFAULT 0,
          is_visible BOOLEAN NOT NULL DEFAULT TRUE
        );
        CREATE TABLE IF NOT EXISTS admins(
          user_id BIGINT PRIMARY KEY, label TEXT DEFAULT '', permissions TEXT[] NOT NULL DEFAULT ARRAY['movies_read'],
          added_by BIGINT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS audit_logs(
          id BIGSERIAL PRIMARY KEY, actor_id BIGINT, action TEXT NOT NULL,
          details TEXT DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS settings(
          key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS broadcasts(
          id BIGSERIAL PRIMARY KEY, actor_id BIGINT, message_text TEXT,
          status TEXT DEFAULT 'queued', sent_count INTEGER DEFAULT 0, failed_count INTEGER DEFAULT 0,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), finished_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS movies_category_idx ON movies(category_id);
        CREATE INDEX IF NOT EXISTS movies_title_idx ON movies(title);
        CREATE INDEX IF NOT EXISTS users_joined_idx ON users(joined_at);
        """)
        for name, emoji in DEFAULT_CATEGORIES:
            await c.execute(
                "INSERT INTO categories(name,emoji) VALUES($1,$2) ON CONFLICT(name) DO NOTHING",
                name, emoji
            )

async def get_pool():
    if _pool is None:
        raise RuntimeError("Database hali ishga tushmagan.")
    return _pool

async def audit(actor_id, action, details=""):
    p = await get_pool()
    async with p.acquire() as c:
        await c.execute("INSERT INTO audit_logs(actor_id,action,details) VALUES($1,$2,$3)", actor_id, action, str(details)[:2000])

async def upsert_user(user_id, username, first_name):
    p = await get_pool()
    async with p.acquire() as c:
        await c.execute("""
        INSERT INTO users(user_id,username,first_name) VALUES($1,$2,$3)
        ON CONFLICT(user_id) DO UPDATE SET username=EXCLUDED.username,
        first_name=EXCLUDED.first_name,last_seen=NOW()
        """, user_id, username, first_name)

async def categories():
    p = await get_pool()
    async with p.acquire() as c:
        return await c.fetch("SELECT * FROM categories ORDER BY id")

async def category_by_id(category_id):
    p = await get_pool()
    async with p.acquire() as c:
        return await c.fetchrow("SELECT * FROM categories WHERE id=$1", category_id)

async def category_create(name, emoji="🎬", description=""):
    p = await get_pool()
    async with p.acquire() as c:
        return await c.fetchrow(
            "INSERT INTO categories(name,emoji,description) VALUES($1,$2,$3) RETURNING *",
            name.strip(), emoji.strip() or "🎬", description.strip()
        )

async def category_delete(category_id):
    p = await get_pool()
    async with p.acquire() as c:
        return await c.execute("DELETE FROM categories WHERE id=$1", category_id)

async def movie_create(category_id, title, year, genre, description, file_id,
                       channel_id=None, channel_message_id=None, added_by=None):
    p = await get_pool()
    async with p.acquire() as c:
        return await c.fetchrow("""
        INSERT INTO movies(category_id,title,year,genre,description,file_id,channel_id,
        channel_message_id,added_by)
        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING *
        """, category_id, title.strip(), year, genre.strip(), description.strip(),
             file_id, str(channel_id) if channel_id else None, channel_message_id, added_by)

async def movie_get(movie_id):
    p = await get_pool()
    async with p.acquire() as c:
        return await c.fetchrow("""
        SELECT m.*,c.name AS category_name,c.emoji AS category_emoji
        FROM movies m JOIN categories c ON c.id=m.category_id WHERE m.id=$1
        """, movie_id)

async def movies_list(category_id=None, limit=30, offset=0, include_hidden=False):
    p = await get_pool()
    async with p.acquire() as c:
        where = "" if include_hidden else "AND m.is_visible=TRUE"
        if category_id is None:
            return await c.fetch(f"""
            SELECT m.*,c.name AS category_name,c.emoji AS category_emoji
            FROM movies m JOIN categories c ON c.id=m.category_id
            WHERE TRUE {where} ORDER BY m.id DESC LIMIT $1 OFFSET $2
            """, limit, offset)
        return await c.fetch(f"""
        SELECT m.*,c.name AS category_name,c.emoji AS category_emoji
        FROM movies m JOIN categories c ON c.id=m.category_id
        WHERE m.category_id=$1 {where} ORDER BY m.id DESC LIMIT $2 OFFSET $3
        """, category_id, limit, offset)

async def movie_search(query, limit=15):
    p = await get_pool()
    async with p.acquire() as c:
        q = f"%{query.strip()}%"
        return await c.fetch("""
        SELECT m.*,c.name AS category_name,c.emoji AS category_emoji
        FROM movies m JOIN categories c ON c.id=m.category_id
        WHERE m.is_visible=TRUE AND (m.title ILIKE $1 OR COALESCE(m.genre,'') ILIKE $1
        OR CAST(COALESCE(m.year,0) AS TEXT)=$2)
        ORDER BY m.views DESC,m.id DESC LIMIT $3
        """, q, query.strip(), limit)

async def movie_update(movie_id, title, year, genre, description, category_id=None, visible=None):
    p = await get_pool()
    async with p.acquire() as c:
        return await c.execute("""
        UPDATE movies SET title=$2,year=$3,genre=$4,description=$5,
        category_id=COALESCE($6,category_id),is_visible=COALESCE($7,is_visible),updated_at=NOW()
        WHERE id=$1
        """, movie_id, title, year, genre, description, category_id, visible)

async def movie_delete(movie_id):
    p = await get_pool()
    async with p.acquire() as c:
        return await c.execute("DELETE FROM movies WHERE id=$1", movie_id)

async def movie_view(movie_id):
    p = await get_pool()
    async with p.acquire() as c:
        await c.execute("UPDATE movies SET views=views+1 WHERE id=$1", movie_id)

async def stats():
    p = await get_pool()
    async with p.acquire() as c:
        return {
            "users": await c.fetchval("SELECT COUNT(*) FROM users"),
            "active_users_7d": await c.fetchval("SELECT COUNT(*) FROM users WHERE last_seen>NOW()-INTERVAL '7 days'"),
            "movies": await c.fetchval("SELECT COUNT(*) FROM movies"),
            "visible_movies": await c.fetchval("SELECT COUNT(*) FROM movies WHERE is_visible=TRUE"),
            "categories": await c.fetchval("SELECT COUNT(*) FROM categories"),
            "views": await c.fetchval("SELECT COALESCE(SUM(views),0) FROM movies"),
            "top_movies": await c.fetch("SELECT title,views FROM movies ORDER BY views DESC LIMIT 5"),
            "recent_logs": await c.fetch("SELECT actor_id,action,details,created_at FROM audit_logs ORDER BY id DESC LIMIT 10"),
        }

async def user_ids():
    p = await get_pool()
    async with p.acquire() as c:
        return await c.fetch("SELECT user_id FROM users WHERE is_blocked=FALSE")

async def user_block(user_id, blocked=True):
    p = await get_pool()
    async with p.acquire() as c:
        await c.execute("UPDATE users SET is_blocked=$2 WHERE user_id=$1", user_id, blocked)

async def admin_permissions(user_id):
    p = await get_pool()
    async with p.acquire() as c:
        row = await c.fetchrow("SELECT permissions FROM admins WHERE user_id=$1", user_id)
        return set(row["permissions"]) if row else set()

async def admin_set(user_id, label, permissions, added_by):
    p = await get_pool()
    async with p.acquire() as c:
        await c.execute("""
        INSERT INTO admins(user_id,label,permissions,added_by) VALUES($1,$2,$3,$4)
        ON CONFLICT(user_id) DO UPDATE SET label=EXCLUDED.label,permissions=EXCLUDED.permissions
        """, user_id, label, permissions, added_by)

async def admin_remove(user_id):
    p = await get_pool()
    async with p.acquire() as c:
        await c.execute("DELETE FROM admins WHERE user_id=$1", user_id)

async def audit_recent(limit=30):
    p = await get_pool()
    async with p.acquire() as c:
        return await c.fetch("SELECT * FROM audit_logs ORDER BY id DESC LIMIT $1", limit)

async def setting_get(key, default=""):
    p = await get_pool()
    async with p.acquire() as c:
        value = await c.fetchval("SELECT value FROM settings WHERE key=$1", key)
        return value if value is not None else default

async def setting_set(key, value):
    p = await get_pool()
    async with p.acquire() as c:
        await c.execute("""
        INSERT INTO settings(key,value) VALUES($1,$2)
        ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value,updated_at=NOW()
        """, key, value)
