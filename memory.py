import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "oshi_memory.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """DBとテーブルを初期化"""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     TEXT PRIMARY KEY,
            profile     TEXT,
            state       TEXT DEFAULT 'start',
            created_at  TEXT,
            updated_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS memories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT,
            category    TEXT,
            content     TEXT,
            created_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT,
            summary     TEXT,
            created_at  TEXT
        );
        """)


# ── ユーザー情報 ──────────────────────────

def save_user(user_id, profile, state):
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO users (user_id, profile, state, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            profile=excluded.profile,
            state=excluded.state,
            updated_at=excluded.updated_at
        """, (user_id, json.dumps(profile, ensure_ascii=False), state, now, now))


def load_user(user_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
    if not row:
        return {}, "start"
    profile = json.loads(row["profile"]) if row["profile"] else {}
    return profile, row["state"]


def update_state(user_id, state):
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute("""
        UPDATE users SET state=?, updated_at=? WHERE user_id=?
        """, (state, now, user_id))


# ── 記憶（現場エピソード・ファン知識） ──────────

def save_memory(user_id, category, content):
    """
    category例：
      'episode'   ライブMC・現場エピソード
      'faninfo'   ユーザーが持つ独自情報
      'goods'     グッズ・購入情報
      'event'     イベント参加記録
    """
    # 重複チェック：同じ内容が直近10件にあれば保存しない
    with get_conn() as conn:
        existing = conn.execute("""
        SELECT id FROM memories
        WHERE user_id=? AND category=? AND content=?
        ORDER BY created_at DESC LIMIT 1
        """, (user_id, category, content)).fetchone()
        if existing:
            print(f"[MEMORY] 重複スキップ: {content[:20]}")
            return
        now = datetime.now().isoformat()
        conn.execute("""
        INSERT INTO memories (user_id, category, content, created_at)
        VALUES (?, ?, ?, ?)
        """, (user_id, category, content, now))


def load_memories(user_id, limit=10):
    """直近の記憶を取得"""
    with get_conn() as conn:
        rows = conn.execute("""
        SELECT category, content, created_at FROM memories
        WHERE user_id=?
        ORDER BY created_at DESC LIMIT ?
        """, (user_id, limit)).fetchall()
    return [dict(r) for r in rows]


def load_memories_by_category(user_id, category):
    with get_conn() as conn:
        rows = conn.execute("""
        SELECT content, created_at FROM memories
        WHERE user_id=? AND category=?
        ORDER BY created_at DESC LIMIT 5
        """, (user_id, category)).fetchall()
    return [dict(r) for r in rows]


# ── 会話履歴 ──────────────────────────────

def save_history(user_id, summary):
    """提供した情報のサマリーを保存"""
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO history (user_id, summary, created_at)
        VALUES (?, ?, ?)
        """, (user_id, summary, now))
        # 直近20件だけ保持
        conn.execute("""
        DELETE FROM history WHERE user_id=? AND id NOT IN (
            SELECT id FROM history WHERE user_id=?
            ORDER BY created_at DESC LIMIT 20
        )
        """, (user_id, user_id))


def load_history(user_id, limit=5):
    """直近の会話履歴を取得"""
    with get_conn() as conn:
        rows = conn.execute("""
        SELECT summary, created_at FROM history
        WHERE user_id=?
        ORDER BY created_at DESC LIMIT ?
        """, (user_id, limit)).fetchall()
    return [dict(r) for r in rows]


def build_memory_context(user_id):
    """Claudeに渡す記憶コンテキストを構築"""
    memories = load_memories(user_id, limit=10)
    history = load_history(user_id, limit=3)

    context = ""

    if memories:
        context += "【このユーザーの記憶・現場情報】\n"
        for m in memories:
            date = m["created_at"][:10]
            context += f"・[{m['category']}] {m['content']}（{date}）\n"
        context += "\n"

    if history:
        context += "【前回までに提供した情報】\n"
        for h in history:
            date = h["created_at"][:10]
            context += f"・{h['summary']}（{date}）\n"
        context += "\n"

    return context


def get_last_visit(user_id):
    """最後に会話した日時を返す"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT updated_at FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
    if not row:
        return None
    return row["updated_at"][:10]


# ── プラン管理 ──────────────────────────────

PLANS = {
    "lite":     {"name": "ライトプラン",      "price": 300,  "oshi_limit": 1},
    "standard": {"name": "スタンダードプラン", "price": 500,  "oshi_limit": 3},
    "premium":  {"name": "プレミアムプラン",   "price": 980,  "oshi_limit": 99},
}


def init_plan_table():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS user_plans (
            user_id     TEXT PRIMARY KEY,
            plan        TEXT DEFAULT 'lite',
            updated_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS oshi_registrations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT,
            oshi_name   TEXT,
            group_name  TEXT,
            category    TEXT,
            created_at  TEXT
        );
        """)


def get_user_plan(user_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT plan FROM user_plans WHERE user_id=?", (user_id,)
        ).fetchone()
    return row["plan"] if row else "lite"


def set_user_plan(user_id, plan):
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO user_plans (user_id, plan, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            plan=excluded.plan,
            updated_at=excluded.updated_at
        """, (user_id, plan, now))


def get_oshi_count(user_id):
    """登録済み推しの数を返す"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM oshi_registrations WHERE user_id=?",
            (user_id,)
        ).fetchone()
    return row["cnt"] if row else 0


def can_add_oshi(user_id):
    """プランの上限内かどうか確認"""
    plan = get_user_plan(user_id)
    limit = PLANS[plan]["oshi_limit"]
    count = get_oshi_count(user_id)
    return count < limit, count, limit, plan


def add_oshi_registration(user_id, oshi_name, group_name, category):
    """推しを登録（プラン上限チェック付き）"""
    can_add, count, limit, plan = can_add_oshi(user_id)
    if not can_add:
        return False, count, limit, plan
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO oshi_registrations (user_id, oshi_name, group_name, category, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, (user_id, oshi_name, group_name, category, now))
    return True, count + 1, limit, plan


def get_registered_oshi_list(user_id):
    """登録済み推しリストを返す"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT oshi_name, group_name, category FROM oshi_registrations WHERE user_id=? ORDER BY created_at",
            (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def remove_oshi(user_id, oshi_name):
    """推しの登録を解除"""
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM oshi_registrations WHERE user_id=? AND oshi_name=?",
            (user_id, oshi_name)
        )


def get_plan_info(plan):
    return PLANS.get(plan, PLANS["lite"])


# 起動時にDB初期化
init_db()
init_plan_table()
