// theme toggle switch - ios-style slider for dark/light mode

"use client";

import { Moon, Sun } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { useTheme } from "@/lib/theme-context";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="flex items-center gap-1.5">
      <Moon className="h-3 w-3 text-muted-foreground" />
      <Switch
        checked={theme === "light"}
        onCheckedChange={toggleTheme}
        aria-label="Toggle theme"
        size="sm"
      />
      <Sun className="h-3 w-3 text-muted-foreground" />
    </div>
  );
}
