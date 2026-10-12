import type { Metadata } from "next";
import { REPO_URL, doc } from "@/lib/data";
import { render } from "@/lib/markdown";

export const metadata: Metadata = { title: "Methodology", description: "Every formula, test and assumption, with references." };

export default function Methodology() {
  return <article className="prose-doc max-w-none" dangerouslySetInnerHTML={{ __html: render(doc("methodology.md"), REPO_URL) }} />;
}
