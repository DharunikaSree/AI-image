import { Heart, ExternalLink } from "lucide-react";
import { motion } from "framer-motion";
import type { Product } from "../types";
import { resolveAssetUrl } from "../services/api";

interface Props {
  product: Product;
  matchScore?: number;
  matchLabel?: string;
  isFavorite?: boolean;
  onToggleFavorite?: () => void;
  onClick?: () => void;
  badge?: string;
}

export default function ProductCard({ product, matchScore, matchLabel, isFavorite, onToggleFavorite, onClick, badge }: Props) {
  const hasDiscount = product.discount_price != null && product.discount_price < product.price;

  return (
    <motion.div
      whileHover={{ y: -4 }}
      className="card group flex cursor-pointer flex-col overflow-hidden"
      onClick={onClick}
    >
      <div className="relative aspect-[4/5] overflow-hidden bg-charcoal-50 dark:bg-charcoal-700">
        <img
          src={resolveAssetUrl(product.image_url)}
          alt={product.name}
          className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
          loading="lazy"
        />
        {badge && (
          <span className="absolute left-3 top-3 rounded-full bg-charcoal-900/90 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-white">
            {badge}
          </span>
        )}
        {onToggleFavorite && (
          <button
            onClick={(e) => { e.stopPropagation(); onToggleFavorite(); }}
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
      <div className="flex flex-1 flex-col gap-1 p-4">
        <div className="text-xs uppercase tracking-wide text-charcoal-300">{product.brand || product.platform}</div>
        <h3 className="line-clamp-1 text-sm font-semibold text-charcoal-900 dark:text-white">{product.name}</h3>
        <div className="mt-1 flex items-center gap-2">
          {hasDiscount ? (
            <>
              <span className="text-sm font-bold text-charcoal-900 dark:text-white">₹{product.discount_price?.toFixed(0)}</span>
              <span className="text-xs text-charcoal-300 line-through">₹{product.price.toFixed(0)}</span>
            </>
          ) : (
            <span className="text-sm font-bold text-charcoal-900 dark:text-white">₹{product.price.toFixed(0)}</span>
          )}
        </div>
        <div className="mt-1 text-xs text-charcoal-400">Available on {product.platform}</div>
        {product.product_url && (
          <a
            href={product.product_url}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="mt-3 inline-flex items-center justify-center gap-1.5 rounded-full border border-charcoal-200 py-2 text-xs font-semibold text-charcoal-700 transition hover:border-charcoal-400 dark:border-charcoal-600 dark:text-white"
          >
            View Product <ExternalLink size={12} />
          </a>
        )}
      </div>
    </motion.div>
  );
}
