from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api import admin, auth, products, recommendations, search, user_routes
from app.core.config import get_settings
from app.core.database import Base, engine
from app import models  # noqa: ensures models are registered before create_all
from app.services.ai_classifier import vit_classifier
from app.services.attribute_classifier import attribute_classifier
from app.services.embedding import embedding_service

settings = get_settings()

Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Ensure required filesystem paths and database tables exist
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    # 2. Preload & warm AI models during startup to eliminate cold-start latency
    if settings.AI_MODE == "model":
        try:
            vit_classifier.warmup()
        except Exception as e:
            print(f"[!] Warning: ViT classifier preload encountered error: {e}")

    try:
        embedding_service.warmup()
    except Exception as e:
        print(f"[!] Warning: Embedding service preload encountered error: {e}")

    try:
        attribute_classifier.warmup()
    except Exception as e:
        print(f"[!] Warning: Attribute classifier preload encountered error: {e}")

    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-based visual fashion search, classification and recommendation API.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.get("/uploads/deepfashion/{filename}")
def serve_deepfashion_image(filename: str):
    # Prevent path traversal attempts
    if ".." in filename or "/" in filename or "\\" in filename or "\x00" in filename:
        return Response(status_code=400, content="Invalid filename")

    # Check configured dataset directories in order (high-res candidates first, then fallback directories)
    for img_dir in settings.dataset_image_dirs:
        if img_dir.exists():
            img_file = (img_dir / filename).resolve()
            try:
                # Ensure the resolved file is strictly within the allowed directory
                if img_file.is_relative_to(img_dir.resolve()) and img_file.is_file():
                    return FileResponse(
                        str(img_file),
                        media_type="image/jpeg",
                        headers={"Cache-Control": "no-cache, must-revalidate"},
                    )
            except (ValueError, RuntimeError):
                continue

    return Response(status_code=404)


app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(search.router)
app.include_router(recommendations.router)
app.include_router(user_routes.router)
app.include_router(admin.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Never leak stack traces to the client.
    return JSONResponse(status_code=500, content={"detail": "Something went wrong. Please try again."})


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "ai_mode": settings.AI_MODE,
        "models": {
            "vit_classifier": vit_classifier.loaded,
            "attribute_classifier": attribute_classifier.loaded,
            "clip_model": embedding_service.loaded,
            "faiss_index": embedding_service.faiss_index is not None,
            "faiss_vectors": embedding_service.faiss_index.ntotal if embedding_service.faiss_index else 0,
        },
    }
