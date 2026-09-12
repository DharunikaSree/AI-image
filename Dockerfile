FROM python:3.11-slim

# Install system dependencies for OpenMP, PyTorch, FAISS, and health checking
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for optimal Docker layer caching
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# Pre-cache Hugging Face transformer models (CLIP & ViT base) using memory-safe stream download
RUN python -c "from huggingface_hub import snapshot_download; \
    snapshot_download('openai/clip-vit-base-patch32'); \
    snapshot_download('google/vit-base-patch16-224')"

# Copy application code, trained AI models, and FAISS vector index from repository root
COPY backend/ /app/backend/
COPY models/ /app/models/
COPY data/ /app/data/

# Ensure runtime uploads directory exists
RUN mkdir -p /app/backend/uploads

# Set working directory to backend so relative DB paths and app imports resolve seamlessly
WORKDIR /app/backend

# Configure runtime environment
ENV PYTHONPATH=/app/backend
ENV AI_MODE=model
ENV MODEL_PATH=/app/models/vit_fashion_classifier/vit_fashion_classifier.pt
ENV DATABASE_URL=sqlite:///./fashion.db
ENV DATASET_IMAGES_DIR=/app/data/images,./data/images,../data/images

EXPOSE 8000

# Container healthcheck (evaluates dynamic $PORT with fallback to 8000)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

