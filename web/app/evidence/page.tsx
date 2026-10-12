import type { Metadata } from "next";
import { DataTable } from "@/components/Sections";
import { REPO_URL, doc, evidence } from "@/lib/data";
import { render } from "@/lib/markdown";

export const metadata: Metadata = { title: "Evidence", description: "Every warning signal and its tested record on NSE stocks." };

export default function EvidencePage() {
  const e = evidence();
  const signals = {
    type: "table" as const,
    truncated: false,
    columns: ["Signal", "Evidence", "Tested lift (90% range)", "Among stocks not down 30%", "Test window (NSE month-ends)"],
    rows: e.signals.map((s) => [s.signal, s.badge, s.lift, s.beyond_momentum, s.window]),
  };
  return (
    <div className="space-y-10">
      <header className="space-y-3">
        <h1 className="text-3xl font-bold">Evidence</h1>
        <p className="max-w-3xl text-slate-700 dark:text-slate-300">
          Every signal the tool shows, with its tested record. Tests were pre-registered: rules fixed and committed
          before the results were computed, then run out of sample on every NSE stock, delisted ones included. Lift =
          how many times more often a flagged stock fell 50% or more within 12 months than the average stock.
        </p>
        <p>
          The full write-up is the research note,{" "}
          <a href={`${REPO_URL}/blob/main/docs/research_note.md`}>
            “What predicts 50% crashes in Indian stocks? Evidence from every NSE stock, 2016–2024”
          </a>{" "}
          (<a href={`${REPO_URL}/raw/main/docs/research_note.pdf`}>PDF</a>).
        </p>
      </header>
      <section className="space-y-3">
        <h2 className="text-2xl font-semibold">Every signal, by strength of evidence</h2>
        <DataTable t={signals} caption="Signals and their tested record" />
        <p className="text-sm text-slate-600 dark:text-slate-400">
          Badges follow written rules (methodology §15.5). “Weaker than momentum”: it warns, but does not beat “down 30%
          in six months”.
        </p>
      </section>
      <section className="space-y-3">
        <h2 className="text-2xl font-semibold">Close to the lenders&apos; selling price (margin-trigger distance, 2022–24)</h2>
        <p className="max-w-3xl">
          Among stocks whose promoters encumbered 20% or more of their shares, being within 10% of the pledge
          margin-call trigger is <strong>not</strong> confirmed to add to the pledge level: the crash-rate ratio&apos;s 90%
          range includes 1.
        </p>
        <DataTable t={e.margin_trigger.ratio} caption="Crash-rate ratio, close vs far from the trigger" />
        <DataTable t={e.margin_trigger.bins} caption="Crash rate by distance to the trigger" />
      </section>
      <section className="space-y-3">
        <h2 className="text-2xl font-semibold">Case studies: did it see the collapses coming?</h2>
        <DataTable t={e.case_tally} caption="Hits and false alarms on the case dates" />
      </section>
      <section className="prose-doc max-w-none border-t border-slate-200 pt-6 dark:border-slate-700">
        <div dangerouslySetInnerHTML={{ __html: render(doc("case_studies.md"), REPO_URL) }} />
      </section>
    </div>
  );
}
