// After `npm run build`: every page exists, every preset page opens with its verdict, and no NSE list is published.
import fs from "node:fs";
import path from "node:path";

const OUT = path.resolve("out");
const DATA = path.resolve("public", "data");
const PAGES = ["overview", "market", "liquidity", "credit", "concentration-factors", "promoter-pledge-governance",
  "integrated-stress", "decisions", "trust"];
const errors = [];
const html = (p) => {
  const f = path.join(OUT, p, "index.html");
  if (!fs.existsSync(f)) { errors.push(`missing ${p}/index.html`); return ""; }
  return fs.readFileSync(f, "utf-8");
};
const decode = (s) => s.replace(/&#x27;|&apos;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, "&").replace(/<!-- -->/g, "");

for (const p of ["", "evidence", "methodology", "glossary", "about"]) html(p);
const presets = JSON.parse(fs.readFileSync(path.join(DATA, "presets.json"), "utf-8"));
for (const { slug } of presets) {
  for (const pg of PAGES) {
    const d = JSON.parse(fs.readFileSync(path.join(DATA, slug, `${pg}.json`), "utf-8"));
    const text = decode(html(`${slug}/${pg}`).replace(/<[^>]+>/g, ""));
    const first = d.summary.verdict.replace(/\*\*/g, "").slice(0, 40);
    if (!text.includes(d.summary.status) || !text.includes(first)) errors.push(`${slug}/${pg}: verdict not found`);
  }
}
// No NSE lists: nothing under the data folder may be a disclosure file
const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(path.join(d, e.name)) : [e.name]));
for (const f of walk(OUT)) if (/^(pledges|sec_list|fo_secban|surveillance|ratings)_\d+\.csv$/.test(f)) errors.push(`NSE file published: ${f}`);

console.log(`${presets.length} presets × ${PAGES.length} pages checked; ${errors.length} problem(s)`);
if (errors.length) { console.error(errors.join("\n")); process.exit(1); }
