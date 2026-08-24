# Lumière — AI Visual Fashion Search & Recommendation System

Upload a fashion photo or screenshot. AI identifies the category, color, pattern,
and style, then searches a product catalog for visually similar items — showing
the closest matches, cheaper alternatives, color variants, and similar styles,
each with a transparent, explainable match score.

> **Scope note:** this is a real, runnable full-stack project (not pseudo-code),
> built to demonstrate the complete architecture end-to-end. The AI runs in an
> honest **Demo AI Mode** by default: classification uses deterministic pixel
> analysis (color clustering, texture/edge density) rather than a trained neural
> network, and similarity search uses real HSV-histogram + texture embeddings
> with cosine similarity — so search genuinely works out of the box, without
> requiring a GPU, a trained model, or any external API keys. Every integration
> point for swapping in a trained PyTorch/TensorFlow classifier is isolated in
> one file (see `AI Model Setup` below) so upgrading never touches other code.

---

## 1. Features

- AI-based clothing detection & attribute extraction (category, color, pattern, style, sleeve, neckline, gender category, season)
- Visual similarity search via image embeddings + cosine similarity
- Affordable alternatives with budget filtering (Under ₹500 / ₹500–1000 / ₹1000–2000 / ₹2000–5000 / custom)
- Color variant grouping
- Similar-style recommendations
- Transparent, explainable recommendation scoring (7 weighted signals, fully configurable)
- JWT authentication, favorites, search history, user style/color/budget preferences
- Admin dashboard: KPIs, charts (searches/day, top categories, popular colors, price distribution), full product CRUD, on-demand embedding generation
- Premium, responsive, light/dark-ready React + Tailwind UI
- Loading/empty/error states everywhere, friendly error messages, no leaked stack traces

## 2. Architecture

```
React (Vite/TS/Tailwind) --REST--> FastAPI --> SQLAlchemy --> SQLite/MySQL
                                     |
                                     +--> AI classification service (demo/model)
                                     +--> Embedding + cosine similarity service
                                     +--> Configurable recommendation engine
```

## 3. Tech Stack

**Frontend:** React, Vite, TypeScript, Tailwind CSS, React Router, Axios, Framer Motion, Lucide, Recharts
**Backend:** FastAPI, Pydantic, SQLAlchemy, JWT (python-jose), Passlib/bcrypt
**Database:** SQLite by default (zero setup); MySQL-ready via `DATABASE_URL`
**AI:** Pillow + NumPy for demo-mode classification/embeddings; swap point documented for a real PyTorch/TensorFlow model

## 4. Folder Structure

```
ai-fashion-search/
├── backend/
│   ├── app/
│   │   ├── api/          # route handlers (auth, products, search, recommendations, favorites/history/profile, admin)
│   │   ├── core/         # config, db session, security, recommendation weights
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic request/response models
│   │   ├── services/     # ai_classifier, embedding, recommendation engine
│   │   └── main.py
│   ├── tests/
│   ├── uploads/          # uploaded search images + seeded demo product photos
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/        # Landing, Search, Results, Catalog, ProductDetail, Favorites, History, Profile, Admin, Auth
│       ├── components/   # Navbar, Footer, ProductCard, States, ProtectedRoute
│       ├── context/      # Auth + Toast providers
│       └── services/     # API client
├── scripts/
│   └── seed_database.py  # generates demo catalog + demo accounts
├── docker-compose.yml
└── .env.example
```

## 5. Setup

### Prerequisites
- Python 3.11+
- Node.js 20+

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env        # already done if you unzipped this project as-is

python ../scripts/seed_database.py   # creates DB, seeds catalog + demo accounts
uvicorn app.main:app --reload --port 8000
```

Backend runs at `http://localhost:8000`. Interactive API docs: `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # already done if present; set VITE_API_BASE_URL if backend isn't on :8000
npm run dev
```

Frontend runs at `http://localhost:5173`.

### Docker (optional)

```bash
docker compose up --build
```

## 6. Database Setup

SQLite is the default — no setup needed, `fashion.db` is created automatically on first run.

To use MySQL instead, edit `backend/.env`:

```
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/fashion_db
```

and add `pymysql` to `requirements.txt` (`pip install pymysql`). Then re-run the seed script.

## 7. AI Model Setup

Default:
```
AI_MODE=demo
```
No setup required — classification and embeddings run immediately using real (deterministic, non-random) pixel analysis, clearly labeled **"Demo AI Mode"** in the UI.

To use a real trained model:
```
AI_MODE=model
MODEL_PATH=./ai_models/clothing_classifier.pt
```
Then implement the model-loading/inference branch inside
`backend/app/services/ai_classifier.py` (`classify_image`, `AI_MODE == "model"` branch) —
it's the single integration point; nothing else in the app needs to change.
The `EmbeddingService` in `backend/app/services/embedding.py` is the equivalent
swap point for a real CNN embedding model.

## 8. Seeding & Demo Accounts

```bash
python scripts/seed_database.py
```

| Role  | Email                  | Password   |
|-------|-------------------------|-----------|
| User  | demo@fashionai.dev      | demo1234  |
| Admin | admin@fashionai.dev     | admin1234 |

**Development-only credentials — change before any real deployment.**

## 9. Testing

```bash
cd backend
pytest
```

Covers: auth flows, product/search validation, and the recommendation engine
(exact-match scoring, mismatched-category penalties, budget filtering, preference
matching, and "best value" never just picking the cheapest item).

## 10. API Documentation

FastAPI auto-generates OpenAPI/Swagger docs at `/docs` and ReDoc at `/redoc` once the backend is running.

## 11. Recommendation Weights

Edit `backend/app/core/recommendation_config.py`:

```python
RECOMMENDATION_WEIGHTS = {
    "visual_similarity": 0.40,
    "category_match": 0.15,
    "color_match": 0.10,
    "style_match": 0.15,
    "pattern_match": 0.05,
    "budget_compatibility": 0.10,
    "user_preference": 0.05,
}
```

Every match score shown in the UI includes a full breakdown and a "Why we recommend this" explanation — never just a bare percentage.

## 12. What's Honest About This Build

- Demo AI Mode is clearly labeled in the UI and is deterministic (same image → same result), not random.
- There is no live marketplace integration; the product catalog is seeded demo data behind a `Product` model/API designed so a real marketplace provider can be added later without touching the frontend.
- No copyrighted datasets, scraped images, or third-party product content are bundled — seeded product photos are generated locally.

## 13. Future Enhancements

- Real trained classifier (EfficientNet/MobileNet) + FAISS for large-scale vector search
- Multi-item "Shop This Look" outfit detection
- Real marketplace provider integrations
- 3D/360° product view component

## License

MIT — for educational/demonstration use.
