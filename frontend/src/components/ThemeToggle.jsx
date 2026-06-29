import React from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/context/ThemeContext";

export default function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button
      type="button"
      onClick={toggle}
      data-testid="theme-toggle"
      aria-label="Toggle theme"
      className="relative inline-flex h-9 w-9 items-center justify-center rounded-full border border-border bg-background/60 text-foreground transition-colors hover:bg-accent"
    >
      <Sun className={`h-4 w-4 transition-all ${theme === "dark" ? "scale-0 rotate-90 opacity-0" : "scale-100 rotate-0 opacity-100"}`} />
      <Moon className={`absolute h-4 w-4 transition-all ${theme === "dark" ? "scale-100 rotate-0 opacity-100" : "scale-0 -rotate-90 opacity-0"}`} />
    </button>
  );
}
