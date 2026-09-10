import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Heart, ExternalLink, ArrowLeft, CheckCircle2, XCircle, Sparkles, ImageOff } from "lucide-react";
import { api, apiErrorMessage, resolveAssetUrl } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import ProductCard from "../components/ProductCard";
import { ErrorState } from "../components/States";
import { isGenuineExternalUrl } from "../utils/url";
import { getDetailCta, getExplanatoryLabel, normalizeDestinationType } from "../utils/shopping";
import type { DestinationType, Product } from "../types";

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
  const [imgError, setImgError] = useState(false);

  useEffect(() => {
    setError("");
    window.scrollTo(0, 0);

    api
      .get(`/products/${id}`)
      .then((res) => {
        setProduct(res.data);
        api
          .get(`/products/${res.data.id}/variants`)
          .then((v) => setVariants(v.data))
          .catch(() => {});
        api
          .get("/products", { params: { category: res.data.category, page_size: 8 } })
          .then((r) => setRelated(r.data.filter((p: Product) => p.id !== res.data.id)))
          .catch(() => {});
      })
      .catch((err) => setError(apiErrorMessage(err, "Product not found.")));

    if (user) {
      api
        .get("/favorites")
        .then((res) => setIsFavorite(res.data.some((p: Product) => p.id === Number(id))))
        .catch(() => {});
    }
  }, [id, user]);

  async function toggleFavorite() {
    if (!user) {
      navigate("/login");
      return;
    }
    if (!product) return;
    try {
      if (isFavorite) {
        await api.delete(`/favorites/${product.id}`);
        setIsFavorite(false);
        push("Removed from favorites", "info");
      } else {
        await api.post(`/favorites/${product.id}`);
        setIsFavorite(true);
        push("Saved to favorites", "success");
      }
    } catch (err) {
      push(apiErrorMessage(err), "error");
    }
  }

  const shoppingDestinations = useMemo(() => {
    if (!product) return [];
    const list: {
      url: string;
      storeName: string;
      destinationType: DestinationType;
      ctaText: string;
      explanatoryLabel: string;
      isExact: boolean;
    }[] = [];

    const seenUrls = new Set<string>();

    // 1. Process all valid external_links
    if (product.external_links && Array.isArray(product.external_links)) {
      for (const link of product.external_links) {
        if (!isGenuineExternalUrl(link.url) || seenUrls.has(link.url)) continue;
        seenUrls.add(link.url);

        const dTypeRaw =
          link.destination_type ||
          (link.verification_status?.toLowerCase() === "verified"
            ? "exact_product"
            : link.verification_status?.toLowerCase() === "official_store"
            ? "official_store"
            : "shopping_search");
        const dType = normalizeDestinationType(dTypeRaw);
        const storeName = link.store_name?.trim() || product.brand || "Store";

        list.push({
          url: link.url,
          storeName,
          destinationType: dType,
          ctaText: getDetailCta(dType),
          explanatoryLabel: getExplanatoryLabel(dType),
          isExact: dType === "exact_product",
        });
      }
    }

    // 2. Fallback to product.product_url if genuine
    if (list.length === 0 && isGenuineExternalUrl(product.product_url) && !seenUrls.has(product.product_url)) {
      seenUrls.add(product.product_url);
      const isGenericPlatform =
        !product.platform ||
        ["deepfashion", "catalog", "demo store", "demostore"].includes(product.platform.toLowerCase());
      const dType: DestinationType = isGenericPlatform ? "exact_product" : "official_store";
      const storeName = isGenericPlatform ? (product.brand || "Store") : product.platform;

      list.push({
        url: product.product_url,
        storeName,
        destinationType: dType,
        ctaText: getDetailCta(dType),
        explanatoryLabel: getExplanatoryLabel(dType),
        isExact: dType === "exact_product",
      });
    }

    // 3. Fallback search destination if no external links exist
    if (list.length === 0) {
      const query = [product.brand, product.color, product.category || product.name || "fashion"]
        .filter(Boolean)
        .join(" ");
      const fallbackUrl = `https://www.google.com/search?tbm=shop&q=${encodeURIComponent(query || "fashion")}`;
      list.push({
        url: fallbackUrl,
        storeName: "Google Shopping",
        destinationType: "fallback_search",
        ctaText: getDetailCta("fallback_search"),
        explanatoryLabel: getExplanatoryLabel("fallback_search"),
        isExact: false,
      });
    }

    return list;
  }, [product]);

  if (error) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-20">
        <ErrorState message={error} />
        <div className="mt-6 text-center">
          <button onClick={() => navigate(-1)} className="btn-secondary">
            <ArrowLeft size={16} /> Go Back
          </button>
        </div>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="mx-auto max-w-7xl px-6 py-20 text-center text-charcoal-400">
        Loading product details...
      </div>
    );
  }

  const hasDiscount = product.discount_price != null && product.discount_price < product.price;

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      {/* Navigation Breadcrumb / Back Button */}
      <div className="mb-6">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-2 text-xs font-semibold text-charcoal-500 hover:text-charcoal-900 dark:text-charcoal-400 dark:hover:text-white transition"
        >
          <ArrowLeft size={15} /> Back to Search / Results
        </button>
      </div>

      <div className="grid gap-10 md:grid-cols-2">
        {/* High-Resolution Product Image */}
        <div className="card overflow-hidden bg-sand-50 p-2 dark:bg-charcoal-800">
          {!imgError ? (
            <img
              src={resolveAssetUrl(product.image_url)}
              alt={product.name}
              className="aspect-[4/5] w-full rounded-2xl object-cover shadow-soft"
              onError={() => setImgError(true)}
            />
          ) : (
            <div className="aspect-[4/5] flex w-full flex-col items-center justify-center gap-2 rounded-2xl bg-sand-100 text-charcoal-400 dark:bg-charcoal-700 dark:text-charcoal-500">
              <ImageOff size={32} />
              <span className="text-xs font-medium">Image unavailable</span>
            </div>
          )}
        </div>

        {/* Product Details & Purchase Actions */}
        <div className="flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase tracking-wider font-semibold text-rose-500">
                {product.brand || product.platform}
              </span>
              <span className="inline-flex items-center gap-1 text-xs font-medium text-charcoal-500 dark:text-charcoal-400">
                {product.availability ? (
                  <>
                    <CheckCircle2 size={13} className="text-green-500" /> In Catalog
                  </>
                ) : (
                  <>
                    <XCircle size={13} className="text-charcoal-400" /> Out of Catalog
                  </>
                )}
              </span>
            </div>

            <h1 className="mt-2 font-display text-3xl font-semibold text-charcoal-900 dark:text-white">
              {product.name}
            </h1>

            <div className="mt-3 flex items-center gap-3">
              {hasDiscount ? (
                <>
                  <span className="text-2xl font-bold text-charcoal-900 dark:text-white">
                    ₹{product.discount_price?.toLocaleString()}
                  </span>
                  <span className="text-lg text-charcoal-300 line-through">
                    ₹{product.price.toLocaleString()}
                  </span>
                  <span className="rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-bold text-rose-600 dark:bg-rose-950/50 dark:text-rose-300">
                    Save ₹{(product.price - product.discount_price!).toLocaleString()}
                  </span>
                </>
              ) : (
                <span className="text-2xl font-bold text-charcoal-900 dark:text-white">
                  ₹{product.price.toLocaleString()}
                </span>
              )}
            </div>

            <p className="mt-4 text-sm leading-relaxed text-charcoal-600 dark:text-charcoal-300">
              {product.description || "High-quality DeepFashion fashion catalog item with verified visual attributes."}
            </p>

            {/* Structured Fashion Attributes */}
            <div className="mt-6 rounded-2xl bg-sand-50/70 p-5 dark:bg-charcoal-700/50">
              <div className="text-xs font-bold uppercase tracking-wider text-charcoal-400 mb-3">
                Garment Attributes
              </div>
              <div className="grid grid-cols-2 gap-x-6 gap-y-3.5 text-sm">
                <Attr label="Category" value={product.category} />
                <Attr label="Subcategory" value={product.subcategory || product.category} />
                <Attr label="Color" value={product.color} />
                <Attr label="Pattern" value={product.pattern} />
                <Attr label="Style" value={product.style} />
                <Attr label="Source / Dataset" value={product.platform} />
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="mt-8 pt-6 border-t border-charcoal-100 dark:border-charcoal-700 space-y-5">
            <div className="flex flex-wrap items-center gap-3">
              <button onClick={toggleFavorite} className="btn-secondary flex-1 sm:flex-none">
                <Heart size={16} className={isFavorite ? "fill-rose-500 text-rose-500" : ""} />
                {isFavorite ? "Saved in Favorites" : "Save to Favorites"}
              </button>
            </div>

            {/* Shopping Destination Actions */}
            {shoppingDestinations.length > 0 && (
              <div className="space-y-3">
                <div className="text-xs font-bold uppercase tracking-wider text-charcoal-500 dark:text-charcoal-400">
                  {shoppingDestinations.some((d) => d.isExact)
                    ? "Available at Verified Retailer:"
                    : "Shop This Style Online:"}
                </div>
                <div className="flex flex-col gap-2.5">
                  {shoppingDestinations.map((dest, idx) => (
                    <div
                      key={`${dest.url}-${idx}`}
                      className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-2xl bg-sand-50/80 border border-charcoal-200/60 dark:bg-charcoal-800/80 dark:border-charcoal-700"
                    >
                      <div>
                        <div className="text-sm font-semibold text-charcoal-900 dark:text-white flex items-center gap-2">
                          <span>{dest.storeName}</span>
                          {dest.destinationType === "exact_product" && (
                            <span className="rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/60 px-2 py-0.5 text-[10px] font-semibold dark:bg-emerald-950/50 dark:text-emerald-300 dark:border-emerald-800">
                              Verified
                            </span>
                          )}
                        </div>
                        <div className="mt-0.5 text-xs text-charcoal-500 dark:text-charcoal-400">
                          {dest.explanatoryLabel}
                        </div>
                      </div>

                      <a
                        href={dest.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-full text-xs font-semibold shadow-sm transition hover:shadow hover:-translate-y-0.5 ${
                          dest.destinationType === "exact_product"
                            ? "bg-rose-500 hover:bg-rose-600 text-white"
                            : dest.destinationType === "official_store"
                            ? "bg-charcoal-900 hover:bg-black text-white dark:bg-rose-600 dark:hover:bg-rose-700"
                            : "bg-white hover:bg-sand-100 text-charcoal-800 border border-charcoal-200 shadow-sm dark:bg-charcoal-700 dark:hover:bg-charcoal-600 dark:text-white dark:border-charcoal-600"
                        }`}
                      >
                        {dest.ctaText} <ExternalLink size={13} />
                      </a>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Available Color Variants */}
      {variants.length > 0 && (
        <section className="mt-16">
          <div className="flex items-center gap-2">
            <Sparkles size={18} className="text-rose-500" />
            <h2 className="font-display text-xl font-semibold text-charcoal-900 dark:text-white">
              Available Color Variants
            </h2>
          </div>
          <div className="mt-5 grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {variants.map((v) => (
              <ProductCard
                key={v.id}
                product={v}
                onClick={() => navigate(`/products/${v.id}`)}
              />
            ))}
          </div>
        </section>
      )}

      {/* Related Products */}
      {related.length > 0 && (
        <section className="mt-16">
          <h2 className="font-display text-xl font-semibold text-charcoal-900 dark:text-white">
            Similar {product.category} Styles
          </h2>
          <div className="mt-5 grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
            {related.slice(0, 4).map((p) => (
              <ProductCard
                key={p.id}
                product={p}
                onClick={() => navigate(`/products/${p.id}`)}
              />
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
      <div className="text-[11px] uppercase tracking-wide text-charcoal-400">{label}</div>
      <div className="font-semibold text-charcoal-800 dark:text-white">{value || "—"}</div>
    </div>
  );
}
