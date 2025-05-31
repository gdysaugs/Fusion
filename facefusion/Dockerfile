# マルチステージビルド - ステージ1: Git LFS対応
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 as builder

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

# ステージ2: 実行環境
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# 必要なパッケージをインストール
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

# Python環境設定
RUN python3 -m pip install --upgrade pip

# 作業ディレクトリ設定
WORKDIR /workspace

# ビルダーステージからFaceFusionをコピー
COPY --from=builder /workspace/facefusion /workspace/facefusion

# FaceFusion依存関係をインストール
WORKDIR /workspace/facefusion

# NumPy 1.xを先にインストール（互換性のため）
RUN pip3 install --no-cache-dir "numpy<2"

# requirements.txtから依存関係をインストール
RUN pip3 install -r requirements.txt --no-cache-dir

# 追加の依存関係（4GB VRAM最適化用）
# onnxruntime-gpuを先にインストール
RUN pip3 install --no-cache-dir --force-reinstall onnxruntime-gpu==1.16.3

# PyTorchを別途インストール
RUN pip3 install --no-cache-dir \
    torch==2.0.1 \
    torchvision==0.15.2 \
    torchaudio==2.0.2 \
    --index-url https://download.pytorch.org/whl/cu118

# NumPyを再度1.xに固定（他のパッケージが2.xをインストールした場合の対策）
RUN pip3 install --no-cache-dir --force-reinstall "numpy<2"

# アップロード/出力ディレクトリ作成
RUN mkdir -p /workspace/uploads /workspace/outputs

# 環境変数設定
ENV PYTHONUNBUFFERED=1
ENV CUDA_MODULE_LOADING=LAZY
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# ポート公開
EXPOSE 7860

# 実行コマンド
CMD ["python3", "facefusion.py", "run", "--execution-providers", "cuda"]