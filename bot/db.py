import os
import time
from typing import Optional

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT,
    lang TEXT NOT NULL DEFAULT 'ar',
    pref TEXT NOT NULL DEFAULT 'ask',
    banned INTEGER NOT NULL DEFAULT 0,
    downloads INTEGER NOT NULL DEFAULT 0,
    premium_until INTEGER NOT NULL DEFAULT 0,
    big TEXT NOT NULL DEFAULT 'split',
    doc INTEGER NOT NULL DEFAULT 0,
    referrer INTEGER NOT NULL DEFAULT 0,
    joined INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY,
    file_id TEXT NOT NULL,
    created INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS usage (
    uid INTEGER NOT NULL,
    day TEXT NOT NULL,
    n INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (uid, day)
);
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid INTEGER NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    ts INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_uid ON history(uid, id);
CREATE TABLE IF NOT EXISTS platform_stats (
    platform TEXT PRIMARY KEY,
    n INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS subs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid INTEGER NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    last_id TEXT,
    created INTEGER NOT NULL,
    UNIQUE (uid, url)
);
"""

# أعمدة اتضافت بعد أول إصدار (لترقية قواعد البيانات القديمة)
MIGRATIONS = {
    "users": {
        "premium_until": "INTEGER NOT NULL DEFAULT 0",
        "big": "TEXT NOT NULL DEFAULT 'split'",
        "doc": "INTEGER NOT NULL DEFAULT 0",
        "referrer": "INTEGER NOT NULL DEFAULT 0",
    }
}


def _today() -> str:
    return time.strftime("%Y-%m-%d")


class DB:
    def __init__(self, path: str):
        self.path = path
        self.conn: Optional[aiosqlite.Connection] = None

    async def init(self) -> None:
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.executescript(SCHEMA)
        for table, cols in MIGRATIONS.items():
            cur = await self.conn.execute(f"PRAGMA table_info({table})")
            have = {r["name"] for r in await cur.fetchall()}
            for col, ddl in cols.items():
                if col not in have:
                    await self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()

    async def checkpoint(self) -> None:
        await self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        await self.conn.commit()

    # ---------------------------------------------------------- users
    async def ensure_user(
        self, uid: int, name: str, lang_code: Optional[str], referrer: int = 0
    ) -> dict:
        cur = await self.conn.execute(
            "SELECT lang, pref, banned, premium_until, big, doc FROM users WHERE id=?",
            (uid,),
        )
        row = await cur.fetchone()
        if row is None:
            lang = "ar" if (lang_code or "").lower().startswith("ar") else "en"
            await self.conn.execute(
                "INSERT INTO users (id, name, lang, referrer, joined) VALUES (?,?,?,?,?)",
                (uid, name, lang, referrer, int(time.time())),
            )
            await self.conn.commit()
            return {
                "lang": lang, "pref": "ask", "banned": False, "premium": False,
                "big": "split", "doc": False, "new": True,
            }
        return {
            "lang": row["lang"],
            "pref": row["pref"],
            "banned": bool(row["banned"]),
            "premium": row["premium_until"] > time.time(),
            "big": row["big"],
            "doc": bool(row["doc"]),
            "new": False,
        }

    async def user_exists(self, uid: int) -> bool:
        cur = await self.conn.execute("SELECT 1 FROM users WHERE id=?", (uid,))
        return await cur.fetchone() is not None

    async def user_info(self, uid: int) -> dict:
        cur = await self.conn.execute(
            "SELECT downloads, premium_until, joined FROM users WHERE id=?", (uid,)
        )
        row = await cur.fetchone()
        if not row:
            return {"downloads": 0, "premium_until": 0, "joined": 0}
        return dict(row)

    async def get_prefs(self, uid: int) -> dict:
        cur = await self.conn.execute("SELECT big, doc FROM users WHERE id=?", (uid,))
        row = await cur.fetchone()
        if not row:
            return {"big": "split", "doc": False}
        return {"big": row["big"], "doc": bool(row["doc"])}

    async def set_lang(self, uid: int, lang: str) -> None:
        await self.conn.execute("UPDATE users SET lang=? WHERE id=?", (lang, uid))
        await self.conn.commit()

    async def set_pref(self, uid: int, pref: str) -> None:
        await self.conn.execute("UPDATE users SET pref=? WHERE id=?", (pref, uid))
        await self.conn.commit()

    async def set_big(self, uid: int, big: str) -> None:
        await self.conn.execute("UPDATE users SET big=? WHERE id=?", (big, uid))
        await self.conn.commit()

    async def set_doc(self, uid: int, doc: bool) -> None:
        await self.conn.execute("UPDATE users SET doc=? WHERE id=?", (int(doc), uid))
        await self.conn.commit()

    async def set_banned(self, uid: int, banned: bool) -> None:
        await self.conn.execute(
            "INSERT INTO users (id, name, joined, banned) VALUES (?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET banned=excluded.banned",
            (uid, "", int(time.time()), int(banned)),
        )
        await self.conn.commit()

    async def count_referrals(self, uid: int) -> int:
        cur = await self.conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE referrer=?", (uid,)
        )
        return (await cur.fetchone())["c"]

    async def set_premium(self, uid: int, days: int) -> int:
        """days<=0 يلغي الاشتراك. يرجع تاريخ الانتهاء (unix)."""
        now = int(time.time())
        await self.conn.execute(
            "INSERT OR IGNORE INTO users (id, name, joined) VALUES (?,?,?)",
            (uid, "", now),
        )
        if days <= 0:
            until = 0
        else:
            cur = await self.conn.execute(
                "SELECT premium_until FROM users WHERE id=?", (uid,)
            )
            row = await cur.fetchone()
            base = max(now, row["premium_until"] if row else 0)
            until = base + days * 86400
        await self.conn.execute(
            "UPDATE users SET premium_until=? WHERE id=?", (until, uid)
        )
        await self.conn.commit()
        return until

    async def is_premium(self, uid: int) -> bool:
        cur = await self.conn.execute(
            "SELECT premium_until FROM users WHERE id=?", (uid,)
        )
        row = await cur.fetchone()
        return bool(row and row["premium_until"] > time.time())

    # -------------------------------------------------- usage / history
    async def usage_today(self, uid: int) -> int:
        cur = await self.conn.execute(
            "SELECT n FROM usage WHERE uid=? AND day=?", (uid, _today())
        )
        row = await cur.fetchone()
        return row["n"] if row else 0

    async def add_history(self, uid: int, url: str, title: str) -> int:
        cur = await self.conn.execute(
            "INSERT INTO history (uid, url, title, ts) VALUES (?,?,?,?)",
            (uid, url, (title or "")[:200], int(time.time())),
        )
        hid = cur.lastrowid
        await self.conn.execute(
            "DELETE FROM history WHERE uid=? AND id NOT IN "
            "(SELECT id FROM history WHERE uid=? ORDER BY id DESC LIMIT 30)",
            (uid, uid),
        )
        await self.conn.commit()
        return hid

    async def record(self, uid: int, url: str, title: str, platform: str = "") -> None:
        await self.conn.execute(
            "UPDATE users SET downloads = downloads + 1 WHERE id=?", (uid,)
        )
        await self.conn.execute(
            "INSERT INTO usage (uid, day, n) VALUES (?,?,1) "
            "ON CONFLICT(uid, day) DO UPDATE SET n = n + 1",
            (uid, _today()),
        )
        if platform:
            await self.conn.execute(
                "INSERT INTO platform_stats (platform, n) VALUES (?,1) "
                "ON CONFLICT(platform) DO UPDATE SET n = n + 1",
                (platform[:40],),
            )
        await self.conn.commit()
        if url:
            await self.add_history(uid, url, title)

    async def get_history(self, uid: int, limit: int = 8) -> list:
        cur = await self.conn.execute(
            "SELECT id, title, url FROM history WHERE uid=? ORDER BY id DESC LIMIT ?",
            (uid, limit),
        )
        return [dict(r) for r in await cur.fetchall()]

    async def get_history_item(self, uid: int, hid: int) -> Optional[dict]:
        cur = await self.conn.execute(
            "SELECT id, title, url FROM history WHERE uid=? AND id=?", (uid, hid)
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------ subscriptions
    async def count_subs(self, uid: int) -> int:
        cur = await self.conn.execute("SELECT COUNT(*) AS c FROM subs WHERE uid=?", (uid,))
        return (await cur.fetchone())["c"]

    async def add_sub(self, uid: int, url: str, title: str, last_id: str) -> bool:
        cur = await self.conn.execute(
            "INSERT OR IGNORE INTO subs (uid, url, title, last_id, created) VALUES (?,?,?,?,?)",
            (uid, url, (title or "")[:150], last_id, int(time.time())),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def list_subs(self, uid: int) -> list:
        cur = await self.conn.execute(
            "SELECT id, url, title FROM subs WHERE uid=? ORDER BY id", (uid,)
        )
        return [dict(r) for r in await cur.fetchall()]

    async def del_sub(self, uid: int, sid: int) -> None:
        await self.conn.execute("DELETE FROM subs WHERE uid=? AND id=?", (uid, sid))
        await self.conn.commit()

    async def delete_user_subs(self, uid: int) -> None:
        await self.conn.execute("DELETE FROM subs WHERE uid=?", (uid,))
        await self.conn.commit()

    async def all_subs(self) -> list:
        cur = await self.conn.execute(
            "SELECT s.id, s.uid, s.url, s.title, s.last_id FROM subs s "
            "JOIN users u ON u.id = s.uid WHERE u.banned = 0"
        )
        return [dict(r) for r in await cur.fetchall()]

    async def update_sub_last(self, sid: int, last_id: str) -> None:
        await self.conn.execute("UPDATE subs SET last_id=? WHERE id=?", (last_id, sid))
        await self.conn.commit()

    # ------------------------------------------------------- admin/stats
    async def all_user_ids(self) -> list:
        cur = await self.conn.execute("SELECT id FROM users WHERE banned=0")
        return [r["id"] for r in await cur.fetchall()]

    async def stats(self) -> dict:
        cur = await self.conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(downloads),0) AS d, "
            "COALESCE(SUM(banned),0) AS b, "
            "COALESCE(SUM(CASE WHEN premium_until > ? THEN 1 ELSE 0 END),0) AS p "
            "FROM users",
            (int(time.time()),),
        )
        r = await cur.fetchone()
        cur = await self.conn.execute("SELECT COUNT(*) AS c FROM cache")
        c = await cur.fetchone()
        cur = await self.conn.execute(
            "SELECT COUNT(DISTINCT uid) AS a, COALESCE(SUM(n),0) AS t FROM usage WHERE day=?",
            (_today(),),
        )
        a = await cur.fetchone()
        cur = await self.conn.execute("SELECT COUNT(*) AS c FROM subs")
        sb = await cur.fetchone()
        return {
            "users": r["n"], "downloads": r["d"], "banned": r["b"], "premium": r["p"],
            "cached": c["c"], "active_today": a["a"], "downloads_today": a["t"],
            "subs": sb["c"],
        }

    async def top_platforms(self, limit: int = 5) -> list:
        cur = await self.conn.execute(
            "SELECT platform, n FROM platform_stats ORDER BY n DESC LIMIT ?", (limit,)
        )
        return [(r["platform"], r["n"]) for r in await cur.fetchall()]

    # ------------------------------------------------------------ cache
    async def cache_get(self, key: str) -> Optional[str]:
        cur = await self.conn.execute("SELECT file_id FROM cache WHERE key=?", (key,))
        row = await cur.fetchone()
        return row["file_id"] if row else None

    async def cache_set(self, key: str, file_id: str) -> None:
        await self.conn.execute(
            "INSERT OR REPLACE INTO cache (key, file_id, created) VALUES (?,?,?)",
            (key, file_id, int(time.time())),
        )
        await self.conn.commit()

    async def cache_delete(self, key: str) -> None:
        await self.conn.execute("DELETE FROM cache WHERE key=?", (key,))
        await self.conn.commit()

    async def cache_clear(self) -> int:
        cur = await self.conn.execute("DELETE FROM cache")
        await self.conn.commit()
        return cur.rowcount