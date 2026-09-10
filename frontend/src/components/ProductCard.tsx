import { useMemo, useState } from "react";
import { Heart, ImageOff } from "lucide-react";
import { motion } from "framer-motion";
import type { DestinationType, Product } from "../types";
import { resolveAssetUrl } from "../services/api";
import { resolveShoppingDestination } from "../utils/shopping";

interface Props {
  product: Product;
  matchScore?: number;
  matchLabel?: string;
  isFavorite?: boolean;
  onToggleFavorite?: () => void;
  onClick?: () => void;
  badge?: string;
  storeUrl?: string | null;
  storeName?: string | null;
  destinationType?: DestinationType | string | null;
  storeCta?: string | null;
  storeAvailable?: boolean;
}

export default function ProductCard({
  product,
  matchScore,
  matchLabel,
  isFavorite,
  onToggleFavorite,
  onClick,
  badge,
  storeUrl,
  storeName,
  destinationType,
  storeAvailable,
}: Props) {
  const [imgError, setImgError] = useState(false);
  const hasDiscount = product.discount_price != null && product.discount_price < product.price;

  const destination = useMemo(() => {
    return resolveShoppingDestination(
      product,
      storeUrl,
      storeName,
      destinationType,
      storeAvailable
    );
  }, [product, storeUrl, storeName, destinationType, storeAvailable]);

  return (
    <motion.div
      whileHover={{ y: -4 }}
      className="card group flex cursor-pointer flex-col overflow-hidden"
      onClick={onClick}
    >
      <div className="relative aspect-[4/5] overflow-hidden bg-charcoal-50 dark:bg-charcoal-700">
        {!imgError ? (
          <img
            src={resolveAssetUrl(product.image_url)}
            alt={product.name}
            className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
            loading="eager"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-1.5 text-charcoal-300 dark:text-charcoal-500">
            <ImageOff size={22} />
            <span className="text-[11px] font-medium">Image unavailable</span>
          </div>
        )}
        {badge && (
          <span className="absolute left-3 top-3 rounded-full bg-charcoal-900/90 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-white">
            {badge}
          </span>
        )}
        {onToggleFavorite && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleFavorite();
            }}
            aria-label={isFavorite ? "Remove from favorites" : "Add to favorites"}
            className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-full bg-white/90 shadow-soft transition hover:scale-110"
          >
            <Heart size={15} className={isFavorite ? "fill-rose-500 text-rose-500" : "text-charcoal-500"} />
          </button>
        )}
        {matchScore != null && (
          <div className="absolute bottom-3 left-3 rounded-full bg-white/95 px-3 py-1 text-xs font-semibold text-charcoal-800 shadow-soft">
            {matchScore.toFixed(0)}% {matchLabel || "Match"}
          </div>
        )}
      </div>
      <div className="flex flex-1 flex-col justify-between p-4">
        <div>
          <div className="text-xs uppercase tracking-wide text-charcoal-300">{product.brand || product.platform}</div>
          <h3 className="line-clamp-1 text-sm font-semibold text-charcoal-900 dark:text-white">{product.name}</h3>
          <div className="mt-1 flex items-center gap-2">
            {hasDiscount ? (
              <>
                <span className="text-sm font-bold text-charcoal-900 dark:text-white">
                  ₹{product.discount_price?.toFixed(0)}
                </span>
                <span className="text-xs text-charcoal-300 line-through">₹{product.price.toFixed(0)}</span>
              </>
            ) : (
              <span className="text-sm font-bold text-charcoal-900 dark:text-white">₹{product.price.toFixed(0)}</span>
            )}
          </div>

          <div className="mt-1.5 flex flex-col gap-0.5">
            <div className="text-xs font-medium text-charcoal-600 dark:text-charcoal-300 line-clamp-1">
              {destination.destinationType === "exact_product"
                ? `Available on ${destination.storeName}`
                : destination.destinationType === "official_store"
                ? `Official store · ${destination.storeName}`
                : `Search on ${destination.storeName}`}
            </div>
            <div className="text-[11px] text-charcoal-400 dark:text-charcoal-400 line-clamp-1">
              {destination.explanatoryLabel}
            </div>
          </div>
        </div>

        <a
          href={destination.url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className={`mt-3 inline-flex w-full items-center justify-center gap-1.5 rounded-full py-2 text-xs font-semibold shadow-sm transition hover:shadow ${
            destination.destinationType === "exact_product"
              ? "bg-rose-500 hover:bg-rose-600 text-white"
              : destination.destinationType === "official_store"
              ? "bg-charcoal-900 hover:bg-black text-white dark:bg-rose-600 dark:hover:bg-rose-700"
              : "bg-sand-100 hover:bg-sand-200 text-charcoal-800 border border-charcoal-200/80 dark:bg-charcoal-700 dark:hover:bg-charcoal-600 dark:text-white dark:border-charcoal-600"
          }`}
        >
          {destination.cardCta}
        </a>
      </div>
    </motion.div>
  );
}
