import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Trash2, ExternalLink, Sparkles } from "lucide-react";
import { api, apiErrorMessage, resolveAssetUrl } from "../services/api";
import { useToast } from "../context/ToastContext";
import { EmptyState, ErrorState } from "../components/States";
import type { SearchHistoryItem } from "../types";

export default function HistoryPage() {
  const navigate = useNavigate();
  const { push } = useToast();
  const [items, setItems] = useState<SearchHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function load() {
    setLoading(true);
    api.get("/history").then((res) => setItems(res.data)).catch((err) => setError(apiErrorMessage(err))).finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function remove(e: React.MouseEvent, id: number) {
    e.stopPropagation();
    try {
      await api.delete(`/history/${id}`);
      setItems((it) => it.filter((x) => x.id !== id));
      push("Search removed from history", "info");
    } catch (err) {
      push(apiErrorMessage(err), "error");
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <h1 className="font-display text-3xl font-semibold text-charcoal-900 dark:text-white">Search History</h1>
      <p className="mt-2 text-charcoal-500 dark:text-charcoal-300">Your previous image searches.</p>

      <div className="mt-8">
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => <div key={i} className="skeleton h-20 w-full" />)}
          </div>
        ) : error ? (
          <ErrorState message={error} />
        ) : items.length === 0 ? (
          <EmptyState title="No searches yet." subtitle="Search by image to build your history." />
        ) : (
          <div className="space-y-3">
            {items.map((item) => (
              <div
                key={item.id}
                onClick={() => navigate(`/results/${item.id}`)}
                className="card flex cursor-pointer items-center gap-4 p-4 transition hover:border-charcoal-400 hover:shadow-soft dark:hover:border-charcoal-500"
              >
                <div className="h-16 w-16 flex-shrink-0 overflow-hidden rounded-xl bg-sand-50 dark:bg-charcoal-700 flex items-center justify-center">
                  {item.image_path ? (
                    <img
                      src={resolveAssetUrl(item.image_path)}
                      alt={item.detected_category}
                      className="h-full w-full object-cover"
                      onError={(e) => {
                        (e.target as HTMLElement).style.display = "none";
                      }}
                    />
                  ) : (
                    <Sparkles size={20} className="text-charcoal-300" />
                  )}
                </div>
                <div className="flex-1">
                  <div className="font-semibold text-charcoal-800 dark:text-white flex items-center gap-2">
                    {item.detected_category} · {item.detected_color} · {item.detected_style}
                    <ExternalLink size={13} className="text-charcoal-400 opacity-0 group-hover:opacity-100" />
                  </div>
                  <div className="text-xs text-charcoal-400">
                    {new Date(item.created_at).toLocaleString()} · {item.result_count} results · {item.confidence.toFixed(1)}% confidence
                  </div>
                </div>
                <button
                  onClick={(e) => remove(e, item.id)}
                  className="rounded-full p-2 text-charcoal-400 hover:bg-rose-50 hover:text-rose-500 transition"
                  aria-label="Delete search"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
