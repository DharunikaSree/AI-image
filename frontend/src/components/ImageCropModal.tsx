import React, { useRef, useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Crop, X, Check, RotateCcw, Plus, Trash2, Layers } from "lucide-react";

export interface GarmentCropItem {
  file: File;
  previewUrl: string;
  label: string;
  rect?: CropRect;
}

interface ImageCropModalProps {
  isOpen: boolean;
  imageUrl: string | null;
  originalFile: File | null;
  onClose: () => void;
  onCropComplete: (
    croppedFile: File,
    croppedPreviewUrl: string,
    allCrops?: GarmentCropItem[]
  ) => void;
}

export interface CropRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

const MIN_CROP_DIMENSION = 20;

export default function ImageCropModal({
  isOpen,
  imageUrl,
  originalFile,
  onClose,
  onCropComplete,
}: ImageCropModalProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  const [crop, setCrop] = useState<CropRect | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(null);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [savedCrops, setSavedCrops] = useState<GarmentCropItem[]>([]);

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setCrop(null);
      setIsDragging(false);
      setStartPoint(null);
      setImageLoaded(false);
      setSavedCrops([]);
    }
  }, [isOpen, imageUrl]);

  const handleImageLoad = () => {
    if (imageRef.current) {
      const rect = imageRef.current.getBoundingClientRect();
      setImageLoaded(true);
      setCrop({
        x: 0,
        y: 0,
        width: rect.width,
        height: rect.height,
      });
    }
  };

  const getClampedCoords = useCallback(
    (clientX: number, clientY: number): { x: number; y: number } | null => {
      if (!imageRef.current) return null;
      const rect = imageRef.current.getBoundingClientRect();
      const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
      const y = Math.max(0, Math.min(clientY - rect.top, rect.height));
      return { x, y };
    },
    []
  );

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    const coords = getClampedCoords(e.clientX, e.clientY);
    if (!coords) return;

    setStartPoint(coords);
    setIsDragging(true);
    setCrop({
      x: coords.x,
      y: coords.y,
      width: 0,
      height: 0,
    });
  };

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isDragging || !startPoint || !imageRef.current) return;
      const coords = getClampedCoords(e.clientX, e.clientY);
      if (!coords) return;

      const x = Math.min(startPoint.x, coords.x);
      const y = Math.min(startPoint.y, coords.y);
      const width = Math.abs(coords.x - startPoint.x);
      const height = Math.abs(coords.y - startPoint.y);

      setCrop({ x, y, width, height });
    },
    [isDragging, startPoint, getClampedCoords]
  );

  const handleMouseUp = useCallback(() => {
    if (isDragging) {
      setIsDragging(false);
      setStartPoint(null);
    }
  }, [isDragging]);

  const handleTouchStart = (e: React.TouchEvent) => {
    if (e.touches.length !== 1) return;
    const touch = e.touches[0];
    const coords = getClampedCoords(touch.clientX, touch.clientY);
    if (!coords) return;

    setStartPoint(coords);
    setIsDragging(true);
    setCrop({
      x: coords.x,
      y: coords.y,
      width: 0,
      height: 0,
    });
  };

  const handleTouchMove = useCallback(
    (e: TouchEvent) => {
      if (!isDragging || !startPoint || !imageRef.current) return;
      if (e.touches.length !== 1) return;
      const touch = e.touches[0];
      const coords = getClampedCoords(touch.clientX, touch.clientY);
      if (!coords) return;

      const x = Math.min(startPoint.x, coords.x);
      const y = Math.min(startPoint.y, coords.y);
      const width = Math.abs(coords.x - startPoint.x);
      const height = Math.abs(coords.y - startPoint.y);

      setCrop({ x, y, width, height });
    },
    [isDragging, startPoint, getClampedCoords]
  );

  const handleTouchEnd = useCallback(() => {
    if (isDragging) {
      setIsDragging(false);
      setStartPoint(null);
    }
  }, [isDragging]);

  useEffect(() => {
    if (isDragging) {
      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
      window.addEventListener("touchmove", handleTouchMove, { passive: false });
      window.addEventListener("touchend", handleTouchEnd);
      return () => {
        window.removeEventListener("mousemove", handleMouseMove);
        window.removeEventListener("mouseup", handleMouseUp);
        window.removeEventListener("touchmove", handleTouchMove);
        window.removeEventListener("touchend", handleTouchEnd);
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp, handleTouchMove, handleTouchEnd]);

  const handleSelectFull = () => {
    if (imageRef.current) {
      const rect = imageRef.current.getBoundingClientRect();
      setCrop({
        x: 0,
        y: 0,
        width: rect.width,
        height: rect.height,
      });
    }
  };

  const generateCropBlob = (cropRect: CropRect): Promise<{ file: File; previewUrl: string } | null> => {
    return new Promise((resolve) => {
      if (!imageRef.current || !imageUrl) {
        resolve(null);
        return;
      }
      const img = imageRef.current;
      const rect = img.getBoundingClientRect();
      const naturalWidth = img.naturalWidth;
      const naturalHeight = img.naturalHeight;

      if (naturalWidth === 0 || naturalHeight === 0 || rect.width === 0 || rect.height === 0) {
        resolve(null);
        return;
      }

      const scaleX = naturalWidth / rect.width;
      const scaleY = naturalHeight / rect.height;

      const naturalCropX = Math.round(cropRect.x * scaleX);
      const naturalCropY = Math.round(cropRect.y * scaleY);
      const naturalCropWidth = Math.round(cropRect.width * scaleX);
      const naturalCropHeight = Math.round(cropRect.height * scaleY);

      if (naturalCropWidth < 10 || naturalCropHeight < 10) {
        resolve(null);
        return;
      }

      const canvas = document.createElement("canvas");
      canvas.width = naturalCropWidth;
      canvas.height = naturalCropHeight;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        resolve(null);
        return;
      }

      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(
        img,
        naturalCropX,
        naturalCropY,
        naturalCropWidth,
        naturalCropHeight,
        0,
        0,
        naturalCropWidth,
        naturalCropHeight
      );

      canvas.toBlob(
        (blob) => {
          if (!blob) {
            resolve(null);
            return;
          }
          const originalName = originalFile?.name || "garment_crop.jpg";
          const baseName = originalName.replace(/\.[^/.]+$/, "");
          const file = new File([blob], `${baseName}_crop_${Date.now()}.jpg`, {
            type: "image/jpeg",
            lastModified: Date.now(),
          });
          const previewUrl = URL.createObjectURL(blob);
          resolve({ file, previewUrl });
        },
        "image/jpeg",
        0.95
      );
    });
  };

  // Add current active crop to list of outfit garments
  const handleAddGarmentCrop = async () => {
    if (!crop || !isCropValid) return;
    const result = await generateCropBlob(crop);
    if (!result) return;

    const newIndex = savedCrops.length + 1;
    const newCrop: GarmentCropItem = {
      file: result.file,
      previewUrl: result.previewUrl,
      label: `Garment ${newIndex}`,
      rect: crop,
    };

    setSavedCrops((prev) => [...prev, newCrop]);
  };

  const handleRemoveCrop = (index: number) => {
    setSavedCrops((prev) => {
      const target = prev[index];
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl);
      return prev.filter((_, i) => i !== index);
    });
  };

  // Submit crops
  const handleCropAndContinue = async () => {
    if (savedCrops.length > 0) {
      // Multiple crops submitted
      const primaryCrop = savedCrops[0];
      onCropComplete(primaryCrop.file, primaryCrop.previewUrl, savedCrops);
      return;
    }

    if (!crop || !isCropValid) return;
    const result = await generateCropBlob(crop);
    if (!result) return;

    onCropComplete(result.file, result.previewUrl, [
      { file: result.file, previewUrl: result.previewUrl, label: "Garment 1", rect: crop },
    ]);
  };

  const isCropValid =
    crop !== null &&
    crop.width >= MIN_CROP_DIMENSION &&
    crop.height >= MIN_CROP_DIMENSION;

  if (!isOpen || !imageUrl) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 bg-charcoal-950/80 backdrop-blur-sm"
        />

        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 15 }}
          className="relative z-10 flex max-h-[92vh] w-full max-w-3xl flex-col rounded-3xl bg-white p-6 shadow-2xl dark:bg-charcoal-800 sm:p-8"
        >
          {/* Header */}
          <div className="flex items-start justify-between pb-4 border-b border-charcoal-100 dark:border-charcoal-700">
            <div>
              <div className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-rose-50 text-rose-500 dark:bg-rose-500/10">
                  <Crop size={18} />
                </span>
                <h2 className="font-display text-xl font-semibold text-charcoal-900 dark:text-white">
                  Shop The Look — Select Garments
                </h2>
              </div>
              <p className="mt-1 text-xs sm:text-sm text-charcoal-500 dark:text-charcoal-400">
                Drag a box over an item (e.g. shirt, trousers, shoes). Click <strong className="text-charcoal-800 dark:text-white">+ Add Garment</strong> to search multiple items together!
              </p>
            </div>
            <button
              onClick={onClose}
              aria-label="Close crop modal"
              className="rounded-full p-2 text-charcoal-400 hover:bg-sand-100 hover:text-charcoal-700 dark:hover:bg-charcoal-700 dark:hover:text-white transition"
            >
              <X size={18} />
            </button>
          </div>

          {/* Interactive Image Cropping Viewport */}
          <div className="my-4 flex flex-1 items-center justify-center overflow-hidden rounded-2xl bg-charcoal-900/95 p-2 sm:p-4">
            <div
              ref={containerRef}
              className="relative inline-block select-none overflow-hidden touch-none"
              onMouseDown={handleMouseDown}
              onTouchStart={handleTouchStart}
              style={{ cursor: isDragging ? "crosshair" : "crosshair" }}
            >
              <img
                ref={imageRef}
                src={imageUrl}
                alt="Crop target"
                onLoad={handleImageLoad}
                className="max-h-[46vh] max-w-full rounded-lg object-contain pointer-events-none"
                draggable={false}
              />

              {/* Bounding Box Selection Highlight */}
              {imageLoaded && crop && crop.width > 0 && crop.height > 0 && (
                <div
                  className="absolute pointer-events-none border-2 border-dashed border-white shadow-[0_0_0_9999px_rgba(0,0,0,0.55)] transition-[box-shadow]"
                  style={{
                    left: `${crop.x}px`,
                    top: `${crop.y}px`,
                    width: `${crop.width}px`,
                    height: `${crop.height}px`,
                  }}
                >
                  <div className="absolute inset-0 grid grid-cols-3 grid-rows-3 opacity-40">
                    <div className="border-r border-b border-white/60" />
                    <div className="border-r border-b border-white/60" />
                    <div className="border-b border-white/60" />
                    <div className="border-r border-b border-white/60" />
                    <div className="border-r border-b border-white/60" />
                    <div className="border-b border-white/60" />
                    <div className="border-r border-b border-white/60" />
                    <div className="border-r border-b border-white/60" />
                    <div />
                  </div>

                  <div className="absolute -left-1 -top-1 h-2.5 w-2.5 bg-white border border-rose-500 rounded-sm" />
                  <div className="absolute -right-1 -top-1 h-2.5 w-2.5 bg-white border border-rose-500 rounded-sm" />
                  <div className="absolute -left-1 -bottom-1 h-2.5 w-2.5 bg-white border border-rose-500 rounded-sm" />
                  <div className="absolute -right-1 -bottom-1 h-2.5 w-2.5 bg-white border border-rose-500 rounded-sm" />

                  <div className="absolute -top-7 left-1/2 -translate-x-1/2 rounded bg-charcoal-900/90 px-2 py-0.5 text-[10px] font-medium text-white shadow">
                    {Math.round(crop.width)} × {Math.round(crop.height)} px
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Saved Multi-Crops Tray */}
          {savedCrops.length > 0 && (
            <div className="mb-3 flex items-center gap-2 overflow-x-auto rounded-xl bg-sand-50 p-2.5 dark:bg-charcoal-700/50">
              <span className="flex items-center gap-1 text-xs font-semibold text-charcoal-600 dark:text-charcoal-300 pr-2 border-r border-charcoal-200 dark:border-charcoal-600">
                <Layers size={14} /> Outfit ({savedCrops.length}):
              </span>
              {savedCrops.map((c, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 rounded-lg bg-white px-2.5 py-1 text-xs font-medium text-charcoal-800 shadow-sm dark:bg-charcoal-800 dark:text-white"
                >
                  <img src={c.previewUrl} alt={c.label} className="h-6 w-6 rounded object-cover" />
                  <span>{c.label}</span>
                  <button
                    onClick={() => handleRemoveCrop(idx)}
                    className="text-charcoal-400 hover:text-rose-500 transition ml-1"
                    title="Remove garment"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Footer Controls */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-charcoal-100 dark:border-charcoal-700">
            <div className="flex items-center gap-3">
              <button
                onClick={handleSelectFull}
                type="button"
                className="flex items-center gap-1.5 text-xs font-semibold text-charcoal-600 hover:text-charcoal-900 dark:text-charcoal-300 dark:hover:text-white"
              >
                <RotateCcw size={14} /> Full Image
              </button>

              <button
                onClick={handleAddGarmentCrop}
                disabled={!isCropValid}
                type="button"
                className={`flex items-center gap-1.5 rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-600 hover:bg-rose-100 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300 ${
                  !isCropValid ? "opacity-50 cursor-not-allowed" : ""
                }`}
              >
                <Plus size={14} /> Add Garment to Look
              </button>
            </div>

            <div className="flex w-full sm:w-auto items-center justify-end gap-2.5">
              <button
                onClick={onClose}
                type="button"
                className="btn-secondary flex-1 sm:flex-none text-xs sm:text-sm py-2 px-4"
              >
                Cancel
              </button>
              <button
                onClick={handleCropAndContinue}
                disabled={!isCropValid && savedCrops.length === 0}
                type="button"
                className={`btn-primary flex-1 sm:flex-none text-xs sm:text-sm py-2 px-4 flex items-center justify-center gap-1.5 ${
                  !isCropValid && savedCrops.length === 0 ? "opacity-50 cursor-not-allowed" : ""
                }`}
              >
                <Check size={16} />
                {savedCrops.length > 1
                  ? `Search Outfit (${savedCrops.length} items)`
                  : "Search Garment"}
              </button>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
