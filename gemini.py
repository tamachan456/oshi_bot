import anthropic
import os
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
}

CATEGORY_HINTS = {
    "人物（歌手）":         "ライブ・リリース・メディア出演を優先",
    "グループ・チーム":     "ライブ・新曲・メンバー動向を優先",
    "キャラクター":         "グッズ・アニメ・コラボを優先",
    "スポーツ選手":         "試合結果・成績・怪我・次戦を優先",
    "俳優・女優":           "出演ドラマ・映画・舞台を優先",
    "お笑い・タレント":     "テレビ出演・ライブ・SNS話題を優先",
    "VTuber・配信者":       "配信・コラボ・グッズを優先",
    "海外セレブ":           "来日・最新作・受賞を優先",
    "モデル・インフルエンサー": "コラボ・ファッション誌・イベントを優先",
    "声優":                 "出演アニメ・CD・イベントを優先",
    "2.5次元・舞台":        "公演日程・キャスト・チケットを優先",
    "eスポーツ・ゲーマー":  "大会結果・配信予定を優先",
}

THEME_SEARCH_QUERIES = {
    "今話題の女性歌手": {
        "billboard": "Billboard Japan 女性アーティスト 2026 週間",
        "oricon":    "オリコン週間 女性歌手 ランキング 2026",
        "spotify":   "Spotify Japan 女性 急上昇 2026",
    },
    "今話題の男性歌手": {
        "billboard": "Billboard Japan 男性アーティスト 2026 週間",
        "oricon":    "オリコン週間 男性歌手 ランキング 2026",
        "spotify":   "Spotify Japan 男性 急上昇 2026",
    },
    "急上昇アニメキャラ": {
        "billboard": "Billboard Japan アニメ 2026",
        "oricon":    "オリコン アニメ グッズ 人気 2026",
        "spotify":   "Spotify Japan アニメ 急上昇 2026",
    },
    "話題のK-POPグループ": {
        "billboard": "Billboard Japan K-POP 2026",
        "oricon":    "オリコン K-POP ランキング 2026",
        "spotify":   "Spotify Japan K-POP 急上昇 2026",
    },
    "注目のスポーツ選手": {
        "billboard": "スポーツ選手 話題 急上昇 2026",
        "oricon":    "オリコン スポーツ 人気 2026",
        "spotify":   "スポーツ選手 SNS トレンド 2026",
    },
    "人気VTuber": {
        "billboard": "Billboard Japan VTuber 2026",
        "oricon":    "オリコン VTuber 人気 2026",
        "spotify":   "Spotify VTuber 急上昇 2026",
    },
    "今売れてるグッズ": {
        "billboard": "推し活 グッズ 人気 2026",
        "oricon":    "オリコン グッズ 売上 2026",
        "spotify":   "推し活 グッズ SNS 2026",
    },
}


def call_claude_with_search(prompt):
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            tools=[WEB_SEARCH_TOOL],
            messages=[{"role": "user", "content": prompt}]
        )
        result_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                result_text += block.text

        if response.stop_reason == "tool_use" and not result_text:
            messages = [{"role": "user", "content": prompt}]
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "検索完了"
                    })
            messages.append({"role": "user", "content": tool_results})
            final_response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
                tools=[WEB_SEARCH_TOOL],
                messages=messages
            )
            for block in final_response.content:
                if hasattr(block, "text"):
                    result_text += block.text

        return result_text.strip() if result_text else None
    except Exception as e:
        print(f"Claude API error: {e}")
        return None


def get_oshi_info(profile):
    oshi = profile.get("oshi_name", "")
    group = profile.get("group_name", "")
    genre = profile.get("genre", "すべて")
    category = profile.get("category", "人物（歌手）")
    memory_context = profile.get("memory_context", "")
    nickname = profile.get("nickname", "あなた")
    age_group = profile.get("age_group", "")
    hint = CATEGORY_HINTS.get(category, "公式情報を優先")

    # 年代別トーン設定
    tone_map = {
        "10代": "タメ口OK・絵文字多め・SNS感覚で話す",
        "20代": "フレンドリーで軽快・共感重視",
        "30代": "丁寧だけど親しみやすい・落ち着いたトーン",
        "40代": "丁寧語・信頼感重視・情報の正確さを大切に",
        "50代以上": "丁寧語・わかりやすい言葉・親切に",
    }
    tone = tone_map.get(age_group, "フレンドリーで自然な口語")

    memory_section = f"\n【記憶情報】\n{memory_context}\n→今日の情報と接続して発見を言語化する" if memory_context else ""

    prompt = f"""推し活コンシェルジュ「推し太郎」として「{oshi}」({group})の最新情報を検索して回答してください。
ユーザー名：{nickname}さん（{age_group}）
口調：{tone}・必ず「{nickname}さん」と呼びかける

検索：「{oshi} {group} 最新情報 2026」と「{oshi} 公式サイト」
優先：{hint}
禁止：「情報なし」で終わること禁止

【情報の扱い方】
- 公式サイト・大手メディア → 🟢確認済み情報として扱う
- Wikipedia → 🟡参考情報として扱う（「Wikipediaによると」と明記）
- SNS・まとめサイト → 🟠要確認として扱う（「〜との情報があります」と明記）
- 不確かな情報 → 🔴「未確認情報です。公式でご確認ください」と必ず添える
{memory_section}

フォーマット（必ず5件・信頼度・出典・URL付き）：

🌸 {oshi}の最新情報 🌸
━━━━━━━━━━━━━━
【情報1】信頼度：🟢 出典： タイトル： 内容：（60文字以内） 🔗
【情報2】信頼度： 出典： タイトル： 内容： 🔗
【情報3】信頼度： 出典： タイトル： 内容： 🔗
【情報4】信頼度： 出典： タイトル： 内容： 🔗
【情報5】信頼度： 出典： タイトル： 内容： 🔗
━━━━━━━━━━━━━━
💬 コンシェルジュからの一言（ファン目線の口語で・次の会話への誘い含む）
⚠️ ※情報は参考程度に。最新・正確な情報は公式サイトでご確認ください。"""

    return call_claude_with_search(prompt)


def get_trend_ranking(theme):
    queries = THEME_SEARCH_QUERIES.get(theme, {
        "billboard": f"{theme} Billboard Japan 2026",
        "oricon":    f"{theme} オリコン 2026",
        "spotify":   f"{theme} Spotify 急上昇 2026",
    })
    q_bill = queries.get("billboard", "")
    q_ori  = queries.get("oricon", "")
    q_spot = queries.get("spotify", "")

    prompt = f"""推し活コンシェルジュ「推し太郎」として「{theme}」のトレンドを3つの観点で検索して回答してください。

検索1：「{q_bill}」
検索2：「{q_ori}」
検索3：「{q_spot}」

禁止：「情報なし」で終わること禁止・必ず5件出す

【情報の扱い方】
- 公式・大手メディア → 🟢確認済み
- Wikipedia → 🟡参考情報（「Wikipediaによると」と明記）
- その他 → 🟠要確認（「〜との情報があります」と明記）
- 不確かな情報 → 🔴「未確認。公式でご確認ください」と添える

フォーマット：

🔥 {theme} トレンドランキング 🔥
━━━━━━━━━━━━━━
📊 Billboard Japan｜📊 オリコン｜📊 Spotify Japan
（各1〜3位を簡潔に）
━━━━━━━━━━━━━━
🏆 総合TOP5
🥇1位 名前： 信頼度： 理由：（50文字以内） 出典： 🔗
🥈2位 名前： 信頼度： 理由： 出典： 🔗
🥉3位 名前： 信頼度： 理由： 出典： 🔗
4位 名前： 信頼度： 理由： 出典： 🔗
5位 名前： 信頼度： 理由： 出典： 🔗
━━━━━━━━━━━━━━
💬 コンシェルジュからの一言（口語で・深掘りの誘い含む）"""

    return call_claude_with_search(prompt)


def free_chat(user_text, oshi_name, memory_context="", nickname="あなた", age_group=""):
    """ユーザーの自由入力に豊富な回答を返す"""

    memory_section = f"\n【このファンの記憶・現場情報】\n{memory_context}\n→必ずこの情報を活用する" if memory_context else ""

    tone_map = {
        "10代": "タメ口OK・絵文字多め・SNS感覚",
        "20代": "フレンドリーで軽快",
        "30代": "丁寧だけど親しみやすい",
        "40代": "丁寧語・信頼感重視",
        "50代以上": "丁寧語・わかりやすく親切に",
    }
    tone = tone_map.get(age_group, "フレンドリーで自然")

    # 質問タイプを判定してプロンプトを変える
    is_profile = any(kw in user_text for kw in ["好き", "趣味", "出身", "年齢", "誕生", "身長", "血液型", "性格"])
    is_live = any(kw in user_text for kw in ["ライブ", "コンサート", "公演", "ツアー", "チケット"])
    is_news = any(kw in user_text for kw in ["最近", "新曲", "リリース", "ドラマ", "映画", "CM", "出演"])

    if is_profile:
        search_hint = "プロフィール・パーソナリティ情報を中心に"
    elif is_live:
        search_hint = "ライブ・コンサート情報を中心に検索して"
    elif is_news:
        search_hint = "最新ニュース・リリース情報を中心に検索して"
    else:
        search_hint = "必要に応じてweb_searchで検索して"

    prompt = f"""推し活コンシェルジュ「推し太郎」として「{oshi_name}」の推しファンと会話してください。
ユーザー名：{nickname}さん（{age_group}）
口調：{tone}・必ず「{nickname}さん」と呼びかける
{memory_section}

{nickname}さんからの質問：「{user_text}」

{search_hint}以下の構成で豊富に答えてください：

【メイン回答】
質問への直接の答えを具体的に。

【もっと詳しく】
関連する豆知識・裏話・意外な事実を1〜2つ。

【ファン目線のひとこと】
推しへの愛を感じる自然な口語コメント。

【次の深掘りはこちら】
関連する話題への誘い（例：「ちなみに〇〇も知ってますか？」）

ルール：
- 記憶情報があれば必ず「あなたが教えてくれた〇〇と繋がりますね！」と接続する
- わからないことは正直に「わかりません」と言う
- 全体で300文字程度にまとめる
- Wikipediaの情報は使ってOKだが「Wikipediaによると」と明記する
- 公式情報以外は「〜との情報があります」「〜と言われています」など不確かさを表現する
- 回答の最後に必ず「※情報は参考程度に。最新情報は公式でご確認ください🔍」を入れる"""

    return call_claude_with_search(prompt)


def get_chat_cache_key(oshi_name, user_text):
    """自由会話のキャッシュキーを生成"""
    import hashlib
    # 質問を正規化（空白除去・小文字化）してハッシュ化
    normalized = user_text.strip().lower().replace(" ", "").replace("　", "")
    hash_str = hashlib.md5(f"{oshi_name}:{normalized}".encode()).hexdigest()[:8]
    return f"chat:{oshi_name}:{hash_str}"


def is_cacheable_question(user_text):
    """キャッシュできる質問かどうか判定（時事性のない質問はキャッシュ可）"""
    # リアルタイム性が必要な質問はキャッシュしない
    realtime_keywords = ["今日", "明日", "今週", "最近", "速報", "今", "いつ", "チケット", "残席"]
    return not any(kw in user_text for kw in realtime_keywords)
