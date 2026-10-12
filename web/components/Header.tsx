import Link from "next/link";
import { APP_URL } from "@/lib/data";
import ThemeToggle from "./ThemeToggle";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/portfolio/overview/", label: "Results" },
  { href: "/evidence/", label: "Evidence" },
  { href: "/methodology/", label: "Methodology" },
  { href: "/glossary/", label: "Glossary" },
  { href: "/about/", label: "About" },
];

export default function Header() {
  return (
    <header className="border-b border-slate-200 dark:border-slate-700">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="text-lg font-bold">
          Risk Analysis Tool
        </Link>
        <nav aria-label="Main" className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} prefetch={false} className="hover:underline">
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <a href={APP_URL} className="rounded bg-slate-900 px-3 py-1 text-sm text-white dark:bg-slate-100 dark:text-slate-900">
            Try it live
          </a>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
