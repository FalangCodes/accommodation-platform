"use client";

import { useState, useRef } from "react";
import { accommodationsApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Loader2, Upload, X, ImagePlus, CheckCircle } from "lucide-react";
import { toast } from "sonner";

interface UploadedImage {
  id: number;
  url: string;
  order: number;
}

interface ImageUploaderProps {
  accommodationId: number;
  existingImages?: UploadedImage[];
  onDone?: () => void;
  showDoneButton?: boolean;
}

export default function ImageUploader({
  accommodationId,
  existingImages = [],
  onDone,
  showDoneButton = true,
}: ImageUploaderProps) {
  const [images, setImages] = useState<UploadedImage[]>(existingImages);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;

    const remaining = 8 - images.length;
    if (remaining <= 0) {
      toast.error("Maximum of 8 images reached");
      return;
    }

    const toUpload = files.slice(0, remaining);
    if (files.length > remaining) {
      toast.warning(`Only ${remaining} more image${remaining !== 1 ? "s" : ""} can be added`);
    }

    setUploading(true);
    let successCount = 0;

    for (const file of toUpload) {
      // Client-side validation
      if (file.size > 5 * 1024 * 1024) {
        toast.error(`${file.name} is too large — max 5MB`);
        continue;
      }
      if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
        toast.error(`${file.name} is not a supported format`);
        continue;
      }

      try {
        const res = await accommodationsApi.uploadImage(accommodationId, file);
        setImages((prev) => [...prev, res.data]);
        successCount++;
      } catch (err: any) {
        toast.error(err?.response?.data?.detail ?? `Failed to upload ${file.name}`);
      }
    }

    if (successCount > 0) {
      toast.success(`${successCount} image${successCount !== 1 ? "s" : ""} uploaded`);
    }

    setUploading(false);
    // Reset input so same file can be re-selected
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleDelete = async (image: UploadedImage) => {
    setDeletingId(image.id);
    try {
      await accommodationsApi.deleteImage(accommodationId, image.id);
      setImages((prev) => prev.filter((img) => img.id !== image.id));
      toast.success("Image removed");
    } catch {
      toast.error("Failed to remove image");
    } finally {
      setDeletingId(null);
    }
  };

  const canUploadMore = images.length < 8;

  return (
    <div className="space-y-4">
      {/* Upload zone */}
      {canUploadMore && (
        <div
          onClick={() => !uploading && inputRef.current?.click()}
          className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all cursor-pointer
            ${uploading
              ? "border-slate-200 bg-slate-50 cursor-not-allowed"
              : "border-slate-300 hover:border-slate-400 hover:bg-slate-50"
            }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            className="hidden"
            onChange={handleFileChange}
            disabled={uploading}
          />
          {uploading ? (
            <div className="flex flex-col items-center gap-2">
              <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
              <p className="text-sm text-slate-500">Uploading...</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <div className="h-12 w-12 rounded-xl bg-slate-100 flex items-center justify-center">
                <ImagePlus className="h-6 w-6 text-slate-400" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-700">
                  Click to upload photos
                </p>
                <p className="text-xs text-slate-400 mt-0.5">
                  JPEG, PNG, WebP — max 5MB each · {images.length}/8 uploaded
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Image grid */}
      {images.length > 0 && (
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-3">
          {images.map((img, index) => (
            <div
              key={img.id}
              className="relative group aspect-square rounded-xl overflow-hidden border border-slate-200 bg-slate-100"
            >
              <img
                src={img.url}
                alt={`Photo ${index + 1}`}
                className="w-full h-full object-cover"
              />
              {/* First image badge */}
              {index === 0 && (
                <div className="absolute top-1.5 left-1.5 bg-black/60 text-white text-[10px] font-medium px-1.5 py-0.5 rounded-md">
                  Cover
                </div>
              )}
              {/* Delete button */}
              <button
                onClick={() => handleDelete(img)}
                disabled={deletingId === img.id}
                className="absolute top-1.5 right-1.5 h-6 w-6 rounded-full bg-black/60 hover:bg-red-500 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all"
              >
                {deletingId === img.id ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <X className="h-3 w-3" />
                )}
              </button>
            </div>
          ))}

          {/* Add more slot */}
          {canUploadMore && (
            <button
              onClick={() => !uploading && inputRef.current?.click()}
              disabled={uploading}
              className="aspect-square rounded-xl border-2 border-dashed border-slate-200 hover:border-slate-300 hover:bg-slate-50 flex items-center justify-center transition-all"
            >
              <Upload className="h-5 w-5 text-slate-300" />
            </button>
          )}
        </div>
      )}

      {/* Max reached notice */}
      {images.length >= 8 && (
        <div className="flex items-center gap-2 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3">
          <CheckCircle className="h-4 w-4 shrink-0" />
          Maximum of 8 photos uploaded
        </div>
      )}

      {/* Done button */}
      {showDoneButton && onDone && (
        <Button
          onClick={onDone}
          className="w-full rounded-xl bg-slate-900 hover:bg-slate-800 text-white"
          disabled={uploading}
        >
          {images.length === 0 ? "Skip for now" : "Done — submit listing"}
        </Button>
      )}
    </div>
  );
}