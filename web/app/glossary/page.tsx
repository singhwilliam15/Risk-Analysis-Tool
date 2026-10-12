import type { Metadata } from "next";
import Link from "next/link";
import { glossary, sectionAnchor } from "@/lib/data";

export const metadata: Metadata = { title: "Glossary", description: "Every term in plain words, with its technical name." };

export default function Glossary() {
  const terms = glossary();
  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold">Glossary</h1>
      <p className="max-w-3xl text-slate-700 dark:text-slate-300">
        Every page uses plain words first and the technical term in brackets. The sections link to the methodology,
        which gives the formulas, sources and tests.
      </p>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 dark:bg-slate-800">
            <tr>
              {["In plain words", "Technical term", "What it means", "Methodology"].map((h) => (
                <th key={h} scope="col" className="px-3 py-2 text-left font-semibold">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {terms.map((t) => (
              <tr key={t.technical} className="border-t border-slate-200 align-top dark:border-slate-700">
                <td className="px-3 py-2 font-medium">{t.plain}</td>
                <td className="px-3 py-2">{t.technical}</td>
                <td className="px-3 py-2">{t.definition}</td>
                <td className="px-3 py-2">
                  <Link href={`/methodology/${sectionAnchor(t.section)}`}>{t.section}</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
