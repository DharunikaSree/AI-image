import { useEffect, useState } from "react";
import { api, apiErrorMessage } from "../services/api";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";
import type { Preferences } from "../types";

const STYLES = ["Casual", "Formal", "Streetwear", "Party", "Traditional", "Minimal", "Sporty", "Vintage"];
const COLORS = ["Black", "White", "Beige", "Gray", "Navy", "Blue", "Red", "Burgundy", "Green", "Olive", "Pink", "Brown"];
const CATEGORIES = ["Shirts", "T-Shirts", "Dresses", "Jeans", "Jackets", "Shoes", "Sarees", "Kurtas"];

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

export default function ProfilePage() {
  const { user } = useAuth();
  const { push } = useToast();
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/profile").then((res) => setPrefs(res.data)).catch((err) => push(apiErrorMessage(err), "error"));
  }, []);

  async function save() {
    if (!prefs) return;
    setSaving(true);
    try {
      await api.put("/profile", prefs);
      push("Preferences saved", "success");
    } catch (err) {
      push(apiErrorMessage(err), "error");
    } finally {
      setSaving(false);
    }
  }

  if (!prefs) return <div className="mx-auto max-w-3xl px-6 py-20 text-center text-charcoal-400">Loading...</div>;

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="font-display text-3xl font-semibold text-charcoal-900 dark:text-white">Your Profile</h1>
      <p className="mt-2 text-charcoal-500 dark:text-charcoal-300">{user?.name} · {user?.email}</p>

      <div className="card mt-8 space-y-8 p-8">
        <div>
          <div className="mb-3 text-sm font-semibold text-charcoal-800 dark:text-white">Preferred Styles</div>
          <div className="flex flex-wrap gap-2">
            {STYLES.map((s) => (
              <button
                key={s}
                onClick={() => setPrefs({ ...prefs, preferred_styles: toggle(prefs.preferred_styles, s) })}
                className={`rounded-full border px-4 py-1.5 text-xs font-semibold transition ${prefs.preferred_styles.includes(s) ? "border-charcoal-800 bg-charcoal-800 text-white" : "border-charcoal-200 text-charcoal-600 dark:border-charcoal-600 dark:text-charcoal-200"}`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="mb-3 text-sm font-semibold text-charcoal-800 dark:text-white">Preferred Colors</div>
          <div className="flex flex-wrap gap-2">
            {COLORS.map((c) => (
              <button
                key={c}
                onClick={() => setPrefs({ ...prefs, preferred_colors: toggle(prefs.preferred_colors, c) })}
                className={`rounded-full border px-4 py-1.5 text-xs font-semibold transition ${prefs.preferred_colors.includes(c) ? "border-charcoal-800 bg-charcoal-800 text-white" : "border-charcoal-200 text-charcoal-600 dark:border-charcoal-600 dark:text-charcoal-200"}`}
              >
                {c}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="mb-3 text-sm font-semibold text-charcoal-800 dark:text-white">Preferred Categories</div>
          <div className="flex flex-wrap gap-2">
            {CATEGORIES.map((c) => (
              <button
                key={c}
                onClick={() => setPrefs({ ...prefs, preferred_categories: toggle(prefs.preferred_categories, c) })}
                className={`rounded-full border px-4 py-1.5 text-xs font-semibold transition ${prefs.preferred_categories.includes(c) ? "border-charcoal-800 bg-charcoal-800 text-white" : "border-charcoal-200 text-charcoal-600 dark:border-charcoal-600 dark:text-charcoal-200"}`}
              >
                {c}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="mb-3 text-sm font-semibold text-charcoal-800 dark:text-white">Budget Range</div>
          <div className="flex items-center gap-4">
            <input
              type="number"
              className="input"
              value={prefs.budget_min}
              onChange={(e) => setPrefs({ ...prefs, budget_min: Number(e.target.value) })}
              placeholder="Min"
            />
            <span className="text-charcoal-400">to</span>
            <input
              type="number"
              className="input"
              value={prefs.budget_max}
              onChange={(e) => setPrefs({ ...prefs, budget_max: Number(e.target.value) })}
              placeholder="Max"
            />
          </div>
        </div>

        <button onClick={save} disabled={saving} className="btn-primary">
          {saving ? "Saving..." : "Save Preferences"}
        </button>
      </div>
    </div>
  );
}
