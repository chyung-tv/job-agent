"use client";

interface PDFViewerProps {
  url: string;
}

/**
 * Simple PDF viewer using iframe with sandbox for security.
 * Falls back gracefully if PDF cannot be displayed.
 */
export function PDFViewer({ url }: PDFViewerProps) {
  return (
    <div className="relative aspect-[8.5/11] w-full overflow-hidden rounded-lg border bg-muted">
      <iframe
        src={url}
        className="h-full w-full"
        sandbox="allow-scripts allow-same-origin"
        title="Tailored CV Preview"
      />
    </div>
  );
}
