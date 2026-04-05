# 推し太郎 Bot セットアップ手順

## フォルダ構成
```
oshi_bot/
├── server.py       # メインサーバー
├── handler.py      # 会話フロー管理
├── gemini.py       # Gemini情報取得
├── .env            # APIキー設定
└── requirements.txt
```

## セットアップ手順

### 1. パッケージのインストール
```bash
pip install -r requirements.txt
```

### 2. .envファイルにAPIキーを入力
`.env`ファイルを開いて3つのキーを入力してください：
- `LINE_CHANNEL_ACCESS_TOKEN` → LINE Developersのチャンネルアクセストークン
- `LINE_CHANNEL_SECRET` → LINE Developersのチャンネルシークレット
- `GEMINI_API_KEY` → Google AI StudioのAPIキー

### 3. サーバーを起動
```bash
python server.py
```

### 4. ngrokでLINEに公開（ローカル実行の場合）
```bash
ngrok http 5000
```
表示されたURLの末尾に `/callback` をつけて
LINE DevelopersのWebhook URLに設定してください。
例：`https://xxxx.ngrok.io/callback`

## ユーザーの使い方
1. Botを友だち追加
2. 「スタート」と送る
3. 質問に答えて推しを登録
4. 「最新情報」で情報を取得

## コマンド一覧
| コマンド | 動作 |
|---------|------|
| スタート | 登録開始 |
| 最新情報 | 推し情報を取得 |
| 設定 | 登録内容をリセット |
