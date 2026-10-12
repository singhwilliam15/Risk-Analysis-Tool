import Link from "next/link";
import { StatusWord } from "@/components/Summary";
import { APP_URL, DEFAULT_PRESET, PAGES, REPO_URL, evidence, page } from "@/lib/data";

export default function Home() {
  const overview = page(DEFAULT_PRESET, "overview");
  const pillars = PAGES.filter((p) => p.slug !== "overview").map((p) => ({ ...p, d: page(DEFAULT_PRESET, p.slug) }));
  const tested = evidence().signals.filter((s) => s.badge.startsWith("Tested · works") || s.badge.startsWith("Tested · weaker"));
  return (
    <div className="space-y-12">
      <section className="space-y-4">
        <h1 className="text-3xl font-bold sm:text-4xl">How risky is this stock or portfolio, and how sure are we?</h1>
        <p className="max-w-3xl text-lg text-slate-700 dark:text-slate-300">
          Market, liquidity, credit, concentration and promoter-pledge risk for Indian and US stocks, linked through one
          stress engine. Every headline number has a range and an A–D trust grade, and every warning signal shows its
          tested record on every NSE stock.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link href={`/${DEFAULT_PRESET}/overview/`} className="rounded bg-slate-900 px-4 py-2 text-white no-underline dark:bg-slate-100 dark:text-slate-900">
            See the results
          </Link>
          <a href={APP_URL} className="rounded border border-slate-400 px-4 py-2 no-underline">
            Try it live with your own stocks
          </a>
          <a href={REPO_URL} className="rounded border border-slate-400 px-4 py-2 no-underline">
            Source code
          </a>
        </div>
      </section>

      <section className="space-y-4" aria-labelledby="today">
        <h2 id="today" className="text-2xl font-semibold">
          The default portfolio today
        </h2>
        <p className="text-slate-600 dark:text-slate-400">
          {overview.preset_label}. {overview.summary.question}
        </p>
        <p className="text-xl">
          <StatusWord status={overview.summary.status} />: {overview.summary.verdict}
        </p>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {pillars.map((p) => (
            <li key={p.slug} className="rounded border border-slate-200 p-4 dark:border-slate-700">
              <Link href={`/${DEFAULT_PRESET}/${p.slug}/`} prefetch={false} className="font-semibold">
                {p.label}
              </Link>
              <p className="mt-1">
                <StatusWord status={p.d.summary.status} />
              </p>
              <p className="mt-1 text-sm text-slate-700 dark:text-slate-300">{p.d.summary.verdict}</p>
            </li>
          ))}
        </ul>
        <p className="text-sm text-slate-600 dark:text-slate-400">{overview.data_note}</p>
      </section>

      <section className="space-y-3" aria-labelledby="evidence">
        <h2 id="evidence" className="text-2xl font-semibold">
          Signals that passed a pre-registered test
        </h2>
        <p className="text-slate-600 dark:text-slate-400">
          Lift = how many times more often a flagged NSE stock fell 50% or more within 12 months than the average stock.
        </p>
        <ul className="space-y-2">
          {tested.map((s) => (
            <li key={s.id}>
              <strong>{s.signal}</strong>: {s.lift} ({s.window}). <span className="text-slate-600 dark:text-slate-400">{s.badge}</span>
            </li>
          ))}
        </ul>
        <Link href="/evidence/">All signals, including the ones that failed</Link>
      </section>
    </div>
  );
}
