import os
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import ApiClient, Configuration, MessagingApi
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError
from handler import handle_message
from scheduler import start_scheduler, init_cache_table, collect_all
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


@app.route("/collect", methods=["GET"])
def manual_collect():
    import threading
    t = threading.Thread(target=collect_all)
    t.daemon = True
    t.start()
    return "collect started", 200


@handler.add(MessageEvent, message=TextMessageContent)
def on_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    reply_token = event.reply_token
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        handle_message(line_bot_api, reply_token, user_id, text)


if __name__ == "__main__":
    init_cache_table()
    start_scheduler()
    print("Bot started")
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
