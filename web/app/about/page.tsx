import type { Metadata } from "next";
import Link from "next/link";
import { APP_URL, REPO_URL } from "@/lib/data";

export const metadata: Metadata = { title: "About", description: "What this project is, how it is built and its limits." };

export default function About() {
  return (
    <article className="prose-doc max-w-3xl">
      <h1>About</h1>
      <p>
        The Risk Analysis Tool measures the risk of an Indian or US stock or portfolio across five pillars: market,
        liquidity, credit, concentration and factors, and promoter pledges and governance. It links them through one
        stress engine. It is an educational project built during a PGDM in Banking and Financial Services at IMI Delhi.
      </p>
      <h2>How this website is made</h2>
      <ul>
        <li>
          The <a href={REPO_URL}>Python engine</a> computes every number. This site does no calculations: a script runs
          the <a href={APP_URL}>live app</a> on each preset and saves what each page shows, which is then published as
          static pages.
        </li>
        <li>The presets use the app&apos;s demo snapshot of Yahoo Finance prices (refreshed after each NSE session); the site is rebuilt weekly.</li>
        <li>
          No NSE data is republished. NSE&apos;s terms reserve redistribution for its written permission, so pledge,
          surveillance and price-band lists are not on this site. The tested evidence uses only derived statistics.
        </li>
      </ul>
      <h2>Rules the project keeps</h2>
      <ul>
        <li>Point-in-time data: a filing counts only from the day it became public.</li>
        <li>No invented data: what is missing is shown as missing, and every assumption is labelled.</li>
        <li>Tests are pre-registered and committed before results are computed. Failed tests are reported too.</li>
      </ul>
      <h2>Limits</h2>
      <p>
        Long-only, single-currency portfolios. Merton default probabilities are risk-neutral. Warning signals were
        tested on 2016–2024 NSE data only. See the <Link href="/methodology/">methodology</Link> for the full list.
      </p>
      <p>Not investment advice.</p>
    </article>
  );
}
