import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { Info, Sparkles, Layers, Tag, SlidersHorizontal } from "lucide-react";
import { api, apiErrorMessage, resolveAssetUrl } from "../services/api";
import { useToast } from "../context/ToastContext";
import ProductCard from "../components/ProductCard";
import { EmptyState, ErrorState } from "../components/States";
import type { ImageSearchResponse, MultiItemResult, RecommendedProduct } from "../types";

export interface BudgetBucket {
  label: string;
  min: number | null;
  max: number | null;
}

const BUDGET_BUCKETS: BudgetBucket[] = [
  { label: "All Prices", min: null, max: null },
  { label: "Under ₹500", min: null, max: 500 },
  { label: "₹500–₹1,000", min: 500, max: 1000 },
  { label: "₹1,000–₹2,000", min: 1000, max: 2000 },
  { label: "₹2,000–₹5,000", min: 2000, max: 5000 },
  { label: "₹5,000+", min: 5000, max: null },
];

function ScoreExplanation({ item }: { item: RecommendedProduct }) {
  return (
    <div className="mt-1 flex flex-wrap gap-1.5">
      {item.scores.reasons.map((r) => (
        <span key={r} className="rounded-full bg-sand-50 px-2.5 py-1 text-[11px] font-medium text-charcoal-600 dark:bg-charcoal-700 dark:text-charcoal-200">
          ✓ {r}
        </span>
      ))}
    </div>
  );
}

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section className="mt-14">
      <h2 className="font-display text-2xl font-semibold text-charcoal-900 dark:text-white">{title}</h2>
      {subtitle && <p className="mt-1 text-sm text-charcoal-400">{subtitle}</p>}
      <div className="mt-6">{children}</div>
    </section>
  );
}

export default function ResultsPage() {
  const { searchId } = useParams();
  const navigate = useNavigate();
  const { push } = useToast();

  const [data, setData] = useState<(ImageSearchResponse & { query_image_url?: string; crop_previews?: { label: string; previewUrl: string }[] }) | null>(null);
  const [queryImageUrl, setQueryImageUrl] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [favorites, setFavorites] = useState<Set<number>>(new Set());
  const [selectedBudget, setSelectedBudget] = useState<BudgetBucket | null>(null);
  const [showExplain, setShowExplain] = useState<number | null>(null);
  const [activeItemIndex, setActiveItemIndex] = useState<number>(0);
  const [activeImageError, setActiveImageError] = useState<boolean>(false);

  useEffect(() => {
    setActiveImageError(false);
  }, [activeItemIndex]);

  useEffect(() => {
    const cached = sessionStorage.getItem(`search_result_${searchId}`);
    const cachedImg = sessionStorage.getItem(`search_image_${searchId}`);

    if (cached) {
      const parsed = JSON.parse(cached);
      setData(parsed);
      if (parsed.query_image_url) {
        setQueryImageUrl(parsed.query_image_url);
      } else if (cachedImg) {
        setQueryImageUrl(cachedImg);
      }
      if (parsed.budget_max) {
        const matchingBucket = BUDGET_BUCKETS.find((b) => b.max === parsed.budget_max && b.min === null);
        if (matchingBucket) {
          setSelectedBudget(matchingBucket);
        } else {
          setSelectedBudget({ label: `Under ₹${parsed.budget_max}`, min: null, max: parsed.budget_max });
        }
      }
    }

    // Retrieve backend search history to obtain server-persisted image path
    api.get(`/search/${searchId}`)
      .then((res) => {
        if (res.data?.image_path) {
          const resolved = resolveAssetUrl(res.data.image_path);
          setQueryImageUrl(resolved);
        }
      })
      .catch(() => {
        if (!cached) {
          setError("Results for this search are no longer available. Try a new search.");
        }
      });

    api.get("/favorites").then((res) => setFavorites(new Set(res.data.map((p: any) => p.id)))).catch(() => {});
  }, [searchId]);

  async function toggleFavorite(productId: number) {
    try {
      if (favorites.has(productId)) {
        await api.delete(`/favorites/${productId}`);
        setFavorites((s) => { const n = new Set(s); n.delete(productId); return n; });
        push("Removed from favorites", "info");
      } else {
        await api.post(`/favorites/${productId}`);
        setFavorites((s) => new Set(s).add(productId));
        push("Saved to favorites", "success");
      }
    } catch (err) {
      push(apiErrorMessage(err), "error");
    }
  }

  const isMultiItem = data?.items && data.items.length > 1;
  const currentItem: MultiItemResult | null = isMultiItem
    ? data!.items![Math.min(activeItemIndex, data!.items!.length - 1)]
    : data?.items?.[0] || null;

  const currentGarmentImageUrl = useMemo(() => {
    const item = currentItem || data?.items?.[activeItemIndex] || data?.items?.[0];
    if (item?.crop_preview_url) {
      return resolveAssetUrl(item.crop_preview_url);
    }
    if (item?.crop_filename) {
      return resolveAssetUrl(`/uploads/${item.crop_filename}`);
    }
    const cropPrev = data?.crop_previews?.[activeItemIndex]?.previewUrl;
    if (cropPrev && !cropPrev.startsWith("blob:")) {
      return resolveAssetUrl(cropPrev);
    }
    if (queryImageUrl && !queryImageUrl.startsWith("blob:")) {
      return resolveAssetUrl(queryImageUrl);
    }
    if (data?.query_image_url && !data.query_image_url.startsWith("blob:")) {
      return resolveAssetUrl(data.query_image_url);
    }
    return cropPrev || queryImageUrl || data?.query_image_url || null;
  }, [currentItem, data, activeItemIndex, queryImageUrl]);

  const activeDetected = currentItem ? currentItem.detected_attributes : data?.detected_items[0];
  const activeBestMatches = currentItem ? currentItem.best_matches : data?.best_matches || [];
  const activeAffordable = currentItem ? currentItem.affordable_alternatives : data?.affordable_alternatives || [];
  const activeSimilar = currentItem ? currentItem.similar_styles : data?.similar_styles || [];
  const activeVariants = currentItem ? currentItem.color_variants : data?.color_variants || [];

  const filteredBestMatches = useMemo(() => {
    if (!selectedBudget || (selectedBudget.min === null && selectedBudget.max === null)) {
      return activeBestMatches;
    }
    return activeBestMatches.filter((r) => {
      const price = r.product.discount_price ?? r.product.price;
      if (selectedBudget.min !== null && price < selectedBudget.min) return false;
      if (selectedBudget.max !== null && price > selectedBudget.max) return false;
      return true;
    });
  }, [activeBestMatches, selectedBudget]);

  const filteredAffordable = useMemo(() => {
    if (!selectedBudget || (selectedBudget.min === null && selectedBudget.max === null)) {
      return activeAffordable;
    }
    return activeAffordable.filter((r) => {
      const price = r.product.discount_price ?? r.product.price;
      if (selectedBudget.min !== null && price < selectedBudget.min) return false;
      if (selectedBudget.max !== null && price > selectedBudget.max) return false;
      return true;
    });
  }, [activeAffordable, selectedBudget]);

  if (error) return <div className="mx-auto max-w-2xl px-6 py-20"><ErrorState message={error} /></div>;
  if (!data || !activeDetected) return <div className="mx-auto max-w-7xl px-6 py-20 text-center text-charcoal-400">Loading results...</div>;

  return (
    <div className="mx-auto max-w-7xl px-6 py-12">
      {data.ai_mode === "demo" && (
        <div className="mb-8 flex items-center gap-2 rounded-full bg-charcoal-900 px-4 py-2 text-xs font-semibold text-white w-fit">
          <Info size={13} /> Demo AI Mode — deterministic heuristic analysis, not a trained neural network
        </div>
      )}

      {/* Multi-Item / Shop The Look Header Tabs */}
      {isMultiItem && (
        <div className="mb-8 rounded-3xl bg-sand-50 p-6 dark:bg-charcoal-800">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-charcoal-200 dark:border-charcoal-700">
            <div className="flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-rose-500 text-white">
                <Layers size={18} />
              </span>
              <div>
                <h2 className="font-display text-xl font-semibold text-charcoal-900 dark:text-white">
                  Shop The Look — {data.items!.length} Outfit Garments Detected
                </h2>
                <p className="text-xs text-charcoal-500 dark:text-charcoal-400">
                  Select a garment below to explore visual matches and recommendations.
                </p>
              </div>
            </div>

            {data.outfit_total_price && (
              <div className="flex items-center gap-2 rounded-2xl bg-white px-4 py-2 text-xs font-semibold text-charcoal-900 shadow-sm dark:bg-charcoal-900 dark:text-white w-fit">
                <Tag size={14} className="text-rose-500" />
                <span>Complete Outfit Total:</span>
                <span className="text-rose-600 dark:text-rose-400 font-bold">₹{data.outfit_total_price.toLocaleString()}</span>
              </div>
            )}
          </div>

          {/* Garment Selector Tabs */}
          <div className="mt-4 flex flex-wrap gap-2.5">
            {data.items!.map((item, idx) => {
              const isActive = idx === activeItemIndex;
              const cropThumb =
                item.crop_preview_url
                  ? resolveAssetUrl(item.crop_preview_url)
                  : item.crop_filename
                  ? resolveAssetUrl(`/uploads/${item.crop_filename}`)
                  : data.crop_previews?.[idx]?.previewUrl;
              return (
                <button
                  key={item.item_id}
                  onClick={() => {
                    setActiveItemIndex(idx);
                    setActiveImageError(false);
                  }}
                  className={`flex items-center gap-2.5 rounded-2xl px-4 py-2.5 text-xs font-semibold transition ${
                    isActive
                      ? "bg-rose-500 text-white shadow-md"
                      : "bg-white text-charcoal-700 hover:bg-sand-100 dark:bg-charcoal-900 dark:text-charcoal-200 dark:hover:bg-charcoal-700"
                  }`}
                >
                  {cropThumb && (
                    <img
                      src={cropThumb}
                      alt={item.detected_attributes.category}
                      className="h-6 w-6 rounded-md object-cover"
                      onError={(e) => {
                        (e.target as HTMLElement).style.display = "none";
                      }}
                    />
                  )}
                  <span>Garment {idx + 1}: {item.detected_attributes.category}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] ${isActive ? "bg-white/20 text-white" : "bg-sand-100 text-charcoal-500 dark:bg-charcoal-800 dark:text-charcoal-400"}`}>
                    {item.detected_attributes.color}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Detected items */}
      <motion.div
        key={activeItemIndex}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="card grid gap-8 p-8 md:grid-cols-[auto,1fr]"
      >
        <div className="mx-auto flex h-48 w-40 items-center justify-center overflow-hidden rounded-2xl bg-sand-50 shadow-soft dark:bg-charcoal-700">
          {!activeImageError && currentGarmentImageUrl ? (
            <img
              src={currentGarmentImageUrl}
              alt={activeDetected.category || "Uploaded garment"}
              className="h-full w-full object-cover"
              onError={() => setActiveImageError(true)}
            />
          ) : (
            <div className="flex flex-col items-center justify-center gap-2 p-3 text-center text-charcoal-400 dark:text-charcoal-300">
              <Sparkles size={28} className="text-rose-500" />
              <span className="text-xs font-semibold">{activeDetected.category || "Garment"}</span>
            </div>
          )}
        </div>
        <div>
          <h1 className="font-display text-2xl font-semibold text-charcoal-900 dark:text-white">
            Detected: {activeDetected.category}
          </h1>
          <p className="text-sm text-charcoal-400">Confidence: {activeDetected.confidence.toFixed(1)}%</p>
          <div className="mt-5 grid grid-cols-2 gap-x-8 gap-y-3 sm:grid-cols-3">
            <Attribute label="Color" value={activeDetected.color} />
            <Attribute label="Pattern" value={activeDetected.pattern} />
            <Attribute label="Style" value={activeDetected.style} />
            <Attribute label="Sleeve" value={activeDetected.sleeve_type} />
            <Attribute label="Neckline" value={activeDetected.neckline} />
            <Attribute label="Gender" value={activeDetected.gender_category} />
            <Attribute label="Season" value={activeDetected.season} />
          </div>
        </div>
      </motion.div>

      {/* Price / Budget Filter Bar */}
      <div className="mt-8 rounded-2xl bg-sand-50 p-5 dark:bg-charcoal-800 border border-charcoal-200/60 dark:border-charcoal-700">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-charcoal-700 dark:text-charcoal-200">
            <SlidersHorizontal size={15} className="text-rose-500" />
            <span>Filter All Matches by Budget:</span>
            {selectedBudget && (selectedBudget.min !== null || selectedBudget.max !== null) && (
              <span className="rounded-full bg-rose-100 px-2.5 py-0.5 text-[11px] font-bold text-rose-700 dark:bg-rose-900/50 dark:text-rose-300">
                {selectedBudget.label}
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {BUDGET_BUCKETS.map((b) => {
              const isSelected = selectedBudget
                ? selectedBudget.min === b.min && selectedBudget.max === b.max
                : b.min === null && b.max === null;
              return (
                <button
                  key={b.label}
                  onClick={() => setSelectedBudget(b.min === null && b.max === null ? null : b)}
                  className={`rounded-full px-3.5 py-1.5 text-xs font-semibold transition ${
                    isSelected
                      ? "bg-charcoal-900 text-white shadow-sm dark:bg-rose-500 dark:text-white"
                      : "bg-white text-charcoal-600 hover:bg-sand-100 dark:bg-charcoal-700 dark:text-charcoal-200 dark:hover:bg-charcoal-600"
                  }`}
                >
                  {b.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Best matches */}
      <Section
        title={isMultiItem ? `Closest Matches for ${activeDetected.category}` : "Closest Matches"}
        subtitle={selectedBudget && (selectedBudget.min !== null || selectedBudget.max !== null) ? `Filtered by ${selectedBudget.label}` : "Ranked by visual, category, color and style similarity."}
      >
        {filteredBestMatches.length === 0 ? (
          <EmptyState title="No matching styles found in this price range." subtitle="Try selecting 'All Prices' or a wider budget range." />
        ) : (
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {filteredBestMatches.map((r) => (
              <div key={r.product.id}>
                <ProductCard
                  product={r.product}
                  matchScore={r.scores.overall_score}
                  storeUrl={r.store_url}
                  storeName={r.store_name}
                  destinationType={r.destination_type}
                  storeCta={r.store_cta}
                  storeAvailable={r.store_available}
                  isFavorite={favorites.has(r.product.id)}
                  onToggleFavorite={() => toggleFavorite(r.product.id)}
                  onClick={() => navigate(`/products/${r.product.id}`)}
                />
                <button
                  onClick={() => setShowExplain(showExplain === r.product.id ? null : r.product.id)}
                  className="mt-2 text-xs font-semibold text-charcoal-400 hover:text-rose-500"
                >
                  {showExplain === r.product.id ? "Hide" : "Why we recommend this"}
                </button>
                {showExplain === r.product.id && <ScoreExplanation item={r} />}
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Affordable alternatives */}
      <Section
        title={isMultiItem ? `Affordable ${activeDetected.category} Alternatives` : "Affordable Alternatives"}
        subtitle="Similar looks, ranked by value — not just price."
      >
        {filteredAffordable.length === 0 ? (
          <EmptyState title="No affordable options in this budget yet." subtitle="Try selecting 'All Prices' or a wider budget range." />
        ) : (
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {filteredAffordable.map((r, i) => (
              <ProductCard
                key={r.product.id}
                product={r.product}
                matchScore={r.scores.overall_score}
                storeUrl={r.store_url}
                storeName={r.store_name}
                destinationType={r.destination_type}
                storeCta={r.store_cta}
                storeAvailable={r.store_available}
                badge={i === 0 ? "Best Value" : undefined}
                isFavorite={favorites.has(r.product.id)}
                onToggleFavorite={() => toggleFavorite(r.product.id)}
                onClick={() => navigate(`/products/${r.product.id}`)}
              />
            ))}
          </div>
        )}
      </Section>

      {/* Color variants */}
      {activeVariants.length > 0 && (
        <Section title="Available Color Variants" subtitle="The same piece, in other shades.">
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {activeVariants.map((p) => (
              <ProductCard key={p.id} product={p} isFavorite={favorites.has(p.id)} onToggleFavorite={() => toggleFavorite(p.id)} onClick={() => navigate(`/products/${p.id}`)} />
            ))}
          </div>
        </Section>
      )}

      {/* Similar styles */}
      {activeSimilar.length > 0 && (
        <Section title="Similar Styles You May Like" subtitle="Not identical — just a great stylistic fit.">
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {activeSimilar.map((r) => (
              <ProductCard
                key={r.product.id}
                product={r.product}
                matchScore={r.scores.overall_score}
                matchLabel="Style Match"
                storeUrl={r.store_url}
                storeName={r.store_name}
                destinationType={r.destination_type}
                storeCta={r.store_cta}
                storeAvailable={r.store_available}
                isFavorite={favorites.has(r.product.id)}
                onToggleFavorite={() => toggleFavorite(r.product.id)}
                onClick={() => navigate(`/products/${r.product.id}`)}
              />
            ))}
          </div>
        </Section>
      )}

      {/* Complete Outfit Look Ensemble */}
      {data.outfit && data.outfit.length > 0 && (
        <Section title="Complete The Look Ensemble" subtitle="Coordinated garments recommended to complete the full look.">
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {data.outfit.map((r) => (
              <ProductCard
                key={r.product.id}
                product={r.product}
                matchScore={r.scores.overall_score}
                matchLabel="Outfit Piece"
                storeUrl={r.store_url}
                storeName={r.store_name}
                destinationType={r.destination_type}
                storeCta={r.store_cta}
                storeAvailable={r.store_available}
                isFavorite={favorites.has(r.product.id)}
                onToggleFavorite={() => toggleFavorite(r.product.id)}
                onClick={() => navigate(`/products/${r.product.id}`)}
              />
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

function Attribute({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-charcoal-300">{label}</div>
      <div className="text-sm font-semibold text-charcoal-800 dark:text-white">{value || "Not detected"}</div>
    </div>
  );
}
