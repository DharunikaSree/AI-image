import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Camera, Sparkles, Search, Tag, Palette, ShoppingBag, ArrowRight } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const FEATURES = [
  { icon: Camera, title: "Upload Any Photo", text: "A screenshot, an ad, a photo from a friend — if you can see it, you can search it." },
  { icon: Sparkles, title: "AI Style Detection", text: "Category, color, pattern and style are identified automatically from the image." },
  { icon: Search, title: "Visual Similarity Search", text: "We compare the uploaded look against our catalog using real embedding similarity." },
  { icon: Tag, title: "Affordable Alternatives", text: "See lower-priced options that match the same style, ranked by real value." },
  { icon: Palette, title: "Color Variants", text: "Love the cut but not the color? See the same piece in other shades." },
  { icon: ShoppingBag, title: "Shop the Full Look", text: "Multiple items detected in one photo become a complete outfit plan." },
];

const STEPS = [
  { step: "01", title: "Upload", text: "Drop in a photo or screenshot of the outfit you love." },
  { step: "02", title: "Analyze", text: "Our AI detects clothing type, color, pattern and style." },
  { step: "03", title: "Discover", text: "Browse visual matches, alternatives, and complete looks." },
];

export default function LandingPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  function goToSearchWithFile(file: File | null) {
    if (!file) return;
    if (user) {
      navigate("/search", { state: { initialFile: file } });
    } else {
      navigate("/login", { state: { pendingFile: file } });
    }
  }

  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 -z-10 bg-gradient-to-b from-sand-50 via-canvas-light to-canvas-light dark:from-charcoal-800 dark:via-canvas-dark dark:to-canvas-dark" />
        <div className="mx-auto grid max-w-7xl items-center gap-12 px-6 py-20 lg:grid-cols-2 lg:py-28">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-600 dark:bg-charcoal-700 dark:text-rose-300">
              <Sparkles size={12} /> AI-Powered Visual Fashion Search
            </span>
            <h1 className="mt-5 font-display text-4xl font-semibold leading-tight text-charcoal-900 dark:text-white sm:text-5xl lg:text-6xl">
              Find Any Style.
              <br />
              Discover Where to Buy.
            </h1>
            <p className="mt-5 max-w-lg text-base leading-relaxed text-charcoal-500 dark:text-charcoal-300">
              Upload a fashion photo or screenshot and let AI identify the style, find visually
              similar products, compare affordable alternatives, and discover your perfect look.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <button onClick={() => navigate(user ? "/search" : "/login")} className="btn-primary">
                <Camera size={16} /> Search by Image
              </button>
              <button onClick={() => navigate("/catalog")} className="btn-secondary">
                Explore Styles <ArrowRight size={15} />
              </button>
            </div>
            <div className="mt-10 flex gap-10">
              <div>
                <div className="font-display text-2xl font-semibold text-charcoal-900 dark:text-white">30+</div>
                <div className="text-xs text-charcoal-400">Catalog Styles</div>
              </div>
              <div>
                <div className="font-display text-2xl font-semibold text-charcoal-900 dark:text-white">6</div>
                <div className="text-xs text-charcoal-400">Recommendation Signals</div>
              </div>
              <div>
                <div className="font-display text-2xl font-semibold text-charcoal-900 dark:text-white">100%</div>
                <div className="text-xs text-charcoal-400">Explainable Matches</div>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6, delay: 0.15 }}
            className={`card relative flex aspect-square flex-col items-center justify-center gap-4 border-2 border-dashed p-10 text-center transition ${
              dragActive ? "border-rose-400 bg-rose-50/50" : "border-charcoal-200"
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
            onDragLeave={() => setDragActive(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragActive(false);
              goToSearchWithFile(e.dataTransfer.files?.[0] ?? null);
            }}
          >
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-charcoal-800 text-white">
              <Camera size={26} />
            </div>
            <div className="font-semibold text-charcoal-800 dark:text-white">Drag & drop a fashion photo</div>
            <p className="text-sm text-charcoal-400">or click below to browse — JPG, PNG or WEBP</p>
            <button onClick={() => fileInputRef.current?.click()} className="btn-primary">
              Choose Image
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={(e) => goToSearchWithFile(e.target.files?.[0] ?? null)}
            />
          </motion.div>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-7xl px-6 py-20">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-display text-3xl font-semibold text-charcoal-900 dark:text-white">
            Everything you need to shop a style you saw
          </h2>
          <p className="mt-3 text-charcoal-500 dark:text-charcoal-300">
            Built around one real problem: you like an outfit, but you don't know what it is or where to find it.
          </p>
        </div>
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="card p-6">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-sand-100 text-charcoal-800 dark:bg-charcoal-700 dark:text-white">
                <f.icon size={20} />
              </div>
              <h3 className="mt-4 font-semibold text-charcoal-900 dark:text-white">{f.title}</h3>
              <p className="mt-1.5 text-sm text-charcoal-500 dark:text-charcoal-300">{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="bg-sand-50 py-20 dark:bg-charcoal-800">
        <div className="mx-auto max-w-7xl px-6">
          <h2 className="text-center font-display text-3xl font-semibold text-charcoal-900 dark:text-white">How it works</h2>
          <div className="mt-12 grid gap-8 md:grid-cols-3">
            {STEPS.map((s) => (
              <div key={s.step} className="text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-charcoal-900 font-display text-lg font-semibold text-white dark:bg-white dark:text-charcoal-900">
                  {s.step}
                </div>
                <h3 className="mt-4 font-semibold text-charcoal-900 dark:text-white">{s.title}</h3>
                <p className="mt-1.5 text-sm text-charcoal-500 dark:text-charcoal-300">{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-4xl px-6 py-24 text-center">
        <h2 className="font-display text-3xl font-semibold text-charcoal-900 dark:text-white">
          Saw something you loved? Let's find it.
        </h2>
        <p className="mx-auto mt-3 max-w-md text-charcoal-500 dark:text-charcoal-300">
          Upload a photo and get matches, alternatives and a full style breakdown in seconds.
        </p>
        <button onClick={() => navigate(user ? "/search" : "/login")} className="btn-primary mt-8">
          <Camera size={16} /> Start Searching
        </button>
      </section>
    </div>
  );
}
