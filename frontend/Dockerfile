# マルチステージビルド - ステージ1: ビルド
FROM node:18-alpine as builder

WORKDIR /app

# package.jsonとpackage-lock.jsonをコピー
COPY package*.json ./

# 依存関係をインストール（キャッシュ活用）
RUN --mount=type=cache,target=/root/.npm \
    npm install

# アプリケーションコードをコピー
COPY . .

# ビルド
RUN npm run build

# ステージ2: 実行環境
FROM node:18-alpine

WORKDIR /app

# ビルド成果物をコピー
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package*.json ./

# 本番用依存関係のみインストール
RUN npm install --omit=dev

# Viteサーバー用の設定
RUN npm install -g serve

EXPOSE 3000

# 静的ファイルをサーブ
CMD ["serve", "-s", "dist", "-l", "3000"]