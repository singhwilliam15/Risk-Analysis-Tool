import type { Metadata, Viewport } from "next";
import Header from "@/components/Header";
import { REPO_URL } from "@/lib/data";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Risk Analysis Tool", template: "%s · Risk Analysis Tool" },
  description:
    "Market, liquidity, credit, concentration and promoter-pledge risk for Indian and US stocks, with tested evidence and plain-language verdicts.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1 };

// Set the theme before the first paint: the saved choice, else the system setting.
const THEME = `try{var t=localStorage.getItem("theme");if(t==="dark"||(!t&&matchMedia("(prefers-color-scheme: dark)").matches))document.documentElement.classList.add("dark")}catch(e){if(matchMedia("(prefers-color-scheme: dark)").matches)document.documentElement.classList.add("dark")}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME }} />
      </head>
      <body className="font-sans">
        <a href="#main" className="sr-only focus:not-sr-only">
          Skip to content
        </a>
        <Header />
        <main id="main" className="mx-auto max-w-6xl px-4 py-8">
          {children}
        </main>
        <footer className="mx-auto max-w-6xl border-t border-slate-200 px-4 py-6 text-sm text-slate-600 dark:border-slate-700 dark:text-slate-400">
          An educational project (PGDM BFS, IMI Delhi). Not investment advice. Numbers come from the{" "}
          <a href={REPO_URL}>open-source engine</a>; no NSE data is republished here.
        </footer>
      </body>
    </html>
  );
}
