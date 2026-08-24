import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Heart, ExternalLink } from "lucide-react";
import { api, apiErrorMessage, resolveAssetUrl } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import ProductCard from "../components/ProductCard";
import { ErrorState } from "../components/States";
import type { Product } from "../types";

export default function ProductDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { push } = useToast();

  const [product, setProduct] = useState<Product | null>(null);
  const [variants, setVariants] = useState<Product[]>([]);
  const [related, setRelated] = useState<Product[]>([]);
  const [error, setError] = useState("");
  const [isFavorite, setIsFavorite] = useState(false);

  useEffect(() => {
    setError("");
    api.get(`/products/${id}`).then((res) => {
      setProduct(res.data);
      api.get(`/products/${res.data.id}/variants`).then((v) => setVariants(v.data)).catch(() => {});
      api.get("/products", { params: { category: res.data.category, page_size: 8 } })
        .then((r) => setRelated(r.data.filter((p: Product) => p.id !== res.data.id)))
        .catch(() => {});
    }).catch((err) => setError(apiErrorMessage(err, "Product not found.")));

    if (user) {
      api.get("/favorites").then((res) => setIsFavorite(res.data.some((p: Product) => p.id === Number(id)))).catch(() => {});
    }
  }, [id, user]);

  async function toggleFavorite() {
    if (!user) { navigate("/login"); return; }
    if (!product) return;
    try {
      if (isFavorite) {
        await api.delete(`/favorites/${product.id}`);
        setIsFavorite(false);
      } else {
        await api.post(`/favorites/${product.id}`);
        setIsFavorite(true);
      }
    } catch (err) {
      push(apiErrorMessage(err), "error");
    }
  }

  if (error) return <div className="mx-auto max-w-2xl px-6 py-20"><ErrorState message={error} /></div>;
  if (!product) return <div className="mx-auto max-w-7xl px-6 py-20 text-center text-charcoal-400">Loading...</div>;

  const hasDiscount = product.discount_price != null && product.discount_price < product.price;

  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <div className="grid gap-10 md:grid-cols-2">
        <div className="card overflow-hidden">
          <img src={resolveAssetUrl(product.image_url)} alt={product.name} className="aspect-[4/5] w-full object-cover" />
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-charcoal-300">{product.brand}</div>
          <h1 className="mt-1 font-display text-3xl font-semibold text-charcoal-900 dark:text-white">{product.name}</h1>
          <div className="mt-3 flex items-center gap-3">
            {hasDiscount ? (
              <>
                <span className="text-2xl font-bold text-charcoal-900 dark:text-white">₹{product.discount_price?.toFixed(0)}</span>
                <span className="text-lg text-charcoal-300 line-through">₹{product.price.toFixed(0)}</span>
              </>
            ) : (
              <span className="text-2xl font-bold text-charcoal-900 dark:text-white">₹{product.price.toFixed(0)}</span>
            )}
          </div>
          <p className="mt-4 text-sm leading-relaxed text-charcoal-500 dark:text-charcoal-300">{product.description}</p>

          <div className="mt-6 grid grid-cols-2 gap-4 text-sm">
            <Attr label="Color" value={product.color} />
            <Attr label="Style" value={product.style} />
            <Attr label="Pattern" value={product.pattern} />
            <Attr label="Category" value={product.category} />
            <Attr label="Source" value={product.platform} />
            <Attr label="Availability" value={product.availability ? "In Stock" : "Out of Stock"} />
          </div>

          <div className="mt-8 flex gap-3">
            <button onClick={toggleFavorite} className="btn-secondary">
              <Heart size={16} className={isFavorite ? "fill-rose-500 text-rose-500" : ""} /> {isFavorite ? "Saved" : "Save"}
            </button>
            {product.product_url && (
              <a href={product.product_url} target="_blank" rel="noreferrer" className="btn-primary">
                View Product <ExternalLink size={15} />
              </a>
            )}
          </div>
        </div>
      </div>

      {variants.length > 0 && (
        <section className="mt-16">
          <h2 className="font-display text-xl font-semibold text-charcoal-900 dark:text-white">Available Color Variants</h2>
          <div className="mt-5 grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {variants.map((v) => (
              <ProductCard key={v.id} product={v} onClick={() => navigate(`/products/${v.id}`)} />
            ))}
          </div>
        </section>
      )}

      {related.length > 0 && (
        <section className="mt-16">
          <h2 className="font-display text-xl font-semibold text-charcoal-900 dark:text-white">You may also like</h2>
          <div className="mt-5 grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {related.slice(0, 4).map((p) => (
              <ProductCard key={p.id} product={p} onClick={() => navigate(`/products/${p.id}`)} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function Attr({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-charcoal-300">{label}</div>
      <div className="font-semibold text-charcoal-800 dark:text-white">{value}</div>
    </div>
  );
}
