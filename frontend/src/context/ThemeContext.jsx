import { createContext, useContext, useEffect, useState } from "react";

const ThemeContext = createContext("light");

const themes = {
  dark: {
    name: "dark",
    background: "#212121",       // ChatGPT dark
    surface: "#2f2f2f",
    card: "#343541",
    text: "#ECECF1",
    secondaryText: "#A0A0A0",
    primary: "#003D7C",          // NUS Blue
    accent: "#EF7C00",           // NUS Orange
    border: "#444654",
  },

  light: {
    name: "light",
    background: "#FFFFFF",
    surface: "#F7F7F8",
    card: "#FFFFFF",
    text: "#202123",
    secondaryText: "#6B7280",
    primary: "#003D7C",
    accent: "#EF7C00",
    border: "#E5E7EB",
  },
};

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState("light");

  useEffect(() => {
    const current = themes[theme];

    Object.entries(current).forEach(([key, value]) => {
      document.documentElement.style.setProperty(
        `--${key}`,
        value
      );
    });

    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const toggleTheme = () =>
    setTheme((t) => (t === "dark" ? "light" : "dark"));

  return (
    <ThemeContext.Provider
      value={{
        theme,
        themeConfig: themes[theme],
        toggleTheme,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);

  if (!ctx) {
    throw new Error(
      "useTheme must be used within ThemeProvider"
    );
  }

  return ctx;
}