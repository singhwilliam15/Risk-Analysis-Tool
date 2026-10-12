// Markdown → HTML at build time. Numbered headings ("## 12. Event…", "### 12.3 …") get ids "s-12", "s-12-3", so the
// glossary can link to a methodology section.
import { marked, type Tokens } from "marked";

const slug = (text: string) =>
  text.toLowerCase().replace(/<[^>]+>/g, "").replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "-");

export function render(md: string, repoBase: string): string {
  const renderer = new marked.Renderer();
  renderer.heading = ({ tokens, depth, text }: Tokens.Heading) => {
    const inner = marked.Parser.parseInline(tokens);
    const num = text.match(/^(\d+(?:\.\d+)*)\.?\s/);
    const id = num ? `s-${num[1].replace(/\./g, "-")}` : slug(text);
    return `<h${depth} id="${id}">${inner}</h${depth}>`;
  };
  // relative links point into the repository on GitHub, as they do in the docs
  renderer.link = ({ href, title, tokens }: Tokens.Link) => {
    const inner = marked.Parser.parseInline(tokens);
    const url = /^(https?:|#|mailto:)/.test(href) ? href : `${repoBase}/blob/main/docs/${href}`;
    return `<a href="${url}"${title ? ` title="${title}"` : ""}>${inner}</a>`;
  };
  renderer.image = ({ href, text }: Tokens.Image) => {
    const url = /^https?:/.test(href) ? href : `${repoBase}/raw/main/docs/${href}`;
    return `<img src="${url}" alt="${text}" loading="lazy" />`;
  };
  return marked.parse(md, { renderer, gfm: true, async: false }) as string;
}
