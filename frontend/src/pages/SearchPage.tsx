import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Camera, Upload, X, CheckCircle2, Loader2 } from "lucide-react";
import { api, apiErrorMessage } from "../services/api";
import { useToast } from "../context/ToastContext";

const ANALYSIS_STEPS = [
  "Detecting clothing",
  "Extracting attributes",
  "Understanding colors",
  "Finding visual matches",
  "Preparing recommendations",
];

const MAX_MB = 8;
const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];

export default function SearchPage() {
  const navigate = useNavigate();
  const { push } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [budgetMax, setBudgetMax] = useState<string>("");

  function validateAndSetFile(f: File | null) {
    setError("");
    if (!f) return;
    if (!ALLOWED_TYPES.includes(f.type)) {
      setError("Unsupported format. Please upload a JPG, PNG, or WEBP image.");
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`Image is too large. Maximum size is ${MAX_MB}MB.`);
      return;
    }
    setFile(f);
    setPreview(URL.createObjectURL(f));
  }

  function reset() {
    setFile(null);
    setPreview(null);
    setError("");
  }

  async function handleAnalyze() {
    if (!file) return;
    setAnalyzing(true);
    setStepIndex(0);

    const interval = setInterval(() => {
      setStepIndex((i) => Math.min(i + 1, ANALYSIS_STEPS.length - 1));
    }, 650);

    try {
      const formData = new FormData();
      formData.append("file", file);
      const params: Record<string, string> = {};
      if (budgetMax) params.budget_max = budgetMax;

      const res = await api.post("/search/image", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        params,
      });

      clearInterval(interval);
      sessionStorage.setItem(`search_result_${res.data.search_id}`, JSON.stringify(res.data));
      navigate(`/results/${res.data.search_id}`);
    } catch (err) {
      clearInterval(interval);
      setAnalyzing(false);
      push(apiErrorMessage(err, "Something went wrong while analyzing your image."), "error");
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <div className="text-center">
        <h1 className="font-display text-3xl font-semibold text-charcoal-900 dark:text-white">Search by Image</h1>
        <p className="mt-2 text-charcoal-500 dark:text-charcoal-300">
          Upload a fashion photo or screenshot and let AI find your style.
        </p>
      </div>

      <AnimatePresence mode="wait">
        {analyzing ? (
          <motion.div
            key="analyzing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="card mt-10 flex flex-col items-center gap-8 p-12 text-center"
          >
            {preview && (
              <img src={preview} alt="Uploaded" className="h-40 w-40 rounded-2xl object-cover shadow-card" />
            )}
            <div>
              <div className="font-display text-xl font-semibold text-charcoal-900 dark:text-white">Analyzing your style...</div>
              <div className="mt-6 space-y-3 text-left">
                {ANALYSIS_STEPS.map((step, i) => (
                  <div key={step} className="flex items-center gap-3">
                    {i < stepIndex ? (
                      <CheckCircle2 size={18} className="text-green-600" />
                    ) : i === stepIndex ? (
                      <Loader2 size={18} className="animate-spin text-rose-500" />
                    ) : (
                      <div className="h-[18px] w-[18px] rounded-full border-2 border-charcoal-200" />
                    )}
                    <span className={`text-sm ${i <= stepIndex ? "text-charcoal-800 dark:text-white" : "text-charcoal-300"}`}>
                      {step}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        ) : (
          <motion.div key="upload" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="mt-10">
            {!file ? (
              <div
                className={`card flex flex-col items-center gap-4 border-2 border-dashed p-14 text-center transition ${
                  dragActive ? "border-rose-400 bg-rose-50/50" : "border-charcoal-200"
                }`}
                onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
                onDragLeave={() => setDragActive(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragActive(false);
                  validateAndSetFile(e.dataTransfer.files?.[0] ?? null);
                }}
              >
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-charcoal-800 text-white">
                  <Upload size={26} />
                </div>
                <div className="font-semibold text-charcoal-800 dark:text-white">Drag & drop your image here</div>
                <p className="text-sm text-charcoal-400">JPG, JPEG, PNG or WEBP — up to {MAX_MB}MB</p>
                <div className="mt-2 flex gap-3">
                  <button onClick={() => fileInputRef.current?.click()} className="btn-primary">
                    <Upload size={15} /> Upload Image
                  </button>
                  <button onClick={() => cameraInputRef.current?.click()} className="btn-secondary">
                    <Camera size={15} /> Use Camera
                  </button>
                </div>
                <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(e) => validateAndSetFile(e.target.files?.[0] ?? null)} />
                <input ref={cameraInputRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => validateAndSetFile(e.target.files?.[0] ?? null)} />
                {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
              </div>
            ) : (
              <div className="card p-8">
                <div className="relative mx-auto w-fit">
                  <img src={preview!} alt="Preview" className="max-h-96 rounded-2xl object-cover shadow-card" />
                  <button
                    onClick={reset}
                    aria-label="Remove image"
                    className="absolute -right-3 -top-3 flex h-8 w-8 items-center justify-center rounded-full bg-charcoal-900 text-white shadow-card"
                  >
                    <X size={15} />
                  </button>
                </div>

                <div className="mt-8">
                  <label className="mb-1.5 block text-xs font-semibold text-charcoal-600 dark:text-charcoal-300">
                    Maximum budget (optional)
                  </label>
                  <input
                    className="input max-w-xs"
                    type="number"
                    min={0}
                    placeholder="e.g. 2000"
                    value={budgetMax}
                    onChange={(e) => setBudgetMax(e.target.value)}
                  />
                  <p className="mt-1 text-xs text-charcoal-400">We'll prioritize affordable alternatives within this budget.</p>
                </div>

                <div className="mt-8 flex justify-center gap-3">
                  <button onClick={reset} className="btn-secondary">Upload Another Image</button>
                  <button onClick={handleAnalyze} className="btn-primary">Analyze Style</button>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
