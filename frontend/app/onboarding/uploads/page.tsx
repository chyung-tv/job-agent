"use client";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { UploadDropzone } from "@/lib/uploadthing";
import { useOnboardingStore } from "@/store/useOnboardingStore";
import { FileText, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

const MAX_FILE_SIZE_MB = 64;

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  const lower = message.toLowerCase();
  if (lower.includes("size") || lower.includes("too large") || lower.includes("bytes"))
    return `File size exceeds ${MAX_FILE_SIZE_MB}MB limit. Please choose a smaller file.`;
  if (lower.includes("type") || lower.includes("invalid") || lower.includes("not allowed") || lower.includes("pdf"))
    return "Only PDF files are allowed.";
  if (lower.includes("network") || lower.includes("fetch") || lower.includes("transport") || lower.includes("socket"))
    return "Network error. Please check your connection and try again.";
  if (lower.includes("metadata") || lower.includes("register"))
    return ""; // Non-critical, don't show to user
  return "Failed to upload file. Please try again.";
}

export default function UploadsPage() {
  const router = useRouter();
  const { cv_files, addCvFile } = useOnboardingStore();
  const [isUploading, setIsUploading] = useState(false);
  const [stagedFiles, setStagedFiles] = useState<File[]>([]);
  const [objectUrls, setObjectUrls] = useState<Record<string, string>>({});
  const [uploadError, setUploadError] = useState<string | null>(null);
  const errorDismissRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** Ref of currently staged files (so we can filter in onBeforeUploadBegin after user deletes some) */
  const stagedFilesRef = useRef<File[]>([]);

  const revokeStagedUrls = useCallback((urls: Record<string, string>) => {
    Object.values(urls).forEach((url) => {
      try {
        URL.revokeObjectURL(url);
      } catch {
        // ignore
      }
    });
  }, []);

  const handleDeleteStaged = useCallback((fileToDelete: File) => {
    setObjectUrls((prev) => {
      const url = prev[fileToDelete.name];
      if (url) {
        try {
          URL.revokeObjectURL(url);
        } catch {
          // ignore
        }
        const next = { ...prev };
        delete next[fileToDelete.name];
        return next;
      }
      return prev;
    });
    setStagedFiles((prev) => {
      const next = prev.filter((f) => f !== fileToDelete);
      stagedFilesRef.current = next;
      return next;
    });
  }, []);

  useEffect(() => {
    return () => {
      revokeStagedUrls(objectUrls);
      if (errorDismissRef.current) clearTimeout(errorDismissRef.current);
    };
  }, [objectUrls, revokeStagedUrls]);

  /** Stage files: create preview URLs and set state. Used when files are selected (onDrop) and right before upload (onBeforeUploadBegin). */
  const stageFiles = useCallback(
    (files: File[]) => {
      const newUrls: Record<string, string> = {};
      files.forEach((file) => {
        try {
          newUrls[file.name] = URL.createObjectURL(file);
        } catch {
          // ignore
        }
      });
      setObjectUrls((prev) => {
        revokeStagedUrls(prev);
        return newUrls;
      });
      setStagedFiles(files);
      stagedFilesRef.current = files;
    },
    [revokeStagedUrls]
  );

  /** Called when user drops or selects files – show them in "Ready to upload" before they click Upload. */
  const handleDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;
      stageFiles(acceptedFiles);
    },
    [stageFiles]
  );

  /** Only upload files that are still in the staged list (user may have removed some via delete). */
  const handleBeforeUploadBegin = useCallback((files: File[]) => {
    const allowed = stagedFilesRef.current;
    return files.filter((f) =>
      allowed.some((sf) => sf.name === f.name && sf.size === f.size)
    );
  }, []);

  const handleUploadComplete = useCallback(
    (res: { name: string; size: number; key: string; url: string }[]) => {
      setIsUploading(false);
      setStagedFiles([]);
      setObjectUrls((prev) => {
        revokeStagedUrls(prev);
        return {};
      });
      setUploadError(null);
      res.forEach((file) => {
        if (file.url) {
          console.log("CV URL:", file.url);
          addCvFile({ url: file.url, name: file.name ?? file.key ?? "document.pdf" });
        } else {
          console.warn("Upload completed but file.url missing:", file.key);
        }
      });
    },
    [addCvFile, revokeStagedUrls]
  );

  const handleUploadError = useCallback((error: unknown) => {
    setIsUploading(false);
    const msg = getErrorMessage(error);
    if (msg) {
      setUploadError(msg);
      if (errorDismissRef.current) clearTimeout(errorDismissRef.current);
      errorDismissRef.current = setTimeout(() => setUploadError(null), 5000);
    }
    if (msg !== "" || !String(error).toLowerCase().includes("metadata")) {
      console.error("Upload error:", error);
    }
  }, []);

  const handleUploadBegin = useCallback(() => {
    setIsUploading(true);
    setUploadError(null);
  }, []);

  const handleContinue = () => {
    if (cv_files.length > 0) router.push("/onboarding/review");
  };

  const handleBack = () => router.push("/onboarding/identity");

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="text-2xl font-bold">Upload Your CV/Resume</CardTitle>
        <CardDescription>
          Upload your CV or resume files in PDF format (max {MAX_FILE_SIZE_MB}MB per file)
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {uploadError && (
          <div
            className="flex items-center justify-between gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
            role="alert"
          >
            <span>{uploadError}</span>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-6 w-6 shrink-0"
              onClick={() => {
                setUploadError(null);
                if (errorDismissRef.current) {
                  clearTimeout(errorDismissRef.current);
                  errorDismissRef.current = null;
                }
              }}
              aria-label="Dismiss error"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}

        {/* Staged files: shown as soon as user selects files, before they click Upload */}
        {stagedFiles.length > 0 && (
          <div className="rounded-lg border-2 border-dashed border-primary/40 bg-primary/5 p-4">
            <h4 className="mb-2 text-sm font-semibold">Ready to upload ({stagedFiles.length})</h4>
            <div className="flex flex-wrap gap-3">
              {stagedFiles.map((file, i) => {
                const previewUrl = objectUrls[file.name];
                const isImage = file.type.startsWith("image/");
                return (
                  <Card key={`${file.name}-${i}`} className="flex items-center gap-2 p-2 shadow-sm">
                    {isImage && previewUrl ? (
                      // eslint-disable-next-line @next/next/no-img-element -- blob URL for local preview
                      <img
                        src={previewUrl}
                        alt=""
                        className="h-8 w-8 shrink-0 rounded object-cover"
                      />
                    ) : (
                      <FileText className="h-8 w-8 shrink-0 text-muted-foreground" />
                    )}
                    <span className="max-w-[150px] truncate text-xs" title={file.name}>
                      {file.name}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {formatFileSize(file.size)}
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 shrink-0"
                      onClick={() => handleDeleteStaged(file)}
                      disabled={isUploading}
                      aria-label={`Remove ${file.name}`}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </Card>
                );
              })}
            </div>
          </div>
        )}

        <UploadDropzone
          endpoint="pdfUploader"
          onDrop={handleDrop}
          onBeforeUploadBegin={handleBeforeUploadBegin}
          onUploadBegin={handleUploadBegin}
          onClientUploadComplete={handleUploadComplete}
          onUploadError={handleUploadError}
        />

        {cv_files.length > 0 && (
          <>
            <Separator />
            <div className="space-y-2">
              <h3 className="text-sm font-semibold">Uploaded Files</h3>
              <div className="space-y-2">
                {cv_files.map((file, index) => (
                  <Card key={index} className="p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">{file.name}</span>
                      <a
                        href={file.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-primary hover:underline"
                      >
                        View
                      </a>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          </>
        )}
      </CardContent>
      <CardFooter className="flex justify-between">
        <Button variant="outline" onClick={handleBack} disabled={isUploading}>
          Back
        </Button>
        <Button
          onClick={handleContinue}
          disabled={cv_files.length === 0 || isUploading}
        >
          {isUploading ? "Uploading..." : "Continue"}
        </Button>
      </CardFooter>
    </Card>
  );
}
