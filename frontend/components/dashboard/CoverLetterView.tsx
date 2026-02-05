"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Copy, Check } from "lucide-react";
import { cn } from "@/lib/utils";

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
        className={cn(
          "absolute right-3 top-3 z-10 gap-1.5 transition-all",
          copied && "border-green-500/50 bg-green-500/10 text-green-600 dark:text-green-400"
        )}
        onClick={handleCopy}
      >
        {copied ? (
          <>
            <Check className="h-3.5 w-3.5" />
            Copied!
          </>
        ) : (
          <>
            <Copy className="h-3.5 w-3.5" />
            Copy
          </>
        )}
      </Button>
      <ScrollArea className="h-[400px] rounded-lg border bg-muted/30 p-4 pr-16">
        <div className="whitespace-pre-wrap text-sm leading-relaxed">
          {content}
        </div>
      </ScrollArea>
    </div>
  );
}
