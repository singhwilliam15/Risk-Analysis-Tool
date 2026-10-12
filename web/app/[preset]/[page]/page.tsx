import type { Metadata } from "next";
import Link from "next/link";
import Sections from "@/components/Sections";
import SummaryBlock from "@/components/Summary";
import { PAGES, page as loadPage, presets } from "@/lib/data";

type Params = { preset: string; page: string };

export function generateStaticParams(): Params[] {
  return presets().flatMap((p) => PAGES.map((pg) => ({ preset: p.slug, page: pg.slug })));
}

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { preset, page } = await params;
  const d = loadPage(preset, page);
  return { title: `${d.title}: ${d.preset_label}`, description: `${d.summary.status}: ${d.summary.verdict}` };
}

export default async function Page({ params }: { params: Promise<Params> }) {
  const { preset, page } = await params;
  const d = loadPage(preset, page);
  const all = presets();
  return (
    <article className="space-y-8">
      <div className="space-y-3">
        <nav aria-label="Preset" className="flex flex-wrap gap-2 text-sm">
          {all.map((p) => (
            <Link
              key={p.slug}
              href={`/${p.slug}/${page}/`}
              prefetch={false}
              aria-current={p.slug === preset ? "page" : undefined}
              className={`rounded-full border px-3 py-1 no-underline ${
                p.slug === preset
                  ? "border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900"
                  : "border-slate-300 text-slate-700 dark:border-slate-600 dark:text-slate-200"
              }`}
            >
              {p.label}
            </Link>
          ))}
        </nav>
        <nav aria-label="Pages" className="flex flex-wrap gap-x-4 gap-y-1 border-b border-slate-200 pb-2 text-sm dark:border-slate-700">
          {PAGES.map((pg) => (
            <Link
              key={pg.slug}
              href={`/${preset}/${pg.slug}/`}
              prefetch={false}
              aria-current={pg.slug === page ? "page" : undefined}
              className={pg.slug === page ? "font-semibold text-slate-900 dark:text-white" : "text-slate-600 dark:text-slate-300"}
            >
              {pg.label}
            </Link>
          ))}
        </nav>
      </div>

      <header>
        <h1 className="text-3xl font-bold">{d.title}</h1>
        <p className="text-slate-600 dark:text-slate-400">{d.preset_label}</p>
      </header>

      {d.stale && (
        <p role="status" className="rounded border border-amber-400 bg-amber-50 p-3 text-sm dark:bg-amber-950">
          Stale: the last build of this preset failed, so these are the results of {d.built}.
        </p>
      )}

      <SummaryBlock s={d.summary} />

      {page === "promoter-pledge-governance" && (
        <aside className="rounded border border-slate-300 p-4 text-sm dark:border-slate-600">
          <p>
            <strong>Why “not checked” here.</strong> NSE&apos;s terms do not allow this project to republish its pledge,
            surveillance or price-band lists, so the website shows no pledge data for the presets. In the{" "}
            <a href={d.app_link}>live app</a> you can upload the files you download from NSE yourself. The tested
            evidence for the pledge signals is on the <Link href="/evidence/">Evidence</Link> page.
          </p>
        </aside>
      )}

      <section aria-labelledby="full" className="space-y-6 border-t border-slate-200 pt-6 dark:border-slate-700">
        <h2 id="full" className="text-2xl font-semibold">
          Full analysis
        </h2>
        <Sections sections={d.sections} />
      </section>

      <p className="text-sm text-slate-600 dark:text-slate-400">
        {d.data_note} Built {d.built}. <a href={d.app_link}>Open this page in the live app</a> to change the inputs.
      </p>
    </article>
  );
}
