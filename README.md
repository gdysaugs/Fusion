# FaceFusion Web Application - 高速顔交換システム

🚀 **Celery + Redis**による非同期処理で高速化した顔交換Webアプリケーション

## 🎯 特徴

- ⚡ **超高速処理**: Celery + Redisによる非同期タスク処理（処理時間: 約96秒）
- 🎨 **リアルタイム進捗表示**: WebSocketとポーリングによる二重の進捗確認
- 🖥️ **GPU最適化**: CUDA 11.8対応、4GB VRAM最適化設定
- 📦 **完全Docker化**: マルチステージビルドによる効率的なコンテナ構成
- 🔄 **スケーラブル**: Celery Workerの並列処理対応

## 🛠️ 技術スタック

### フロントエンド
- **React 18** + **Vite** - 高速な開発環境
- **TailwindCSS** - モダンなUIデザイン
- **Axios** - HTTP通信
- **React Dropzone** - ドラッグ&ドロップファイルアップロード

### バックエンド
- **FastAPI** - 高性能な非同期Webフレームワーク
- **Celery 5.3** - 分散タスクキュー
- **Redis 7** - メッセージブローカー & 結果バックエンド
- **Flower** - Celeryタスク監視ダッシュボード

### AI/ML
- **FaceFusion** - 顔交換エンジン
- **ONNX Runtime GPU** - 推論高速化
- **PyTorch 2.0** - ディープラーニングフレームワーク

### インフラ
- **Docker** - コンテナ化
- **Docker Compose** - マルチコンテナ管理
- **NVIDIA CUDA 11.8** - GPU計算
- **Ubuntu 22.04** - ベースOS

## 📋 必要な環境

- WSL2 (Windows) または Linux
- Docker & Docker Compose
- NVIDIA GPU (CUDA 11.8対応)
- 最低4GB VRAM
- 16GB以上のRAM推奨

## 🚀 セットアップ

### 1. リポジトリのクローン
```bash
git clone https://github.com/gdysaugs/Fusion.git
cd Fusion
```

### 2. 環境変数の設定
```bash
cp .env.example .env
```

### 3. Dockerイメージのビルドと起動
```bash
# ビルドキャッシュを活用した高速ビルド
docker compose build

# 全サービス起動
docker compose up -d
```

### 4. サービスの確認
```bash
# 起動状況確認
docker compose ps

# ログの確認
docker compose logs -f
```

## 🌐 アクセスURL

| サービス | URL | 説明 |
|---------|-----|------|
| フロントエンド | http://localhost:3000 | Reactアプリケーション |
| バックエンドAPI | http://localhost:8000 | FastAPI |
| API ドキュメント | http://localhost:8000/docs | Swagger UI |
| Flower ダッシュボード | http://localhost:5555 | Celeryタスク監視 |
| Redis | localhost:6379 | Redisサーバー |

## 📖 使い方

1. **アプリケーションにアクセス**
   - ブラウザで http://localhost:3000 を開く

2. **ファイルのアップロード**
   - 動画ファイル（.mp4, .avi, .mov, .webm）をドラッグ&ドロップ
   - 顔画像（.jpg, .jpeg, .png）をドラッグ&ドロップ

3. **処理の実行**
   - 「処理開始」ボタンをクリック
   - リアルタイムで進捗が表示される

4. **結果のダウンロード**
   - 処理完了後、「結果をダウンロード」ボタンが表示
   - クリックして変換済み動画をダウンロード

## 🏗️ アーキテクチャ

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   Backend   │────▶│    Redis    │
│   (React)   │     │  (FastAPI)  │     │   (Broker)  │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                     │
                           ▼                     ▼
                    ┌─────────────┐     ┌─────────────┐
                    │   Celery    │────▶│ FaceFusion  │
                    │   Worker    │     │   (GPU)     │
                    └─────────────┘     └─────────────┘
```

### 処理フロー

1. **ファイルアップロード**
   - フロントエンド → FastAPI → ローカルストレージ

2. **タスクキューイング**
   - FastAPI → Celery → Redis

3. **非同期処理**
   - Celery Worker → FaceFusion (GPU処理)

4. **進捗更新**
   - Celery → Redis → FastAPI → WebSocket/Polling → フロントエンド

5. **結果取得**
   - 完成ファイル → FastAPI → フロントエンド

## 🔧 開発者向け情報

### プロジェクト構造
```
Fusion/
├── backend/
│   ├── app/
│   │   ├── main_celery.py    # FastAPIメインアプリ
│   │   ├── celery_app.py     # Celery設定
│   │   ├── tasks.py          # Celeryタスク定義
│   │   └── ...
│   ├── Dockerfile            # マルチステージビルド
│   └── requirements.txt      # Python依存関係
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # メインコンポーネント
│   │   └── ...
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml       # Docker Compose設定
└── README.md
```

### Celery設定の詳細

```python
# celery_app.py
celery_app = Celery(
    "face_fusion_tasks",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
)

# 重要な設定
celery_app.conf.update(
    task_track_started=True,          # タスク開始を追跡
    task_acks_late=True,              # タスク完了後にACK
    task_reject_on_worker_lost=True,  # ワーカー喪失時に再キュー
    worker_prefetch_multiplier=1,     # プリフェッチ無効化
)
```

### パフォーマンス最適化

1. **GPU最適化**
   ```python
   # 4GB VRAM用設定
   "--execution-thread-count", "2",
   "--face-detector-score", "0.5",
   ```

2. **Docker最適化**
   - マルチステージビルド
   - レイヤーキャッシュ活用
   - 最小限のベースイメージ

3. **並列処理**
   ```bash
   # 複数ワーカー起動（オプション）
   docker compose scale celery-worker=3
   ```

## 📊 パフォーマンス

| 処理内容 | 時間 |
|---------|------|
| 動画アップロード | < 1秒 |
| タスクキューイング | < 0.1秒 |
| 顔交換処理（30秒動画） | 約96秒 |
| 結果ダウンロード | < 1秒 |

## 🐛 トラブルシューティング

### GPU関連
```bash
# NVIDIA ドライバー確認
nvidia-smi

# Docker GPU サポート確認
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### Celery関連
```bash
# ワーカーログ確認
docker compose logs celery-worker

# Flower ダッシュボード
http://localhost:5555
```

### Redis関連
```bash
# Redis CLI
docker compose exec redis redis-cli
> ping
> info
```

## 🔒 セキュリティ

- 環境変数による設定管理
- Dockerネットワーク分離
- CORS設定
- ファイルアップロード制限

## 📝 ライセンス

本プロジェクトはMITライセンスの下で公開されています。

## 🤝 貢献

プルリクエストを歓迎します！

1. Fork
2. Feature branch作成 (`git checkout -b feature/amazing-feature`)
3. Commit (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing-feature`)
5. Pull Request作成

## 👥 作者

- GitHub: [@gdysaugs](https://github.com/gdysaugs)

## 🙏 謝辞

- [FaceFusion](https://github.com/facefusion/facefusion) - 素晴らしい顔交換エンジン
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能Webフレームワーク
- [Celery](https://docs.celeryproject.org/) - 分散タスクキュー

---

⭐ このプロジェクトが役立った場合は、スターをお願いします！