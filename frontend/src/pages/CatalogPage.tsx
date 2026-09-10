import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "../services/api";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";
import ProductCard from "../components/ProductCard";
import { ProductGridSkeleton, EmptyState, ErrorState } from "../components/States";
import type { Product } from "../types";
import { SlidersHorizontal, Sparkles } from "lucide-react";

interface BudgetBucket {
  label: string;
  min: number | null;
  max: number | null;
}

const BUDGET_BUCKETS: BudgetBucket[] = [
  { label: "All Prices", min: null, max: null },
  { label: "Under ₹500", min: null, max: 500 },
  { label: "₹500–₹1,000", min: 500, max: 1000 },
  { label: "₹1,000–₹2,000", min: 1000, max: 2000 },
  { label: "₹2,000+", min: 2000, max: null },
];

const ALL_CATEGORIES = [
  "T-Shirt",
  "Shirt",
  "Jeans",
  "Trousers",
  "Jacket",
  "Hoodie",
  "Sweater",
  "Shorts",
  "Kurta",
  "Dress",
  "Skirt",
  "Saree",
  "Shoes",
  "Sneakers",
];

const MEN_CATEGORIES = [
  "T-Shirt",
  "Shirt",
  "Jeans",
  "Trousers",
  "Jacket",
  "Hoodie",
  "Sweater",
  "Shorts",
  "Kurta",
  "Shoes",
  "Sneakers",
];

const WOMEN_CATEGORIES = [
  "Dress",
  "Saree",
  "Skirt",
  "T-Shirt",
  "Shirt",
  "Jeans",
  "Trousers",
  "Jacket",
  "Hoodie",
  "Sweater",
  "Shorts",
  "Kurta",
  "Shoes",
  "Sneakers",
];

export default function CatalogPage() {
  const navigate = useNavigate();
  const { push } = useToast();
  const { user } = useAuth();

  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [department, setDepartment] = useState<"All" | "Men" | "Women">("All");
  const [category, setCategory] = useState<string | null>(null);
  const [selectedBudget, setSelectedBudget] = useState<BudgetBucket>(BUDGET_BUCKETS[0]);
  const [favorites, setFavorites] = useState<Set<number>>(new Set());

  const categoriesToShow =
    department === "Men"
      ? MEN_CATEGORIES
      : department === "Women"
      ? WOMEN_CATEGORIES
      : ALL_CATEGORIES;

  useEffect(() => {
    setLoading(true);
    setError("");

    const params: Record<string, string | number> = { page_size: 60 };
    if (category) params.category = category;
    if (department !== "All") params.gender = department;
    if (selectedBudget.min !== null) params.min_price = selectedBudget.min;
    if (selectedBudget.max !== null) params.max_price = selectedBudget.max;

    api
      .get("/products", { params })
      .then((res) => setProducts(res.data))
      .catch((err) => setError(apiErrorMessage(err, "Could not load the catalog.")))
      .finally(() => setLoading(false));
  }, [category, department, selectedBudget]);

  useEffect(() => {
    if (!user) return;
    api
      .get("/favorites")
      .then((res) => setFavorites(new Set(res.data.map((p: Product) => p.id))))
      .catch(() => {});
  }, [user]);

  async function toggleFavorite(productId: number) {
    if (!user) {
      navigate("/login");
      return;
    }
    try {
      if (favorites.has(productId)) {
        await api.delete(`/favorites/${productId}`);
        setFavorites((s) => {
          const n = new Set(s);
          n.delete(productId);
          return n;
        });
      } else {
        await api.post(`/favorites/${productId}`);
        setFavorites((s) => new Set(s).add(productId));
      }
    } catch (err) {
      push(apiErrorMessage(err), "error");
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-12">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-600 dark:bg-charcoal-700 dark:text-rose-300">
            <Sparkles size={12} /> Curated Catalog (44,000+ Items)
          </span>
          <h1 className="mt-3 font-display text-3xl font-semibold text-charcoal-900 dark:text-white">
            Explore Styles & Collections
          </h1>
          <p className="mt-1 text-charcoal-500 dark:text-charcoal-300 text-sm">
            Browse Men's, Women's, footwear, and apparel with verified real-time store availability.
          </p>
        </div>

        {/* Department / Gender Switcher Tabs */}
        <div className="flex rounded-2xl bg-sand-100 p-1.5 dark:bg-charcoal-800 w-fit">
          <button
            onClick={() => {
              setDepartment("All");
              setCategory(null);
            }}
            className={`rounded-xl px-4 py-2 text-xs font-semibold transition ${
              department === "All"
                ? "bg-white text-charcoal-900 shadow-sm dark:bg-rose-500 dark:text-white"
                : "text-charcoal-600 hover:text-charcoal-900 dark:text-charcoal-300 dark:hover:text-white"
            }`}
          >
            All Collections
          </button>
          <button
            onClick={() => {
              setDepartment("Men");
              setCategory(null);
            }}
            className={`rounded-xl px-4 py-2 text-xs font-semibold transition ${
              department === "Men"
                ? "bg-white text-charcoal-900 shadow-sm dark:bg-rose-500 dark:text-white"
                : "text-charcoal-600 hover:text-charcoal-900 dark:text-charcoal-300 dark:hover:text-white"
            }`}
          >
            Men's Collection
          </button>
          <button
            onClick={() => {
              setDepartment("Women");
              setCategory(null);
            }}
            className={`rounded-xl px-4 py-2 text-xs font-semibold transition ${
              department === "Women"
                ? "bg-white text-charcoal-900 shadow-sm dark:bg-rose-500 dark:text-white"
                : "text-charcoal-600 hover:text-charcoal-900 dark:text-charcoal-300 dark:hover:text-white"
            }`}
          >
            Women's Collection
          </button>
        </div>
      </div>

      {/* Categories Filter Bar */}
      <div className="mt-8 flex flex-wrap items-center gap-2">
        <button
          onClick={() => setCategory(null)}
          className={`rounded-full border px-4 py-1.5 text-xs font-semibold transition ${
            !category
              ? "border-charcoal-800 bg-charcoal-800 text-white dark:border-rose-500 dark:bg-rose-500"
              : "border-charcoal-200 text-charcoal-600 hover:bg-sand-50 dark:border-charcoal-600 dark:text-charcoal-200 dark:hover:bg-charcoal-700"
          }`}
        >
          All Items
        </button>
        {categoriesToShow.map((c) => (
          <button
            key={c}
            onClick={() => setCategory(c === category ? null : c)}
            className={`rounded-full border px-4 py-1.5 text-xs font-semibold transition ${
              category === c
                ? "border-charcoal-800 bg-charcoal-800 text-white dark:border-rose-500 dark:bg-rose-500"
                : "border-charcoal-200 text-charcoal-600 hover:bg-sand-50 dark:border-charcoal-600 dark:text-charcoal-200 dark:hover:bg-charcoal-700"
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      {/* Price / Budget Filter Bar */}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-charcoal-400 mr-2">
          <SlidersHorizontal size={13} />
          <span>Budget:</span>
        </div>
        {BUDGET_BUCKETS.map((b) => {
          const isSelected = selectedBudget.min === b.min && selectedBudget.max === b.max;
          return (
            <button
              key={b.label}
              onClick={() => setSelectedBudget(b)}
              className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                isSelected
                  ? "bg-sand-200 text-charcoal-900 dark:bg-charcoal-700 dark:text-white"
                  : "bg-sand-50 text-charcoal-600 hover:bg-sand-100 dark:bg-charcoal-800 dark:text-charcoal-300 dark:hover:bg-charcoal-700"
              }`}
            >
              {b.label}
            </button>
          );
        })}
      </div>

      {/* Products Grid */}
      <div className="mt-8">
        {loading ? (
          <ProductGridSkeleton count={12} />
        ) : error ? (
          <ErrorState message={error} />
        ) : products.length === 0 ? (
          <EmptyState
            title={`No products found in ${department !== "All" ? department + "'s" : ""} ${category || "selection"}.`}
            subtitle="Try clearing the category or selecting 'All Prices' to expand your search."
          />
        ) : (
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {products.map((p) => (
              <ProductCard
                key={p.id}
                product={p}
                isFavorite={favorites.has(p.id)}
                onToggleFavorite={() => toggleFavorite(p.id)}
                onClick={() => navigate(`/products/${p.id}`)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
