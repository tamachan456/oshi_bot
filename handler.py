from linebot.v3.messaging import (
    ReplyMessageRequest, PushMessageRequest, TextMessage,
    QuickReply, QuickReplyItem, MessageAction
)
from gemini import get_oshi_info, get_trend_ranking
from memory import (
    save_user, load_user, update_state,
    save_memory, load_memories, build_memory_context,
    get_last_visit, save_history,
    get_user_plan, set_user_plan, can_add_oshi,
    add_oshi_registration, get_registered_oshi_list,
    remove_oshi, get_plan_info, PLANS
)
from scheduler import (
    load_trend_cache, load_oshi_cache,
    save_oshi_cache, save_trend_cache
)
import threading

MODE_OPTIONS = ["推しを登録", "トレンドを探す", "推しリスト", "プラン確認"]

CATEGORY_OPTIONS_1 = ["人物（歌手）", "グループ・チーム", "キャラクター", "スポーツ選手"]
CATEGORY_OPTIONS_2 = ["俳優・女優", "お笑い・タレント", "VTuber・配信者", "海外セレブ"]
CATEGORY_OPTIONS_3 = ["モデル・インフルエンサー", "声優", "2.5次元・舞台", "eスポーツ・ゲーマー"]

GENRE_OPTIONS = ["ライブ・イベント", "SNS・投稿", "グッズ", "すべて"]
FREQ_OPTIONS = ["毎日", "週3回", "週1回"]

TREND_THEMES = [
    "今話題の女性歌手",
    "今話題の男性歌手",
    "急上昇アニメキャラ",
    "話題のK-POPグループ",
    "注目のスポーツ選手",
    "人気VTuber",
    "今売れてるグッズ",
    "自由に入力する",
]

ALL_CATEGORIES = CATEGORY_OPTIONS_1 + CATEGORY_OPTIONS_2 + CATEGORY_OPTIONS_3

OSHI_QUESTIONS = {
    "人物（歌手）":         "推しの名前を教えてください😊\n（例：赤西仁、五木ひろし）",
    "グループ・チーム":     "グループ名を教えてください😊\n（例：嵐、BTS）",
    "キャラクター":         "推しのキャラクター名を教えてください😊\n（例：スンスン、ピカチュウ）",
    "スポーツ選手":         "推しの選手名を教えてください😊\n（例：大の里、大谷翔平）",
    "俳優・女優":           "推しの名前を教えてください😊\n（例：菅田将暉、浜辺美波）",
    "お笑い・タレント":     "推しの名前・コンビ名を教えてください😊\n（例：千鳥、霜降り明星）",
    "VTuber・配信者":       "推しのVTuber名を教えてください😊\n（例：葛葉、大空スバル）",
    "海外セレブ":           "推しの名前を教えてください😊\n（例：テイラー・スウィフト）",
    "モデル・インフルエンサー": "推しの名前を教えてください😊\n（例：藤田ニコル）",
    "声優":                 "推しの名前を教えてください😊\n（例：花江夏樹、水瀬いのり）",
    "2.5次元・舞台":        "推しの名前・作品名を教えてください😊\n（例：刀剣乱舞、宝塚）",
    "eスポーツ・ゲーマー":  "推しの名前を教えてください😊\n（例：ときど、加藤純一）",
}

GROUP_QUESTIONS = {
    "人物（歌手）":         "所属グループや事務所を教えてください。ソロの場合は「ソロ」と入力してください。",
    "グループ・チーム":     "ジャンルを教えてください。（例：K-POP、バンド）",
    "キャラクター":         "作品名を教えてください。（例：ポケモン、呪術廻戦）",
    "スポーツ選手":         "競技・所属を教えてください。（例：大相撲・二所ノ関部屋）",
    "俳優・女優":           "所属事務所や代表作を教えてください。わからなければ「不明」でOK。",
    "お笑い・タレント":     "所属事務所を教えてください。（例：吉本興業）",
    "VTuber・配信者":       "所属事務所を教えてください。（例：にじさんじ、個人）",
    "海外セレブ":           "国籍・ジャンルを教えてください。（例：アメリカ・歌手）",
    "モデル・インフルエンサー": "主な活動SNSや媒体を教えてください。（例：Instagram）",
    "声優":                 "代表作を教えてください。わからなければ「不明」でOK。",
    "2.5次元・舞台":        "所属・出演作品を教えてください。",
    "eスポーツ・ゲーマー":  "主なゲームタイトルを教えてください。（例：ストリートファイター）",
}


def reply(line_bot_api, reply_token, messages):
    if not isinstance(messages, list):
        messages = [messages]
    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=reply_token,
        messages=messages
    ))


def text_msg(text):
    return TextMessage(text=text)


def text_with_quick(text, options):
    items = [
        QuickReplyItem(action=MessageAction(label=o[:20], text=o))
        for o in options
    ]
    return TextMessage(text=text, quick_reply=QuickReply(items=items))


def fetch_and_push(line_bot_api, user_id, profile):
    try:
        oshi_name = profile.get("oshi_name", "")
        group = profile.get("group_name", "")
        oshi_key = f"{oshi_name}_{group}"

        # ── まずキャッシュを確認（8時間以内のデータがあれば即返す）
        cached = load_oshi_cache(oshi_key)
        if cached:
            print(f"[CACHE HIT] {oshi_name}")
            # 記憶コンテキストを付加してキャッシュを返す
            memory_context = build_memory_context(user_id)
            nick = profile.get("nickname", "")
            if memory_context:
                msg = cached + f"\n\n━━━━━━━━━━━━━━\n🗒️ {nick}さんの記憶情報\n{memory_context}"
            else:
                msg = cached
        else:
            # ── キャッシュなし→リアルタイム検索
            print(f"[CACHE MISS] {oshi_name} → リアルタイム検索")
            memory_context = build_memory_context(user_id)
            profile_with_memory = dict(profile)
            profile_with_memory["memory_context"] = memory_context
            msg = get_oshi_info(profile_with_memory)
            if not msg:
                msg = "情報が見つかりませんでした😢"
            else:
                # 取得できたらキャッシュに保存
                save_oshi_cache(oshi_key, msg)

        line_bot_api.push_message(PushMessageRequest(
            to=user_id, messages=[text_msg(msg)]
        ))

        # 履歴保存
        from datetime import datetime
        save_history(user_id, f"{oshi_name}の情報を提供（{datetime.now().strftime('%m/%d %H:%M')}）")

    except Exception as e:
        print(f"Push error: {e}")


def fetch_trend_and_push(line_bot_api, user_id, theme):
    try:
        # ── まずキャッシュを確認
        cached = load_trend_cache(theme)
        if cached:
            print(f"[CACHE HIT] トレンド: {theme}")
            msg = cached
        else:
            # ── キャッシュなし→リアルタイム検索
            print(f"[CACHE MISS] トレンド: {theme} → リアルタイム検索")
            msg = get_trend_ranking(theme)
            if not msg:
                msg = "トレンド情報が見つかりませんでした😢"
            else:
                save_trend_cache(theme, msg)

        line_bot_api.push_message(PushMessageRequest(
            to=user_id, messages=[text_msg(msg)]
        ))
    except Exception as e:
        print(f"Trend push error: {e}")


def handle_message(line_bot_api, reply_token, user_id, text):
    # DBから状態とプロフィールを読み込み
    profile, state = load_user(user_id)

    # ── スタート・メニュー
    if text in ["スタート", "start", "はじめる", "登録", "メニュー"]:
        last_visit = get_last_visit(user_id)
        nick = profile.get("nickname", "")
        oshi = profile.get("oshi_name", "")

        # 再訪問ユーザー
        if last_visit and nick and oshi:
            greeting = f"おかえりなさい、{nick}さん🌸\n{oshi}の情報、今日も調べましょうか？"
            save_user(user_id, profile, "ask_mode")
            reply(line_bot_api, reply_token,
                  text_with_quick(greeting, MODE_OPTIONS))
            return

        # 初回：ニックネームを聞く
        save_user(user_id, profile, "ask_nickname")
        reply(line_bot_api, reply_token,
              text_msg(
                  "こんにちは！推し太郎です🌟\n\n"
                  "まず、あなたのニックネームを教えてください😊\n"
                  "（例：さくら、ゆうき、たろう）"
              ))
        return

    # ── ニックネーム入力
    if state == "ask_nickname":
        profile["nickname"] = text
        save_user(user_id, profile, "ask_age")
        reply(line_bot_api, reply_token,
              text_with_quick(
                  f"{text}さんですね✨\nつぎに年代を教えてください😊",
                  ["10代", "20代", "30代", "40代", "50代以上"]
              ))
        return

    # ── 年代選択
    if state == "ask_age" and text in ["10代", "20代", "30代", "40代", "50代以上"]:
        profile["age_group"] = text
        nick = profile.get("nickname", "")
        save_user(user_id, profile, "ask_mode")
        reply(line_bot_api, reply_token,
              text_with_quick(
                  f"{nick}さん、よろしくお願いします🌟\nどちらにしますか？",
                  MODE_OPTIONS
              ))
        return

    # ── モード選択
    if state == "ask_mode":
        if text == "推しを登録":
            # プラン上限チェック
            can_add, count, limit, plan = can_add_oshi(user_id)
            if not can_add:
                plan_info = get_plan_info(plan)
                reply(line_bot_api, reply_token,
                      text_with_quick(
                          f"現在の{plan_info['name']}では推しを{limit}人まで登録できます。\n"
                          f"現在{count}人登録済みです。\n\n"
                          f"上位プランにアップグレードすると更に登録できます！",
                          ["プラン確認", "推しリスト", "メニュー"]
                      ))
                return
            save_user(user_id, profile, "ask_category_1")
            reply(line_bot_api, reply_token,
                  text_with_quick(
                      "推しのジャンルを選んでください✨（1/3）\n「次へ→」で他のジャンルも見られます",
                      CATEGORY_OPTIONS_1 + ["次へ→"]
                  ))
            return
        elif text == "トレンドを探す":
            save_user(user_id, profile, "ask_trend_theme")
            reply(line_bot_api, reply_token,
                  text_with_quick("どんなジャンルのトレンドを調べますか？🔥", TREND_THEMES))
            return
        elif text == "推しリスト":
            _show_oshi_list(line_bot_api, reply_token, user_id)
            return
        elif text == "プラン確認":
            _show_plan_info(line_bot_api, reply_token, user_id)
            return

    # ── カテゴリ選択（3ページ）
    if state == "ask_category_1":
        if text in CATEGORY_OPTIONS_1:
            _set_category(line_bot_api, reply_token, user_id, profile, text)
            return
        elif text == "次へ→":
            save_user(user_id, profile, "ask_category_2")
            reply(line_bot_api, reply_token,
                  text_with_quick("ジャンルを選んでください✨（2/3）",
                                  CATEGORY_OPTIONS_2 + ["←戻る", "次へ→"]))
            return

    if state == "ask_category_2":
        if text == "←戻る":
            save_user(user_id, profile, "ask_category_1")
            reply(line_bot_api, reply_token,
                  text_with_quick("ジャンルを選んでください✨（1/3）",
                                  CATEGORY_OPTIONS_1 + ["次へ→"]))
            return
        if text in CATEGORY_OPTIONS_2:
            _set_category(line_bot_api, reply_token, user_id, profile, text)
            return
        elif text == "次へ→":
            save_user(user_id, profile, "ask_category_3")
            reply(line_bot_api, reply_token,
                  text_with_quick("ジャンルを選んでください✨（3/3）",
                                  CATEGORY_OPTIONS_3 + ["←戻る"]))
            return

    if state == "ask_category_3":
        if text == "←戻る":
            save_user(user_id, profile, "ask_category_2")
            reply(line_bot_api, reply_token,
                  text_with_quick("ジャンルを選んでください✨（2/3）",
                                  CATEGORY_OPTIONS_2 + ["←戻る", "次へ→"]))
            return
        if text in CATEGORY_OPTIONS_3:
            _set_category(line_bot_api, reply_token, user_id, profile, text)
            return

    # ── 推し名入力
    if state == "ask_oshi":
        profile["oshi_name"] = text
        save_user(user_id, profile, "ask_group")
        category = profile.get("category", "人物（歌手）")
        q = GROUP_QUESTIONS.get(category, "詳細を教えてください。")
        reply(line_bot_api, reply_token,
              text_msg(f"「{text}」ですね！💕\n{q}"))
        return

    # ── 所属・詳細入力
    if state == "ask_group":
        profile["group_name"] = text
        save_user(user_id, profile, "ask_genre")
        reply(line_bot_api, reply_token,
              text_with_quick("どんな情報が欲しいですか？🎯", GENRE_OPTIONS))
        return

    # ── ジャンル選択
    if state == "ask_genre" and text in GENRE_OPTIONS:
        profile["genre"] = text
        save_user(user_id, profile, "ask_freq")
        reply(line_bot_api, reply_token,
              text_with_quick("情報を届ける頻度はどうしますか？📅", FREQ_OPTIONS))
        return

    # ── 頻度選択
    if state == "ask_freq" and text in FREQ_OPTIONS:
        profile["frequency"] = text
        save_user(user_id, profile, "registered")
        oshi = profile["oshi_name"]
        group = profile["group_name"]
        genre = profile["genre"]
        freq = profile["frequency"]
        category = profile.get("category", "")

        # 推し登録リストに追加
        ok, count, limit, plan = add_oshi_registration(
            user_id, oshi, group, category
        )
        plan_info = get_plan_info(plan)

        nick = profile.get("nickname", "")
        confirm = (
            f"✅ 登録完了！{nick}さん🌸\n\n"
            f"推し：{oshi}\n"
            f"ジャンル：{category}\n"
            f"詳細：{group}\n"
            f"情報種別：{genre}\n"
            f"頻度：{freq}\n\n"
            f"📋 {plan_info['name']}：{count}/{limit}人登録済み\n\n"
            f"「最新情報」で今すぐ情報をお届けします🌸\n"
            f"「現場情報」でライブMCや現場エピソードを教えてもらえると、より深い情報をお届けできます🎤"
        )
        reply(line_bot_api, reply_token, text_msg(confirm))
        return

    # ── 最新情報リクエスト
    if text in ["最新情報", "情報", "教えて"] and state == "registered":
        if not profile:
            reply(line_bot_api, reply_token,
                  text_msg("まず「スタート」と送って登録してください😊"))
            return
        reply(line_bot_api, reply_token,
              text_msg(f"🔍 {profile['oshi_name']}の情報を調べています...少々お待ちください！"))
        t = threading.Thread(target=fetch_and_push, args=(line_bot_api, user_id, profile))
        t.daemon = True
        t.start()
        return

    # ── 現場情報・エピソード登録
    if text == "現場情報" and state == "registered":
        save_user(user_id, profile, "ask_episode")
        reply(line_bot_api, reply_token,
              text_msg(
                  "ライブや現場で気になった一言・エピソードを教えてください🎤\n\n"
                  "例：「ライブMCで〇〇って言ってた」\n"
                  "例：「FCイベントで△△の話をしてた」\n\n"
                  "あなたしか知らない情報が、深掘りのカギになります！"
              ))
        return

    # ── エピソード受け取り
    if state == "ask_episode":
        save_memory(user_id, "episode", text)
        save_user(user_id, profile, "registered")
        oshi = profile.get("oshi_name", "推し")
        reply(line_bot_api, reply_token,
              text_msg(
                  f"ありがとうございます！記憶しました🗒️\n\n"
                  f"「{text[:30]}...」\n\n"
                  f"次回「最新情報」を送ると、この情報を使って{oshi}の深掘り分析をします✨"
              ))
        return

    # ── トレンドテーマ選択
    if state == "ask_trend_theme":
        if text == "自由に入力する":
            save_user(user_id, profile, "ask_trend_free")
            reply(line_bot_api, reply_token,
                  text_msg("調べたいテーマを自由に入力してください✨"))
            return
        else:
            save_user(user_id, profile, "trend_mode")
            reply(line_bot_api, reply_token,
                  text_msg(f"🔥「{text}」のトレンドを調べています...\n少々お待ちください！"))
            t = threading.Thread(target=fetch_trend_and_push, args=(line_bot_api, user_id, text))
            t.daemon = True
            t.start()
            return

    # ── 自由テーマ入力
    if state == "ask_trend_free":
        theme = text
        save_user(user_id, profile, "trend_mode")
        reply(line_bot_api, reply_token,
              text_msg(f"🔥「{theme}」のトレンドを調べています...\n少々お待ちください！"))
        t = threading.Thread(target=fetch_trend_and_push, args=(line_bot_api, user_id, theme))
        t.daemon = True
        t.start()
        return

    # ── トレンド呼び出し（登録済みからも）
    if text in ["トレンド", "ランキング", "話題"]:
        save_user(user_id, profile, "ask_trend_theme")
        reply(line_bot_api, reply_token,
              text_with_quick("どんなジャンルのトレンドを調べますか？🔥", TREND_THEMES))
        return

    # ── 推しリスト表示
    if text in ["推しリスト", "登録リスト"]:
        _show_oshi_list(line_bot_api, reply_token, user_id)
        return

    # ── プラン確認
    if text in ["プラン確認", "プラン", "料金"]:
        _show_plan_info(line_bot_api, reply_token, user_id)
        return

    # ── プランアップグレード
    if text in ["ライトプランに変更", "スタンダードプランに変更", "プレミアムプランに変更"]:
        plan_map = {
            "ライトプランに変更":         "lite",
            "スタンダードプランに変更":   "standard",
            "プレミアムプランに変更":     "premium",
        }
        new_plan = plan_map[text]
        set_user_plan(user_id, new_plan)
        plan_info = get_plan_info(new_plan)
        reply(line_bot_api, reply_token,
              text_msg(
                  f"✅ {plan_info['name']}に変更しました！\n"
                  f"月額：¥{plan_info['price']}\n"
                  f"推し登録上限：{plan_info['oshi_limit']}人\n\n"
                  f"「推しを登録」で新しい推しを追加できます🌸"
              ))
        return

    # ── リセット
    if text in ["設定", "変更", "リセット"]:
        save_user(user_id, {}, "start")
        reply(line_bot_api, reply_token,
              text_msg("設定をリセットしました🔄\n「スタート」と送って再登録してください。\n※記憶した現場情報は保持されています。"))
        return

    # ── 記憶確認
    if text in ["記憶", "覚えてること", "メモ"]:
        memories = load_memories(user_id, limit=5)
        if memories:
            mem_text = "📝 記憶している情報：\n\n"
            for m in memories:
                date = m["created_at"][:10]
                mem_text += f"・{m['content'][:30]}（{date}）\n"
            mem_text += "\nこれらの情報を使って深掘り分析します🔍"
        else:
            mem_text = "まだ現場情報は記憶していません。\n「現場情報」と送って教えてください🎤"
        reply(line_bot_api, reply_token, text_msg(mem_text))
        return

    # ── その他：自由入力をClaudeに渡して自然に返答
    if state == "registered":
        from gemini import free_chat, get_chat_cache_key, is_cacheable_question
        from scheduler import load_cache, save_cache
        memory_context = build_memory_context(user_id)
        oshi = profile.get("oshi_name", "")

        reply(line_bot_api, reply_token,
              text_msg("🤔 考えています..."))

        nick = profile.get("nickname", "")
        age_group = profile.get("age_group", "")

        def push_free_chat():
            try:
                result = None

                # ① キャッシュ確認（時事性のない質問のみ）
                if is_cacheable_question(text):
                    cache_key = get_chat_cache_key(oshi, text)
                    cached = load_cache(cache_key, max_age_hours=24)
                    if cached:
                        print(f"[CHAT CACHE HIT] {text[:20]}")
                        result = cached

                # ② キャッシュなし→Claude API
                if not result:
                    print(f"[CHAT API] {text[:20]}")
                    result = free_chat(text, oshi, memory_context, nick, age_group)
                    if result and is_cacheable_question(text):
                        cache_key = get_chat_cache_key(oshi, text)
                        save_cache(cache_key, result)

                if result:
                    line_bot_api.push_message(PushMessageRequest(
                        to=user_id, messages=[text_msg(result)]
                    ))
                else:
                    line_bot_api.push_message(PushMessageRequest(
                        to=user_id, messages=[text_msg(
                            "うまく答えられませんでした😢\n"
                            "「最新情報」で推しの情報をお届けします🌸"
                        )]
                    ))
            except Exception as e:
                print(f"free_chat error: {e}")

        t = threading.Thread(target=push_free_chat)
        t.daemon = True
        t.start()
        return

    elif state == "trend_mode":
        reply(line_bot_api, reply_token,
              text_with_quick(
                  "次はどうしますか？",
                  ["別のテーマ", "最新情報", "メニュー"]
              ))
    else:
        reply(line_bot_api, reply_token,
              text_msg("スタートと送ると始められます。すでに登録済みの方はメニューと送ってください"))


def _show_oshi_list(line_bot_api, reply_token, user_id):
    """登録済み推しリストを表示"""
    oshi_list = get_registered_oshi_list(user_id)
    plan = get_user_plan(user_id)
    plan_info = get_plan_info(plan)
    can_add, count, limit, _ = can_add_oshi(user_id)

    if oshi_list:
        text = f"📋 登録済み推し一覧\n（{plan_info['name']}：{count}/{limit}人）\n\n"
        for i, o in enumerate(oshi_list, 1):
            text += f"{i}. {o['oshi_name']}（{o['group_name']}）\n"
        if can_add:
            text += f"\nあと{limit - count}人追加できます✨"
        else:
            text += f"\n上限に達しています。プレミアムプランで無制限になります🌟"
    else:
        text = "まだ推しが登録されていません\n「スタート」→「推しを登録」で登録できます🌸"

    reply(line_bot_api, reply_token,
          text_with_quick(text, ["推しを登録", "プラン確認", "メニュー"]))


def _show_plan_info(line_bot_api, reply_token, user_id):
    """プラン情報を表示"""
    current_plan = get_user_plan(user_id)
    _, count, limit, _ = can_add_oshi(user_id)

    text = "📊 料金プラン一覧\n\n"
    for key, info in PLANS.items():
        mark = "✅ 現在のプラン" if key == current_plan else ""
        text += (
            f"{'▶' if key == current_plan else '　'} {info['name']} {mark}\n"
            f"   月額：¥{info['price']}\n"
            f"   推し登録：{info['oshi_limit']}人まで\n\n"
        )
    text += f"現在：{count}/{limit}人登録済み"

    options = []
    if current_plan != "lite":
        options.append("ライトプランに変更")
    if current_plan != "standard":
        options.append("スタンダードプランに変更")
    if current_plan != "premium":
        options.append("プレミアムプランに変更")
    options.append("メニュー")

    reply(line_bot_api, reply_token, text_with_quick(text, options))


def _set_category(line_bot_api, reply_token, user_id, profile, category):
    profile["category"] = category
    save_user(user_id, profile, "ask_oshi")
    q = OSHI_QUESTIONS.get(category, "推しの名前を教えてください😊")
    reply(line_bot_api, reply_token, text_msg(q))
