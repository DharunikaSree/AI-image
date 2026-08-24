import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { api, apiErrorMessage } from "../services/api";
import { useToast } from "../context/ToastContext";
import { EmptyState, ErrorState } from "../components/States";
import type { SearchHistoryItem } from "../types";

export default function HistoryPage() {
  const { push } = useToast();
  const [items, setItems] = useState<SearchHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function load() {
    setLoading(true);
    api.get("/history").then((res) => setItems(res.data)).catch((err) => setError(apiErrorMessage(err))).finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function remove(id: number) {
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
              <div key={item.id} className="card flex items-center gap-4 p-4">
                <div className="h-16 w-16 flex-shrink-0 rounded-xl bg-sand-50 dark:bg-charcoal-700" />
                <div className="flex-1">
                  <div className="font-semibold text-charcoal-800 dark:text-white">
                    {item.detected_category} · {item.detected_color} · {item.detected_style}
                  </div>
                  <div className="text-xs text-charcoal-400">
                    {new Date(item.created_at).toLocaleString()} · {item.result_count} results · {item.confidence.toFixed(1)}% confidence
                  </div>
                </div>
                <button onClick={() => remove(item.id)} className="rounded-full p-2 text-charcoal-400 hover:bg-rose-50 hover:text-rose-500" aria-label="Delete search">
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
