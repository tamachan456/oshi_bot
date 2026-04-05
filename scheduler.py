"""
scheduler.py
1日3回（朝8時・昼12時・夜20時）に自動でデータ収集してDBにキャッシュする
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import sqlite3
import json
import os
import time

DB_PATH = os.path.join(os.path.dirname(__file__), "oshi_memory.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_cache_table():
    """キャッシュテーブルを初期化"""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS cache (
            cache_key   TEXT PRIMARY KEY,
            content     TEXT,
            updated_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS trend_cache (
            theme       TEXT PRIMARY KEY,
            content     TEXT,
            updated_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS oshi_cache (
            oshi_key    TEXT PRIMARY KEY,
            content     TEXT,
            updated_at  TEXT
        );
        """)


def save_cache(cache_key, content):
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO cache (cache_key, content, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
            content=excluded.content,
            updated_at=excluded.updated_at
        """, (cache_key, content, now))


def load_cache(cache_key, max_age_hours=8):
    """キャッシュを取得（max_age_hours時間以内のものだけ有効）"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT content, updated_at FROM cache WHERE cache_key=?",
            (cache_key,)
        ).fetchone()
    if not row:
        return None
    # 鮮度チェック
    updated = datetime.fromisoformat(row["updated_at"])
    age_hours = (datetime.now() - updated).total_seconds() / 3600
    if age_hours > max_age_hours:
        return None
    return row["content"]


def save_trend_cache(theme, content):
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO trend_cache (theme, content, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(theme) DO UPDATE SET
            content=excluded.content,
            updated_at=excluded.updated_at
        """, (theme, content, now))


def load_trend_cache(theme, max_age_hours=8):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT content, updated_at FROM trend_cache WHERE theme=?",
            (theme,)
        ).fetchone()
    if not row:
        return None
    updated = datetime.fromisoformat(row["updated_at"])
    age_hours = (datetime.now() - updated).total_seconds() / 3600
    if age_hours > max_age_hours:
        return None
    return row["content"]


def save_oshi_cache(oshi_key, content):
    """推し個人情報のキャッシュ保存"""
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO oshi_cache (oshi_key, content, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(oshi_key) DO UPDATE SET
            content=excluded.content,
            updated_at=excluded.updated_at
        """, (oshi_key, content, now))


def load_oshi_cache(oshi_key, max_age_hours=8):
    """推し個人情報のキャッシュ取得"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT content, updated_at FROM oshi_cache WHERE oshi_key=?",
            (oshi_key,)
        ).fetchone()
    if not row:
        return None
    updated = datetime.fromisoformat(row["updated_at"])
    age_hours = (datetime.now() - updated).total_seconds() / 3600
    if age_hours > max_age_hours:
        return None
    return row["content"]


def get_all_registered_oshi():
    """登録済みの全推しリストを取得（重複なし）"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT profile FROM users WHERE state='registered'"
        ).fetchall()
    oshi_list = []
    seen = set()
    for row in rows:
        try:
            profile = json.loads(row["profile"])
            oshi_name = profile.get("oshi_name", "")
            if oshi_name and oshi_name not in seen:
                seen.add(oshi_name)
                oshi_list.append(profile)
        except:
            pass
    return oshi_list


def collect_trend_data():
    """トレンドデータを収集してキャッシュに保存"""
    from gemini import get_trend_ranking

    themes = [
        "今話題の女性歌手",
        "今話題の男性歌手",
        "急上昇アニメキャラ",
        "話題のK-POPグループ",
        "注目のスポーツ選手",
        "人気VTuber",
        "今売れてるグッズ",
    ]

    now = datetime.now().strftime("%H:%M")
    print(f"[{now}] トレンドデータ収集開始 ({len(themes)}テーマ)")

    for i, theme in enumerate(themes):
        try:
            print(f"  収集中: {theme}")
            result = get_trend_ranking(theme)
            if result:
                save_trend_cache(theme, result)
                print(f"  ✅ キャッシュ保存: {theme}")
            else:
                print(f"  ❌ 取得失敗: {theme}")
        except Exception as e:
            print(f"  ❌ エラー ({theme}): {e}")

        # レート制限対策：テーマ間に30秒待機
        if i < len(themes) - 1:
            print(f"  ⏳ 次のテーマまで30秒待機...")
            time.sleep(60)

    print(f"[{now}] トレンドデータ収集完了")


def collect_oshi_data():
    """登録済み推しの情報を収集してキャッシュに保存"""
    from gemini import get_oshi_info

    oshi_list = get_all_registered_oshi()
    now = datetime.now().strftime("%H:%M")
    print(f"[{now}] 推しデータ収集開始 ({len(oshi_list)}件)")

    for i, profile in enumerate(oshi_list):
        oshi_name = profile.get("oshi_name", "")
        group = profile.get("group_name", "")
        oshi_key = f"{oshi_name}_{group}"

        try:
            print(f"  収集中: {oshi_name}")
            result = get_oshi_info(profile)
            if result:
                save_oshi_cache(oshi_key, result)
                print(f"  ✅ キャッシュ保存: {oshi_name}")
            else:
                print(f"  ❌ 取得失敗: {oshi_name}")
        except Exception as e:
            print(f"  ❌ エラー ({oshi_name}): {e}")

        # レート制限対策：推し間に30秒待機
        if i < len(oshi_list) - 1:
            print(f"  ⏳ 次の推しまで30秒待機...")
            time.sleep(60)

    print(f"[{now}] 推しデータ収集完了")


def collect_all():
    """全データ収集（トレンド＋推し）"""
    print(f"\n{'='*40}")
    print(f"定期収集開始: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*40}")
    collect_trend_data()
    collect_oshi_data()
    print(f"{'='*40}\n")


def start_scheduler():
    """スケジューラーを起動（朝8時・昼12時・夜20時）"""
    init_cache_table()

    scheduler = BackgroundScheduler(timezone="Asia/Tokyo")

    # 朝8時
    scheduler.add_job(
        collect_all,
        CronTrigger(hour=8, minute=0, timezone="Asia/Tokyo"),
        id="morning_collect"
    )
    # 昼12時
    scheduler.add_job(
        collect_all,
        CronTrigger(hour=12, minute=0, timezone="Asia/Tokyo"),
        id="noon_collect"
    )
    # 夜20時
    scheduler.add_job(
        collect_all,
        CronTrigger(hour=20, minute=0, timezone="Asia/Tokyo"),
        id="evening_collect"
    )

    scheduler.start()
    print("✅ スケジューラー起動（朝8時・昼12時・夜20時に自動収集）")
    return scheduler
