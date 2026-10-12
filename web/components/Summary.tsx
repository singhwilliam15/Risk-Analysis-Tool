// The Phase 4 summary: question, status word (never colour alone), verdict, facts, grades, action, evidence, method.
import { marked } from "marked";
import type { Chip, Grade, Summary } from "@/lib/data";

const DOT: Record<string, string> = { Clear: "bg-emerald-500", Watch: "bg-amber-500", Warning: "bg-red-600" };
const inline = (s: string) => marked.parseInline(s, { async: false }) as string;

export function StatusWord({ status }: { status: string }) {
  return (
    <span className="inline-flex items-center gap-2 font-semibold">
      <span aria-hidden className={`inline-block h-3 w-3 rounded-full ${DOT[status] ?? "bg-slate-400"}`} />
      {status}
    </span>
  );
}

export function GradeBadge({ g }: { g: Grade }) {
  return (
    <details className="rounded border border-slate-300 px-3 py-1 text-sm dark:border-slate-600">
      <summary className="cursor-pointer select-none">
        {g.label}: grade <strong>{g.grade}</strong>
      </summary>
      <p className="mt-2 max-w-md text-slate-600 dark:text-slate-300">
        <strong>{g.name}</strong>: {g.reasons.length ? g.reasons.join("; ") : "no deductions"}
      </p>
    </details>
  );
}

export function EvidenceChip({ c }: { c: Chip }) {
  const plain = c.signal.split(" (")[0];
  return (
    <p className="text-sm text-slate-600 dark:text-slate-300">
      Evidence for “{plain}”: <strong>{c.badge}</strong>
      {c.lift !== "—" && <>. Flagged stocks crashed {c.lift} as often as the average stock ({c.window})</>}.
    </p>
  );
}

export default function SummaryBlock({ s }: { s: Summary }) {
  return (
    <section aria-label="Summary" className="space-y-3">
      <p className="font-semibold text-slate-700 dark:text-slate-200">{s.question}</p>
      <h2 className="text-xl font-semibold leading-snug sm:text-2xl">
        <StatusWord status={s.status} />: <span dangerouslySetInnerHTML={{ __html: inline(s.verdict) }} />
      </h2>
      <ul className="list-disc space-y-1 pl-5">
        {s.facts.map((f) => (
          <li key={f.label}>
            <strong>{f.label}:</strong> {f.value}
            {f.so_what && <span className="text-slate-600 dark:text-slate-300"> — {f.so_what}</span>}
          </li>
        ))}
      </ul>
      {s.grades.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {s.grades.map((g) => (
            <GradeBadge key={g.label} g={g} />
          ))}
        </div>
      )}
      <p>
        <strong>What to do:</strong> <span dangerouslySetInnerHTML={{ __html: inline(s.action) }} />
      </p>
      {s.chips.map((c) => (
        <EvidenceChip key={c.id} c={c} />
      ))}
      {s.methods.map((m) => (
        <p key={m} className="text-sm text-slate-500 dark:text-slate-400">
          Method: {m}
        </p>
      ))}
    </section>
  );
}
