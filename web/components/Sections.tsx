// The full analysis: every section the app showed, in its order (tables, charts, metrics, notes).
import { marked } from "marked";
import type { Item, Section, Table } from "@/lib/data";
import Chart from "./Chart";

const block = (s: string) => marked.parse(s, { async: false }) as string;

function fmt(v: string | number | boolean | null): string {
  if (v === null) return "—";
  if (typeof v === "number") {
    const a = Math.abs(v);
    if (a !== 0 && (a < 0.0001 || a >= 1e12)) return v.toExponential(2);
    return v.toLocaleString("en-IN", { maximumFractionDigits: a < 1 ? 4 : 2 });
  }
  return String(v);
}

export function DataTable({ t, caption }: { t: Table; caption?: string }) {
  return (
    <div className="overflow-x-auto rounded border border-slate-200 dark:border-slate-700">
      <table className="min-w-full text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead className="bg-slate-50 dark:bg-slate-800">
          <tr>
            {t.columns.map((c) => (
              <th key={c} scope="col" className="px-3 py-2 text-left font-semibold">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {t.rows.map((r, i) => (
            <tr key={i} className="border-t border-slate-200 dark:border-slate-700">
              {r.map((v, j) => (
                <td key={j} className={`px-3 py-1.5 ${typeof v === "string" && v.length > 30 ? "min-w-[16rem]" : "whitespace-nowrap"}`}>
                  {fmt(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ItemView({ it, title }: { it: Item; title: string }) {
  switch (it.type) {
    case "table":
      return <DataTable t={it} caption={title} />;
    case "chart":
      return <Chart src={it.src} label={title} />;
    case "metric":
      return (
        <div className="inline-block min-w-[10rem] rounded border border-slate-200 p-3 dark:border-slate-700">
          <div className="text-xs text-slate-600 dark:text-slate-400">{it.label}</div>
          <div className="text-lg font-semibold">{it.value}</div>
        </div>
      );
    case "note":
      return (
        <div className="prose-doc text-sm text-slate-600 dark:text-slate-400" dangerouslySetInnerHTML={{ __html: block(it.text) }} />
      );
    case "text":
      return <div className="prose-doc" dangerouslySetInnerHTML={{ __html: block(it.text) }} />;
  }
}

type Card = { type: "card"; label: string; value: string; notes: string[] };
type Block = Item | { type: "cards"; cards: Card[] };

// A metric and the notes right after it (its range and grade) form a card; consecutive cards sit in a grid.
function group(items: Item[]): Block[] {
  const out: Block[] = [];
  let i = 0;
  while (i < items.length) {
    const it = items[i];
    if (it.type !== "metric") {
      out.push(it);
      i++;
      continue;
    }
    const cards: Card[] = [];
    while (i < items.length && items[i].type === "metric") {
      const m = items[i] as Extract<Item, { type: "metric" }>;
      const card: Card = { type: "card", label: m.label, value: m.value, notes: [] };
      i++;
      while (i < items.length && items[i].type === "note" && card.notes.length < 2) {
        card.notes.push((items[i] as Extract<Item, { type: "note" }>).text);
        i++;
      }
      cards.push(card);
    }
    out.push({ type: "cards", cards });
  }
  return out;
}

function Cards({ cards }: { cards: Card[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((c) => (
        <div key={c.label} className="rounded border border-slate-200 p-3 dark:border-slate-700">
          <div className="text-xs text-slate-600 dark:text-slate-400">{c.label}</div>
          <div className="text-xl font-semibold">{c.value}</div>
          {c.notes.map((n, k) => (
            <div key={k} className="prose-doc mt-1 text-xs text-slate-600 dark:text-slate-400" dangerouslySetInnerHTML={{ __html: block(n) }} />
          ))}
        </div>
      ))}
    </div>
  );
}

export default function Sections({ sections }: { sections: Section[] }) {
  return (
    <div className="space-y-8">
      {sections.map((s, i) => (
        <section key={i} className="space-y-3">
          {s.title && <h3 className="text-lg font-semibold">{s.title}</h3>}
          {group(s.items).map((b, j) =>
            b.type === "cards" ? <Cards key={j} cards={b.cards} /> : <ItemView key={j} it={b} title={s.title} />,
          )}
        </section>
      ))}
    </div>
  );
}
