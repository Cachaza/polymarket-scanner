import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-xl border border-line bg-white px-4 text-sm text-ink outline-none transition focus:border-accent",
        className,
      )}
      {...props}
    />
  );
}
