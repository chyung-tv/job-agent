"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Copy, Check } from "lucide-react";

interface CoverLetterViewProps {
  content: string;
}

export function CoverLetterView({ content }: CoverLetterViewProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  return (
    <div className="relative">
      <Button
        variant="outline"
        size="sm"
        className="absolute right-2 top-2"
        onClick={handleCopy}
      >
        {copied ? (
          <>
            <Check className="mr-1 h-3 w-3" />
            Copied
          </>
        ) : (
          <>
            <Copy className="mr-1 h-3 w-3" />
            Copy
          </>
        )}
      </Button>
      <div className="max-h-96 overflow-y-auto rounded-lg bg-muted/50 p-4 pr-24">
        <p className="whitespace-pre-wrap text-sm">{content}</p>
      </div>
    </div>
  );
}
