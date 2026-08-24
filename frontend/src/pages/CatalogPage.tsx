import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "../services/api";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";
import ProductCard from "../components/ProductCard";
import { ProductGridSkeleton, EmptyState, ErrorState } from "../components/States";
import type { Product } from "../types";

const CATEGORIES = ["T-Shirt", "Shirt", "Jeans", "Trousers", "Dress", "Skirt", "Shorts", "Jacket", "Hoodie", "Sweater", "Kurta", "Saree", "Shoes", "Sneakers"];

export default function CatalogPage() {
  const navigate = useNavigate();
  const { push } = useToast();
  const { user } = useAuth();

  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [favorites, setFavorites] = useState<Set<number>>(new Set());

  useEffect(() => {
    setLoading(true);
    api
      .get("/products", { params: category ? { category, page_size: 60 } : { page_size: 60 } })
      .then((res) => setProducts(res.data))
      .catch((err) => setError(apiErrorMessage(err, "Could not load the catalog.")))
      .finally(() => setLoading(false));
  }, [category]);

  useEffect(() => {
    if (!user) return;
    api.get("/favorites").then((res) => setFavorites(new Set(res.data.map((p: Product) => p.id)))).catch(() => {});
  }, [user]);

  async function toggleFavorite(productId: number) {
    if (!user) { navigate("/login"); return; }
    try {
      if (favorites.has(productId)) {
        await api.delete(`/favorites/${productId}`);
        setFavorites((s) => { const n = new Set(s); n.delete(productId); return n; });
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
      <h1 className="font-display text-3xl font-semibold text-charcoal-900 dark:text-white">Explore Styles</h1>
      <p className="mt-2 text-charcoal-500 dark:text-charcoal-300">Browse the full catalog by category.</p>

      <div className="mt-6 flex flex-wrap gap-2">
        <button
          onClick={() => setCategory(null)}
          className={`rounded-full border px-4 py-1.5 text-xs font-semibold transition ${!category ? "border-charcoal-800 bg-charcoal-800 text-white" : "border-charcoal-200 text-charcoal-600 dark:border-charcoal-600 dark:text-charcoal-200"}`}
        >
          All
        </button>
        {CATEGORIES.map((c) => (
          <button
            key={c}
            onClick={() => setCategory(c)}
            className={`rounded-full border px-4 py-1.5 text-xs font-semibold transition ${category === c ? "border-charcoal-800 bg-charcoal-800 text-white" : "border-charcoal-200 text-charcoal-600 dark:border-charcoal-600 dark:text-charcoal-200"}`}
          >
            {c}
          </button>
        ))}
      </div>

      <div className="mt-8">
        {loading ? (
          <ProductGridSkeleton count={12} />
        ) : error ? (
          <ErrorState message={error} />
        ) : products.length === 0 ? (
          <EmptyState title="No products in this category yet." />
        ) : (
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {products.map((p) => (
              <ProductCard key={p.id} product={p} isFavorite={favorites.has(p.id)} onToggleFavorite={() => toggleFavorite(p.id)} onClick={() => navigate(`/products/${p.id}`)} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
