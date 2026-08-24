import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { Info, Sparkles } from "lucide-react";
import { api, apiErrorMessage } from "../services/api";
import { useToast } from "../context/ToastContext";
import ProductCard from "../components/ProductCard";
import { EmptyState, ErrorState } from "../components/States";
import type { ImageSearchResponse, RecommendedProduct } from "../types";

const BUDGET_BUCKETS = [
  { label: "Under ₹500", max: 500 },
  { label: "₹500–1,000", max: 1000 },
  { label: "₹1,000–2,000", max: 2000 },
  { label: "₹2,000–5,000", max: 5000 },
  { label: "Any budget", max: null as number | null },
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

  const [data, setData] = useState<ImageSearchResponse | null>(null);
  const [error, setError] = useState("");
  const [favorites, setFavorites] = useState<Set<number>>(new Set());
  const [budgetFilter, setBudgetFilter] = useState<number | null>(null);
  const [showExplain, setShowExplain] = useState<number | null>(null);

  useEffect(() => {
    const cached = sessionStorage.getItem(`search_result_${searchId}`);
    if (cached) {
      setData(JSON.parse(cached));
    } else {
      setError("Results for this search are no longer available. Try a new search.");
    }
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

  const filteredAffordable = useMemo(() => {
    if (!data) return [];
    if (budgetFilter == null) return data.affordable_alternatives;
    return data.affordable_alternatives.filter((r) => (r.product.discount_price ?? r.product.price) <= budgetFilter!);
  }, [data, budgetFilter]);

  if (error) return <div className="mx-auto max-w-2xl px-6 py-20"><ErrorState message={error} /></div>;
  if (!data) return <div className="mx-auto max-w-7xl px-6 py-20 text-center text-charcoal-400">Loading results...</div>;

  const primary = data.detected_items[0];

  return (
    <div className="mx-auto max-w-7xl px-6 py-12">
      {data.ai_mode === "demo" && (
        <div className="mb-8 flex items-center gap-2 rounded-full bg-charcoal-900 px-4 py-2 text-xs font-semibold text-white w-fit">
          <Info size={13} /> Demo AI Mode — deterministic heuristic analysis, not a trained neural network
        </div>
      )}

      {/* Detected items */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="card grid gap-8 p-8 md:grid-cols-[auto,1fr]">
        <div className="mx-auto flex h-48 w-40 items-center justify-center rounded-2xl bg-sand-50 text-charcoal-300 dark:bg-charcoal-700">
          <Sparkles size={28} />
        </div>
        <div>
          <h1 className="font-display text-2xl font-semibold text-charcoal-900 dark:text-white">Detected: {primary.category}</h1>
          <p className="text-sm text-charcoal-400">Confidence: {primary.confidence.toFixed(1)}%</p>
          <div className="mt-5 grid grid-cols-2 gap-x-8 gap-y-3 sm:grid-cols-3">
            <Attribute label="Color" value={primary.color} />
            <Attribute label="Pattern" value={primary.pattern} />
            <Attribute label="Style" value={primary.style} />
            <Attribute label="Sleeve" value={primary.sleeve_type} />
            <Attribute label="Neckline" value={primary.neckline} />
            <Attribute label="Gender" value={primary.gender_category} />
            <Attribute label="Season" value={primary.season} />
          </div>
        </div>
      </motion.div>

      {/* Best matches */}
      <Section title="Closest Matches" subtitle="Ranked by visual, category, color and style similarity.">
        {data.best_matches.length === 0 ? (
          <EmptyState title="No matching styles found." subtitle="Try a clearer photo or a different angle." />
        ) : (
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {data.best_matches.map((r) => (
              <div key={r.product.id}>
                <ProductCard
                  product={r.product}
                  matchScore={r.scores.overall_score}
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
      <Section title="Affordable Alternatives" subtitle="Similar looks, ranked by value — not just price.">
        <div className="mb-5 flex flex-wrap gap-2">
          {BUDGET_BUCKETS.map((b) => (
            <button
              key={b.label}
              onClick={() => setBudgetFilter(b.max)}
              className={`rounded-full border px-4 py-1.5 text-xs font-semibold transition ${
                budgetFilter === b.max
                  ? "border-charcoal-800 bg-charcoal-800 text-white"
                  : "border-charcoal-200 text-charcoal-600 hover:border-charcoal-400 dark:border-charcoal-600 dark:text-charcoal-200"
              }`}
            >
              {b.label}
            </button>
          ))}
        </div>
        {filteredAffordable.length === 0 ? (
          <EmptyState title="No options in this budget yet." subtitle="Try a wider budget range." />
        ) : (
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {filteredAffordable.map((r, i) => (
              <ProductCard
                key={r.product.id}
                product={r.product}
                matchScore={r.scores.overall_score}
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
      {data.color_variants.length > 0 && (
        <Section title="Available Color Variants" subtitle="The same piece, in other shades.">
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {data.color_variants.map((p) => (
              <ProductCard key={p.id} product={p} isFavorite={favorites.has(p.id)} onToggleFavorite={() => toggleFavorite(p.id)} onClick={() => navigate(`/products/${p.id}`)} />
            ))}
          </div>
        </Section>
      )}

      {/* Similar styles */}
      <Section title="Similar Styles You May Like" subtitle="Not identical — just a great stylistic fit.">
        {data.similar_styles.length === 0 ? (
          <EmptyState title="No similar styles found." />
        ) : (
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {data.similar_styles.map((r) => (
              <ProductCard
                key={r.product.id}
                product={r.product}
                matchScore={r.scores.overall_score}
                matchLabel="Style Match"
                isFavorite={favorites.has(r.product.id)}
                onToggleFavorite={() => toggleFavorite(r.product.id)}
                onClick={() => navigate(`/products/${r.product.id}`)}
              />
            ))}
          </div>
        )}
      </Section>
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
