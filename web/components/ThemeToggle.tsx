"use client";
// Light/dark switch. Follows the system setting until the reader chooses; the choice is remembered when storage works.
import { useEffect, useState } from "react";

export default function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => setDark(document.documentElement.classList.contains("dark")), []);
  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {
      /* storage blocked: the switch still works for this page */
    }
  };
  return (
    <button
      type="button"
      onClick={toggle}
      className="rounded border border-slate-300 px-2 py-1 text-sm dark:border-slate-600"
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
    >
      {dark ? "Light" : "Dark"}
    </button>
  );
}
