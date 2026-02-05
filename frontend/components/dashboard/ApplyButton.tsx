"use client";

import { Button } from "@/components/ui/button";
import { ExternalLink } from "lucide-react";

interface ApplyButtonProps {
  url: string;
}

export function ApplyButton({ url }: ApplyButtonProps) {
  return (
    <Button asChild>
      <a href={url} target="_blank" rel="noopener noreferrer">
        <ExternalLink className="mr-2 h-4 w-4" />
        Apply Now
      </a>
    </Button>
  );
}
