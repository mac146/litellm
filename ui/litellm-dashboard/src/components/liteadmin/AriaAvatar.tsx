import { cn } from "@/lib/cva.config";
import { MousePointer2 } from "lucide-react";

export function AriaAvatar({ size = 28, className }: { size?: number; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn("inline-flex shrink-0 items-center justify-center text-foreground", className)}
      style={{ width: size, height: size }}
    >
      <MousePointer2 style={{ width: Math.round(size * 0.7), height: Math.round(size * 0.7) }} strokeWidth={2} />
    </span>
  );
}
