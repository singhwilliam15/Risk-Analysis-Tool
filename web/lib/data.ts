// Read the JSON written by site_data/build.py at build time. The site does no calculations.
import fs from "node:fs";
import path from "node:path";

const DATA = path.join(process.cwd(), "public", "data");

export type Fact = { label: string; value: string; so_what: string };
export type Grade = { label: string; name: string; grade: string; reasons: string[] };
export type Chip = { id: string; signal: string; badge: string; lift: string; window: string; beyond_momentum: string };
export type Summary = {
  question: string; status: "Clear" | "Watch" | "Warning"; verdict: string; facts: Fact[]; grades: Grade[];
  action: string; methods: string[]; chips: Chip[];
};
export type Table = { type: "table"; columns: string[]; rows: (string | number | boolean | null)[][]; truncated: boolean };
export type Item =
  | Table
  | { type: "chart"; src: string }
  | { type: "metric"; label: string; value: string }
  | { type: "note"; text: string }
  | { type: "text"; text: string };
export type Section = { title: string; items: Item[] };
export type PageData = {
  preset: string; preset_label: string; page: string; title: string; app_link: string; summary: Summary;
  sections: Section[]; data_note: string; built: string; stale: boolean; stale_reason?: string;
};
export type Preset = { slug: string; label: string; kind: string; stale: boolean };
export type Signal = { id: string; signal: string; badge: string; lift: string; beyond_momentum: string; window: string; note: string };
export type Evidence = {
  signals: Signal[];
  margin_trigger: { ratio: Table; bins: Table };
  case_tally: Table;
  decisions: Record<string, Record<string, unknown>>;
};
export type Term = { plain: string; technical: string; definition: string; section: string };

// site page slug → nav label (the app's pages, in the app's order)
export const PAGES: { slug: string; label: string }[] = [
  { slug: "overview", label: "Overview" },
  { slug: "market", label: "Market" },
  { slug: "liquidity", label: "Liquidity" },
  { slug: "credit", label: "Credit" },
  { slug: "concentration-factors", label: "Concentration & Factors" },
  { slug: "promoter-pledge-governance", label: "Promoter Pledge & Governance" },
  { slug: "integrated-stress", label: "Integrated Stress" },
  { slug: "decisions", label: "Decisions" },
  { slug: "trust", label: "Trust" },
];
export const DEFAULT_PRESET = "portfolio";
export const APP_URL = "https://risk-analysis-tool.streamlit.app/";
export const REPO_URL = "https://github.com/singhwilliam15/Risk-Analysis-Tool";

function read<T>(...parts: string[]): T {
  return JSON.parse(fs.readFileSync(path.join(DATA, ...parts), "utf-8")) as T;
}

export const presets = (): Preset[] => read<Preset[]>("presets.json");
export const page = (preset: string, slug: string): PageData => read<PageData>(preset, `${slug}.json`);
export const evidence = (): Evidence => read<Evidence>("evidence.json");
export const glossary = (): Term[] => read<Term[]>("glossary.json");
export const doc = (name: string): string => fs.readFileSync(path.join(DATA, "docs", name), "utf-8");

// "§12.3" → "#s-12-3" on the methodology page
export const sectionAnchor = (section: string): string => `#s-${section.replace("§", "").replace(/\./g, "-")}`;
