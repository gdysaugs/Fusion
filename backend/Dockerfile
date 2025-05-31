# マルチステージビルド - ステージ1: FaceFusionのセットアップ
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 as facefusion-builder

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y \
    git \
    git-lfs \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Git LFSを初期化
RUN git lfs install

# FaceFusionリポジトリをクローン
WORKDIR /workspace
RUN git clone https://github.com/facefusion/facefusion.git

# LFSファイルを確実にダウンロード
WORKDIR /workspace/facefusion
RUN git lfs fetch --all && \
    git lfs checkout

# ステージ2: Python環境のセットアップ
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 as builder

# 必要なシステムパッケージをインストール
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3.10-venv \
    && rm -rf /var/lib/apt/lists/*

# 仮想環境を作成
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# pipをアップグレード
RUN pip install --upgrade pip

# 作業ディレクトリ設定
WORKDIR /app

# 依存関係ファイルをコピー
COPY requirements.txt .

# 依存関係をインストール
RUN pip install --no-cache-dir -r requirements.txt

# ステージ3: 実行環境
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# 必要なシステムパッケージをインストール
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libglib2.0-0 \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 仮想環境をコピー
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# FaceFusionをコピー
COPY --from=facefusion-builder /workspace/facefusion /workspace/facefusion

# FaceFusion依存関係をインストール
WORKDIR /workspace/facefusion

# NumPy 1.xを先にインストール（互換性のため）
RUN pip install --no-cache-dir "numpy<2"

# requirements.txtから依存関係をインストール
RUN pip install -r requirements.txt --no-cache-dir

# 追加の依存関係（4GB VRAM最適化用）
RUN pip install --no-cache-dir --force-reinstall onnxruntime-gpu==1.16.3

# PyTorchを別途インストール
RUN pip install --no-cache-dir \
    torch==2.0.1 \
    torchvision==0.15.2 \
    torchaudio==2.0.2 \
    --index-url https://download.pytorch.org/whl/cu118

# NumPyを再度1.xに固定
RUN pip install --no-cache-dir --force-reinstall "numpy<2"

# 作業ディレクトリ設定
WORKDIR /app

# アプリケーションコードをコピー
COPY . .

# アップロード/出力ディレクトリ作成
RUN mkdir -p /app/uploads /app/outputs /workspace/uploads /workspace/outputs

# 環境変数設定
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/workspace/facefusion
ENV CUDA_MODULE_LOADING=LAZY
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# ポート公開
EXPOSE 8000

# 実行コマンド
CMD ["uvicorn", "app.main_celery:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]