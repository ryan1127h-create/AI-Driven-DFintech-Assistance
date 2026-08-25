import { Sun, Moon } from "lucide-react";
import { useTheme } from "../context/ThemeContext";
import { cn } from "../utils/cn";

export default function ThemeToggle({ className }) {
  const { theme, toggleTheme } = useTheme();
  return (
    <button
      onClick={toggleTheme}
      className={cn(
        "flex h-9 w-9 items-center justify-center rounded-lg border transition-all",
        "border-app-input text-app-secondary hover:text-app-primary hover:bg-app-hover",
        className,
      )}
      title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
    >
      {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}
