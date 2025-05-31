# FaceFusion Web Application

動画の顔を画像の顔に変換するWebアプリケーション

## 技術スタック

- **フロントエンド**: React + Vite + TailwindCSS
- **バックエンド**: FastAPI (Python)
- **顔変換エンジン**: FaceFusion
- **コンテナ**: Docker (マルチステージビルド)
- **GPU**: CUDA 11.8 (RTX 3050 4GB VRAM対応)

## セットアップ

1. プロジェクトディレクトリに移動:
```bash
cd ~/projects/my-website
```

2. 環境変数の設定:
```bash
cp .env.example .env
```

3. Dockerイメージのビルドと起動:
```bash
docker compose up --build
```

## アクセス

- フロントエンド: http://localhost:3000
- バックエンドAPI: http://localhost:8000
- API ドキュメント: http://localhost:8000/docs

## 使い方

1. ブラウザで http://localhost:3000 にアクセス
2. 変換したい動画をアップロード
3. 置き換えたい顔の画像をアップロード
4. 「処理開始」ボタンをクリック
5. 処理完了後、結果をダウンロード

## 注意事項

- 初回ビルド時はFaceFusionのモデルダウンロードのため時間がかかります
- 4GB VRAMでの動作のため、大きな動画の処理には時間がかかる場合があります