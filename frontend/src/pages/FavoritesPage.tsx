import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "../services/api";
import { useToast } from "../context/ToastContext";
import ProductCard from "../components/ProductCard";
import { ProductGridSkeleton, EmptyState, ErrorState } from "../components/States";
import type { Product } from "../types";

export default function FavoritesPage() {
  const navigate = useNavigate();
  const { push } = useToast();
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function load() {
    setLoading(true);
    api.get("/favorites").then((res) => setProducts(res.data)).catch((err) => setError(apiErrorMessage(err))).finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function remove(productId: number) {
    try {
      await api.delete(`/favorites/${productId}`);
      setProducts((p) => p.filter((x) => x.id !== productId));
      push("Removed from favorites", "info");
    } catch (err) {
      push(apiErrorMessage(err), "error");
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-12">
      <h1 className="font-display text-3xl font-semibold text-charcoal-900 dark:text-white">Your Favorites</h1>
      <p className="mt-2 text-charcoal-500 dark:text-charcoal-300">Products you've saved to revisit later.</p>

      <div className="mt-8">
        {loading ? (
          <ProductGridSkeleton />
        ) : error ? (
          <ErrorState message={error} />
        ) : products.length === 0 ? (
          <EmptyState title="No favorites yet." subtitle="Save products from search results or the catalog to see them here." />
        ) : (
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {products.map((p) => (
              <ProductCard key={p.id} product={p} isFavorite onToggleFavorite={() => remove(p.id)} onClick={() => navigate(`/products/${p.id}`)} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
