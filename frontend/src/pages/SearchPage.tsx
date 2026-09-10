import { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Camera, Upload, X, CheckCircle2, Loader2, Crop, RotateCcw, Layers } from "lucide-react";
import { api, apiErrorMessage, resolveAssetUrl } from "../services/api";
import { useToast } from "../context/ToastContext";
import ImageCropModal, { GarmentCropItem } from "../components/ImageCropModal";

const ANALYSIS_STEPS = [
  "Detecting garments & regions",
  "Classifying fashion categories",
  "Extracting colors, styles & patterns",
  "Performing sub-millisecond visual retrieval",
  "Synthesizing Shop The Look recommendations",
];

const MAX_MB = 8;
const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];

export default function SearchPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { push } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [crops, setCrops] = useState<GarmentCropItem[]>([]);
  const [isCropModalOpen, setIsCropModalOpen] = useState(false);

  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [budgetMax, setBudgetMax] = useState<string>("");

  useEffect(() => {
    if (location.state?.initialFile instanceof File) {
      validateAndSetFile(location.state.initialFile);
      window.history.replaceState({}, document.title);
    }
  }, [location.state]);

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
      crops.forEach((c) => {
        if (c.previewUrl) URL.revokeObjectURL(c.previewUrl);
      });
    };
  }, [preview, crops]);

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

    if (preview) URL.revokeObjectURL(preview);
    crops.forEach((c) => {
      if (c.previewUrl) URL.revokeObjectURL(c.previewUrl);
    });

    const objectUrl = URL.createObjectURL(f);
    setFile(f);
    setPreview(objectUrl);
    setCrops([]);
    setIsCropModalOpen(true);
  }

  function handleCropComplete(
    croppedFile: File,
    croppedPreviewUrl: string,
    allCrops?: GarmentCropItem[]
  ) {
    if (allCrops && allCrops.length > 0) {
      setCrops(allCrops);
    } else {
      setCrops([{ file: croppedFile, previewUrl: croppedPreviewUrl, label: "Garment 1" }]);
    }
    setIsCropModalOpen(false);
  }

  function handleRevertToFull() {
    crops.forEach((c) => {
      if (c.previewUrl) URL.revokeObjectURL(c.previewUrl);
    });
    setCrops([]);
  }

  function reset() {
    if (preview) URL.revokeObjectURL(preview);
    crops.forEach((c) => {
      if (c.previewUrl) URL.revokeObjectURL(c.previewUrl);
    });
    setFile(null);
    setPreview(null);
    setCrops([]);
    setIsCropModalOpen(false);
    setError("");
  }

  async function handleAnalyze() {
    if (!file && crops.length === 0) return;
    setAnalyzing(true);
    setStepIndex(0);

    const interval = setInterval(() => {
      setStepIndex((i) => Math.min(i + 1, ANALYSIS_STEPS.length - 1));
    }, 600);

    try {
      const isMulti = crops.length > 1;
      const params: Record<string, string> = {};
      if (budgetMax) params.budget_max = budgetMax;

      let res;
      if (isMulti) {
        // Multi-Item Shop The Look
        const formData = new FormData();
        crops.forEach((c) => {
          formData.append("files", c.file);
        });

        res = await api.post("/search/multi-item", formData, {
          headers: { "Content-Type": "multipart/form-data" },
          params,
        });
      } else {
        // Single Garment Search
        const singleFile = crops.length === 1 ? crops[0].file : file!;
        const formData = new FormData();
        formData.append("file", singleFile);

        res = await api.post("/search/image", formData, {
          headers: { "Content-Type": "multipart/form-data" },
          params,
        });
      }

      clearInterval(interval);

      // Determine the persisted server image URL
      const firstItemCrop = res.data.items?.[0];
      const serverImageUrl = res.data.query_image_url
        ? resolveAssetUrl(res.data.query_image_url)
        : res.data.image_path
        ? resolveAssetUrl(res.data.image_path)
        : firstItemCrop?.crop_filename
        ? resolveAssetUrl(`/uploads/${firstItemCrop.crop_filename}`)
        : displayPreviewUrl;

      // Build permanent crop previews from server response
      const cropPreviews = (res.data.items && res.data.items.length > 0)
        ? res.data.items.map((it: any, idx: number) => ({
            label: crops[idx]?.label || `Garment ${idx + 1}`,
            previewUrl: resolveAssetUrl(it.crop_preview_url || `/uploads/${it.crop_filename}`),
          }))
        : crops.map((c) => ({ label: c.label, previewUrl: c.previewUrl }));

      const resultPayload = {
        ...res.data,
        query_image_url: serverImageUrl,
        crop_previews: cropPreviews,
      };

      sessionStorage.setItem(`search_result_${res.data.search_id}`, JSON.stringify(resultPayload));
      if (serverImageUrl) {
        sessionStorage.setItem(`search_image_${res.data.search_id}`, serverImageUrl);
      }
      navigate(`/results/${res.data.search_id}`);
    } catch (err) {
      clearInterval(interval);
      setAnalyzing(false);
      push(apiErrorMessage(err, "Something went wrong while analyzing your image."), "error");
    }
  }

  const displayPreviewUrl = crops.length === 1 ? crops[0].previewUrl : preview;

  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <div className="text-center">
        <h1 className="font-display text-3xl font-semibold text-charcoal-900 dark:text-white">
          Shop The Look & AI Visual Search
        </h1>
        <p className="mt-2 text-charcoal-500 dark:text-charcoal-300">
          Upload any fashion photo or outfit screenshot. Search individual pieces or find matches for the entire look.
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
            {crops.length > 1 ? (
              <div className="flex items-center justify-center gap-3">
                {crops.map((c, idx) => (
                  <img
                    key={idx}
                    src={c.previewUrl}
                    alt={c.label}
                    className="h-28 w-24 rounded-xl object-cover shadow-card border-2 border-white dark:border-charcoal-700"
                  />
                ))}
              </div>
            ) : displayPreviewUrl ? (
              <img src={displayPreviewUrl} alt="Uploaded" className="h-40 w-40 rounded-2xl object-cover shadow-card" />
            ) : null}

            <div>
              <div className="font-display text-xl font-semibold text-charcoal-900 dark:text-white">
                {crops.length > 1 ? `Analyzing ${crops.length} Garments in Outfit...` : "Analyzing your style..."}
              </div>
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
                <div className="font-semibold text-charcoal-800 dark:text-white">Drag & drop your outfit photo here</div>
                <p className="text-sm text-charcoal-400">JPG, JPEG, PNG or WEBP — up to {MAX_MB}MB</p>
                <div className="mt-2 flex gap-3">
                  <button onClick={() => fileInputRef.current?.click()} className="btn-primary">
                    <Upload size={15} /> Upload Image
                  </button>
                  <button onClick={() => cameraInputRef.current?.click()} className="btn-secondary">
                    <Camera size={15} /> Use Camera
                  </button>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                  onChange={(e) => {
                    const selected = e.target.files?.[0] ?? null;
                    e.target.value = "";
                    validateAndSetFile(selected);
                  }}
                />
                <input
                  ref={cameraInputRef}
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="hidden"
                  onChange={(e) => {
                    const selected = e.target.files?.[0] ?? null;
                    e.target.value = "";
                    validateAndSetFile(selected);
                  }}
                />
                {error && <p className="text-sm font-medium text-rose-600">{error}</p>}
              </div>
            ) : (
              <div className="card p-8">
                {crops.length > 1 ? (
                  <div className="mb-4 flex items-center justify-center gap-1.5 rounded-full bg-rose-50 px-3.5 py-1 text-xs font-semibold text-rose-600 dark:bg-rose-500/10 dark:text-rose-400 w-fit mx-auto">
                    <Layers size={13} /> Shop The Look Active ({crops.length} Garments Selected)
                  </div>
                ) : crops.length === 1 ? (
                  <div className="mb-4 flex items-center justify-center gap-1.5 rounded-full bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-600 dark:bg-rose-500/10 dark:text-rose-400 w-fit mx-auto">
                    <Crop size={13} /> Garment Crop Active
                  </div>
                ) : null}

                {/* Preview Thumbnail Container */}
                <div className="relative mx-auto w-fit">
                  {crops.length > 1 ? (
                    <div className="flex flex-wrap justify-center gap-3">
                      {crops.map((c, idx) => (
                        <div key={idx} className="relative group">
                          <img
                            src={c.previewUrl}
                            alt={c.label}
                            className="h-44 w-36 rounded-2xl object-cover shadow-card border-2 border-rose-500/30"
                          />
                          <span className="absolute bottom-2 left-2 rounded-md bg-charcoal-900/80 px-2 py-0.5 text-[11px] font-semibold text-white">
                            {c.label}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <img src={displayPreviewUrl!} alt="Preview" className="max-h-96 rounded-2xl object-cover shadow-card" />
                  )}

                  <button
                    onClick={reset}
                    aria-label="Remove image"
                    className="absolute -right-3 -top-3 flex h-8 w-8 items-center justify-center rounded-full bg-charcoal-900 text-white shadow-card hover:bg-rose-600 transition"
                  >
                    <X size={15} />
                  </button>
                </div>

                <div className="mt-6 flex flex-wrap justify-center gap-2.5">
                  <button
                    onClick={() => setIsCropModalOpen(true)}
                    type="button"
                    className="btn-secondary text-xs py-2 px-3.5 flex items-center gap-1.5"
                  >
                    <Crop size={14} /> {crops.length > 0 ? "Adjust Garment Crops" : "Select Garments / Shop The Look"}
                  </button>
                  {crops.length > 0 && (
                    <button
                      onClick={handleRevertToFull}
                      type="button"
                      className="btn-secondary text-xs py-2 px-3.5 flex items-center gap-1.5"
                    >
                      <RotateCcw size={14} /> Use Full Image
                    </button>
                  )}
                </div>

                <div className="mt-8">
                  <label className="mb-1.5 block text-xs font-semibold text-charcoal-600 dark:text-charcoal-300">
                    Maximum budget per garment (optional)
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
                  <button onClick={handleAnalyze} className="btn-primary">
                    {crops.length > 1 ? `Analyze Outfit (${crops.length} Items)` : "Analyze Style"}
                  </button>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <ImageCropModal
        isOpen={isCropModalOpen}
        imageUrl={preview}
        originalFile={file}
        onClose={() => setIsCropModalOpen(false)}
        onCropComplete={handleCropComplete}
      />
    </div>
  );
}
