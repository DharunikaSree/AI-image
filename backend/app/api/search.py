import io
import json
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import rate_limit
from app.models.activity import SearchHistory, SearchResult, Recommendation
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductResponse
from app.schemas.search import (
    DetectedAttributes,
    ImageSearchResponse,
    MultiItemResult,
    MultiItemSearchResponse,
    RecommendedProduct,
    ScoreBreakdown,
    SearchHistoryDetailResponse,
    SearchHistoryItem,
)
from app.services.ai_classifier import classify_image
from app.services.embedding import embedding_service
from app.services.recommendation import rank_products, score_product

router = APIRouter(prefix="/api/search", tags=["search"])
settings = get_settings()

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}


from app.services.shopping_destination_resolver import destination_resolver


def _to_recommended(scored) -> RecommendedProduct:
    prod_resp = ProductResponse.model_validate(scored.product)
    dest = destination_resolver.resolve(prod_resp)

    return RecommendedProduct(
        product=prod_resp,
        scores=ScoreBreakdown(
            visual_score=scored.visual_score,
            category_score=scored.category_score,
            color_score=scored.color_score,
            style_score=scored.style_score,
            pattern_score=scored.pattern_score,
            budget_score=scored.budget_score,
            preference_score=scored.preference_score,
            overall_score=scored.overall_score,
            reasons=scored.reasons,
        ),
        store_name=dest.store_name,
        store_url=dest.store_url,
        store_available=dest.store_available,
        destination_type=dest.destination_type,
        store_cta=dest.store_cta,
    )



def _process_crop(
    contents: bytes,
    filename_hint: str,
    content_type: str | None,
    db: Session,
    current_user: User,
    budget_min: float | None = None,
    budget_max: float | None = None,
):
    ext = Path(filename_hint or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file format. Use JPG, PNG, or WEBP.")

    if content_type and content_type.lower() not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Invalid Content-Type. Expected image/jpeg, image/png, or image/webp.")

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(status_code=400, detail=f"Image exceeds the {settings.MAX_UPLOAD_MB}MB limit.")
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    # Validate image integrity and magic bytes with PIL
    try:
        raw_io = io.BytesIO(contents)
        img = PILImage.open(raw_io)
        img.verify()
        img = PILImage.open(io.BytesIO(contents))
        img_format = (img.format or "").upper()
        if img_format not in {"JPEG", "JPG", "PNG", "WEBP"}:
            raise HTTPException(status_code=400, detail="Corrupted or unrecognized image data.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Corrupted or invalid image file.")

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_ext = ".jpg" if ext in {".jpg", ".jpeg"} else ext
    saved_filename = f"{uuid.uuid4().hex}{safe_ext}"
    image_path = upload_dir / saved_filename
    with open(image_path, "wb") as f:
        f.write(contents)

    try:
        query_embedding = embedding_service.generate_embedding(str(image_path))
        detected = classify_image(str(image_path), embedding=query_embedding)
    except NotImplementedError as e:
        if image_path.exists():
            image_path.unlink()
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        if image_path.exists():
            image_path.unlink()
        raise HTTPException(status_code=422, detail="Could not analyze this image. Try a clearer photo.")

    primary = detected[0]

    # FAISS Sub-Millisecond Vector Retrieval over DeepFashion 44,441 items
    faiss_matches = embedding_service.search_faiss(query_embedding, top_k=80)
    visual_scores_by_id = {pid: score for pid, score in faiss_matches}
    candidate_pids = list(visual_scores_by_id.keys())

    # Determine related categories (e.g. Shoes <-> Sneakers, Jacket <-> Hoodie/Sweater)
    p_cat = (primary.category or "").lower()
    matching_categories = [primary.category]
    if p_cat in ["shoes", "sneakers"]:
        matching_categories = ["Shoes", "Sneakers"]
    elif p_cat in ["jacket", "hoodie", "sweater"]:
        matching_categories = [primary.category, "Jacket", "Hoodie", "Sweater"]
    elif p_cat in ["t-shirt", "shirt"]:
        matching_categories = [primary.category, "Shirt", "T-Shirt"]
    elif p_cat in ["jeans", "trousers"]:
        matching_categories = [primary.category, "Jeans", "Trousers"]

    candidates = []
    if candidate_pids:
        candidates = db.query(Product).filter(Product.id.in_(candidate_pids)).all()

    # If FAISS did not retrieve enough products matching the detected category,
    # enrich the candidate pool with targeted products from the detected category!
    cat_count = sum(1 for p in candidates if (p.category or "").lower() in [c.lower() for c in matching_categories])
    if cat_count < 20:
        existing_ids = {p.id for p in candidates}
        cat_query = db.query(Product).filter(Product.category.in_(matching_categories))
        if existing_ids:
            cat_query = cat_query.filter(~Product.id.in_(existing_ids))
        if primary.gender_category:
            g = primary.gender_category.lower()
            if g in ["men", "boys"]:
                cat_query = cat_query.filter(Product.name.ilike("%Men%") | Product.name.ilike("%Boys%"))
            elif g in ["women", "girls"]:
                cat_query = cat_query.filter(Product.name.ilike("%Women%") | Product.name.ilike("%Girls%"))
        enriched_candidates = cat_query.limit(60).all()
        candidates.extend(enriched_candidates)

    if not candidates:
        candidates = db.query(Product).limit(80).all()

    preferences = current_user.preferences
    preferred_styles = [s for s in (preferences.preferred_styles or "").split(",") if s] if preferences else []
    preferred_colors = [c for c in (preferences.preferred_colors or "").split(",") if c] if preferences else []
    effective_budget_min = budget_min if budget_min is not None else (preferences.budget_min if preferences else None)
    effective_budget_max = budget_max if budget_max is not None else (preferences.budget_max if preferences else None)

    scored_all = [
        score_product(
            p,
            query_embedding,
            primary.category,
            primary.color,
            primary.style,
            primary.pattern,
            effective_budget_min,
            effective_budget_max,
            preferred_styles,
            preferred_colors,
            visual_similarity_score=visual_scores_by_id.get(p.id),
            detected_gender=primary.gender_category,
        )
        for p in candidates
    ]

    # Filter out strict gender mismatches if gender is clearly detected
    if primary.gender_category:
        g = primary.gender_category.lower()
        if g in ["men", "boys"]:
            scored_all = [
                s for s in scored_all 
                if not any(w in (s.product.name or "").lower() for w in ["women", "girls", "ladies"])
            ]
        elif g in ["women", "girls"]:
            scored_all = [
                s for s in scored_all 
                if not any(w in (s.product.name or "").lower().split() for w in ["men", "boys", "gents"])
            ]

    # Prioritize matching category pool for best matches
    matching_cat_pool = [
        s for s in scored_all 
        if (s.product.category or "").lower() in [c.lower() for c in matching_categories]
    ]

    primary_pool = matching_cat_pool if len(matching_cat_pool) >= 4 else scored_all

    if effective_budget_max:
        budget_filtered_pool = [s for s in primary_pool if (s.product.discount_price or s.product.price) <= effective_budget_max]
        best_matches = rank_products(budget_filtered_pool or primary_pool, "best_match")[:8]
        affordable = rank_products(budget_filtered_pool or primary_pool, "best_value")[:8]
    else:
        best_matches = rank_products(primary_pool, "best_match")[:8]
        affordable = rank_products(primary_pool, "best_value")[:8]

    similar_pool = matching_cat_pool if matching_cat_pool else scored_all
    similar_styles = rank_products(similar_pool, "similar_style")[8:16] or rank_products(similar_pool, "similar_style")[:8]

    top_match_product = best_matches[0].product if best_matches else None
    color_variants: list[Product] = []
    if top_match_product and top_match_product.group_key:
        color_variants = (
            db.query(Product)
            .filter(Product.group_key == top_match_product.group_key, Product.id != top_match_product.id)
            .all()
        )

    return primary, detected, best_matches, affordable, similar_styles, color_variants, str(image_path), saved_filename


@router.post(
    "/image",
    response_model=ImageSearchResponse,
    dependencies=[Depends(rate_limit("search"))],
)
async def search_by_image(
    file: UploadFile = File(...),
    budget_min: float | None = None,
    budget_max: float | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contents = await file.read()
    primary, detected, best_matches, affordable, similar_styles, color_variants, image_path, saved_filename = _process_crop(
        contents=contents,
        filename_hint=file.filename or "uploaded.jpg",
        content_type=file.content_type,
        db=db,
        current_user=current_user,
        budget_min=budget_min,
        budget_max=budget_max,
    )

    search = SearchHistory(
        user_id=current_user.id,
        image_path=f"uploads/{saved_filename}",
        detected_category=primary.category,
        detected_style=primary.style,
        detected_color=primary.color,
        confidence=primary.confidence,
        result_count=len(best_matches),
    )
    db.add(search)
    db.flush()

    for rank, s in enumerate(best_matches, start=1):
        db.add(SearchResult(search_id=search.id, product_id=s.product.id, similarity_score=s.visual_score, overall_score=s.overall_score, rank=rank))
        db.add(
            Recommendation(
                search_id=search.id,
                product_id=s.product.id,
                mode="best_match",
                visual_score=s.visual_score,
                category_score=s.category_score,
                color_score=s.color_score,
                style_score=s.style_score,
                pattern_score=s.pattern_score,
                budget_score=s.budget_score,
                preference_score=s.preference_score,
                overall_score=s.overall_score,
                reasons=json.dumps(s.reasons),
            )
        )
    db.commit()

    crop_url = f"/uploads/{saved_filename}"
    primary_item = MultiItemResult(
        item_id=1,
        crop_filename=saved_filename,
        crop_preview_url=crop_url,
        detected_attributes=DetectedAttributes(
            category=primary.category,
            confidence=primary.confidence,
            color=primary.color,
            pattern=primary.pattern,
            style=primary.style,
            sleeve_type=primary.sleeve_type,
            neckline=primary.neckline,
            gender_category=primary.gender_category,
            season=primary.season,
        ),
        best_matches=[_to_recommended(s) for s in best_matches],
        affordable_alternatives=[_to_recommended(s) for s in affordable],
        similar_styles=[_to_recommended(s) for s in similar_styles],
        color_variants=[ProductResponse.model_validate(p) for p in color_variants],
    )

    return ImageSearchResponse(
        search_id=search.id,
        ai_mode=settings.AI_MODE,
        image_path=f"uploads/{saved_filename}",
        query_image_url=crop_url,
        detected_items=[
            DetectedAttributes(
                category=d.category,
                confidence=d.confidence,
                color=d.color,
                pattern=d.pattern,
                style=d.style,
                sleeve_type=d.sleeve_type,
                neckline=d.neckline,
                gender_category=d.gender_category,
                season=d.season,
            )
            for d in detected
        ],
        best_matches=[_to_recommended(s) for s in best_matches],
        affordable_alternatives=[_to_recommended(s) for s in affordable],
        similar_styles=[_to_recommended(s) for s in similar_styles],
        color_variants=[ProductResponse.model_validate(p) for p in color_variants],
        items=[primary_item],
    )


@router.post(
    "/multi-item",
    response_model=MultiItemSearchResponse,
    dependencies=[Depends(rate_limit("search"))],
)
async def search_multi_item(
    files: list[UploadFile] = File(...),
    budget_min: float | None = None,
    budget_max: float | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Shop The Look Multi-Item Fashion Search:
    Processes multiple garment crops independently using preloaded ViT, Multi-Attribute,
    CLIP embeddings, and sub-millisecond FAISS retrieval.
    """
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="No garment crop files provided.")
    if len(files) > 6:
        raise HTTPException(status_code=400, detail="Maximum of 6 garment crops allowed per outfit search.")

    multi_results: list[MultiItemResult] = []
    total_outfit_price = 0.0
    master_search = None

    for idx, f in enumerate(files, start=1):
        contents = await f.read()
        primary, detected, best_matches, affordable, similar_styles, color_variants, img_path, saved_filename = _process_crop(
            contents=contents,
            filename_hint=f.filename or f"crop_{idx}.jpg",
            content_type=f.content_type,
            db=db,
            current_user=current_user,
            budget_min=budget_min,
            budget_max=budget_max,
        )

        crop_url = f"/uploads/{saved_filename}"

        if master_search is None:
            master_search = SearchHistory(
                user_id=current_user.id,
                image_path=f"uploads/{saved_filename}",
                detected_category=f"Outfit ({len(files)} items)",
                detected_style=primary.style,
                detected_color=primary.color,
                confidence=primary.confidence,
                result_count=len(best_matches),
            )
            db.add(master_search)
            db.flush()

        for rank, s in enumerate(best_matches, start=1):
            db.add(SearchResult(search_id=master_search.id, product_id=s.product.id, similarity_score=s.visual_score, overall_score=s.overall_score, rank=rank))

        if best_matches:
            top_p = best_matches[0].product
            total_outfit_price += (top_p.discount_price or top_p.price)

        item_result = MultiItemResult(
            item_id=idx,
            crop_filename=saved_filename,
            crop_preview_url=crop_url,
            detected_attributes=DetectedAttributes(
                category=primary.category,
                confidence=primary.confidence,
                color=primary.color,
                pattern=primary.pattern,
                style=primary.style,
                sleeve_type=primary.sleeve_type,
                neckline=primary.neckline,
                gender_category=primary.gender_category,
                season=primary.season,
            ),
            best_matches=[_to_recommended(s) for s in best_matches],
            affordable_alternatives=[_to_recommended(s) for s in affordable],
            similar_styles=[_to_recommended(s) for s in similar_styles],
            color_variants=[ProductResponse.model_validate(p) for p in color_variants],
        )
        multi_results.append(item_result)

    db.commit()

    first_crop = multi_results[0] if multi_results else None

    return MultiItemSearchResponse(
        search_id=master_search.id if master_search else 0,
        ai_mode=settings.AI_MODE,
        image_path=f"uploads/{first_crop.crop_filename}" if first_crop else None,
        query_image_url=first_crop.crop_preview_url if first_crop else None,
        total_items=len(multi_results),
        items=multi_results,
        outfit_total_price=round(total_outfit_price, 2) if total_outfit_price > 0 else None,
    )


def _rehydrate_search_response(search: SearchHistory, db: Session) -> SearchHistoryDetailResponse:
    recs = db.query(Recommendation).filter(Recommendation.search_id == search.id).all()
    results = db.query(SearchResult).filter(SearchResult.search_id == search.id).order_by(SearchResult.rank.asc()).all()

    rec_pids = [r.product_id for r in recs]
    res_pids = [r.product_id for r in results]
    all_pids = list(dict.fromkeys(rec_pids + res_pids))

    products_by_id: dict[int, Product] = {}
    if all_pids:
        products = db.query(Product).filter(Product.id.in_(all_pids)).all()
        products_by_id = {p.id: p for p in products}

    best_matches: list[RecommendedProduct] = []
    if recs:
        for r in recs:
            if r.mode == "best_match" and r.product_id in products_by_id:
                p = products_by_id[r.product_id]
                prod_resp = ProductResponse.model_validate(p)
                dest = destination_resolver.resolve(prod_resp)
                try:
                    reasons = json.loads(r.reasons) if r.reasons else ["Visual match"]
                except Exception:
                    reasons = ["Visual match"]
                best_matches.append(
                    RecommendedProduct(
                        product=prod_resp,
                        scores=ScoreBreakdown(
                            visual_score=r.visual_score,
                            category_score=r.category_score,
                            color_score=r.color_score,
                            style_score=r.style_score,
                            pattern_score=r.pattern_score,
                            budget_score=r.budget_score,
                            preference_score=r.preference_score,
                            overall_score=r.overall_score,
                            reasons=reasons,
                        ),
                        store_name=dest.store_name,
                        store_url=dest.store_url,
                        store_available=dest.store_available,
                        destination_type=dest.destination_type,
                        store_cta=dest.store_cta,
                    )
                )

    if not best_matches and results:
        for sr in results:
            if sr.product_id in products_by_id:
                p = products_by_id[sr.product_id]
                prod_resp = ProductResponse.model_validate(p)
                dest = destination_resolver.resolve(prod_resp)
                best_matches.append(
                    RecommendedProduct(
                        product=prod_resp,
                        scores=ScoreBreakdown(
                            visual_score=sr.similarity_score,
                            overall_score=sr.overall_score,
                            reasons=["Visual match"],
                        ),
                        store_name=dest.store_name,
                        store_url=dest.store_url,
                        store_available=dest.store_available,
                        destination_type=dest.destination_type,
                        store_cta=dest.store_cta,
                    )
                )

    target_category = search.detected_category or ""
    cat_query = db.query(Product)
    if target_category and not target_category.startswith("Outfit"):
        cat_query = cat_query.filter(Product.category.ilike(f"%{target_category}%"))

    cat_products = cat_query.filter(~Product.id.in_(all_pids) if all_pids else True).limit(40).all()
    if not cat_products and all_pids:
        cat_products = db.query(Product).filter(~Product.id.in_(all_pids)).limit(40).all()

    sorted_by_price = sorted(cat_products, key=lambda p: (p.discount_price or p.price))
    affordable_alternatives: list[RecommendedProduct] = []
    for p in sorted_by_price[:8]:
        prod_resp = ProductResponse.model_validate(p)
        dest = destination_resolver.resolve(prod_resp)
        affordable_alternatives.append(
            RecommendedProduct(
                product=prod_resp,
                scores=ScoreBreakdown(
                    visual_score=75.0,
                    overall_score=80.0,
                    reasons=["Affordable alternative in budget"],
                ),
                store_name=dest.store_name,
                store_url=dest.store_url,
                store_available=dest.store_available,
                destination_type=dest.destination_type,
                store_cta=dest.store_cta,
            )
        )

    similar_styles: list[RecommendedProduct] = []
    for p in cat_products[:8]:
        prod_resp = ProductResponse.model_validate(p)
        dest = destination_resolver.resolve(prod_resp)
        similar_styles.append(
            RecommendedProduct(
                product=prod_resp,
                scores=ScoreBreakdown(
                    visual_score=70.0,
                    overall_score=75.0,
                    reasons=["Similar style match"],
                ),
                store_name=dest.store_name,
                store_url=dest.store_url,
                store_available=dest.store_available,
                destination_type=dest.destination_type,
                store_cta=dest.store_cta,
            )
        )

    color_variants: list[ProductResponse] = []
    if best_matches:
        top_product_id = best_matches[0].product.id
        top_p = products_by_id.get(top_product_id)
        if top_p and top_p.group_key:
            variants = (
                db.query(Product)
                .filter(Product.group_key == top_p.group_key, Product.id != top_p.id)
                .all()
            )
            color_variants = [ProductResponse.model_validate(v) for v in variants]

    detected_attr = DetectedAttributes(
        category=search.detected_category or "Clothing",
        confidence=search.confidence or 90.0,
        color=search.detected_color or "",
        pattern="Solid",
        style=search.detected_style or "",
        sleeve_type=None,
        neckline=None,
        gender_category=None,
        season=None,
    )

    crop_url = f"/{search.image_path}" if search.image_path and not search.image_path.startswith("/") else search.image_path

    primary_item = MultiItemResult(
        item_id=1,
        crop_filename=Path(search.image_path.replace("\\", "/")).name if search.image_path else "",
        crop_preview_url=crop_url,
        detected_attributes=detected_attr,
        best_matches=best_matches,
        affordable_alternatives=affordable_alternatives,
        similar_styles=similar_styles,
        color_variants=color_variants,
    )

    return SearchHistoryDetailResponse(
        id=search.id,
        search_id=search.id,
        ai_mode=settings.AI_MODE,
        image_path=search.image_path,
        query_image_url=crop_url,
        detected_category=search.detected_category,
        detected_style=search.detected_style,
        detected_color=search.detected_color,
        confidence=search.confidence,
        result_count=search.result_count or len(best_matches),
        created_at=search.created_at,
        detected_items=[detected_attr],
        best_matches=best_matches,
        affordable_alternatives=affordable_alternatives,
        similar_styles=similar_styles,
        color_variants=color_variants,
        items=[primary_item],
    )


@router.get("/{search_id}", response_model=SearchHistoryDetailResponse)
def get_search(search_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    search = db.query(SearchHistory).filter(SearchHistory.id == search_id, SearchHistory.user_id == current_user.id).first()
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    return _rehydrate_search_response(search, db)



@router.delete("/{search_id}", status_code=204)
def delete_search(search_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    search = db.query(SearchHistory).filter(SearchHistory.id == search_id, SearchHistory.user_id == current_user.id).first()
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")

    file_to_del: Path | None = None
    image_path_str = search.image_path
    if image_path_str:
        upload_dir = Path(settings.UPLOAD_DIR).resolve()
        filename = Path(image_path_str.replace("\\", "/")).name
        candidate = (upload_dir / filename).resolve()
        if candidate.is_relative_to(upload_dir) and candidate.is_file():
            file_to_del = candidate

    try:
        db.delete(search)
        db.commit()
    except Exception:
        db.rollback()
        raise

    if file_to_del:
        remaining_ref = db.query(SearchHistory).filter(
            SearchHistory.image_path == image_path_str
        ).first()
        if not remaining_ref:
            try:
                file_to_del.unlink()
            except OSError:
                pass
