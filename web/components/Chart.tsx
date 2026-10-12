"use client";
// A Plotly figure from the app. The figure (a JSON file) and Plotly itself load only when the chart scrolls into view,
// so they cost nothing on first paint; styled for light and dark.
import { useEffect, useRef, useState } from "react";

type Figure = { data: unknown[]; layout: Record<string, unknown> };

const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export default function Chart({ src, label }: { src: string; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver((e) => e[0].isIntersecting && setVisible(true), { rootMargin: "300px" });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (!visible || !ref.current) return;
    let cancelled = false;
    const el = ref.current;
    let figure: Figure | null = null;
    const draw = async () => {
      const [Plotly, fig] = await Promise.all([
        import("plotly.js-dist-min").then((m) => m.default),
        figure ?? fetch(`${BASE}/data/${src}`).then((r) => r.json() as Promise<Figure>),
      ]);
      figure = fig;
      if (cancelled) return;
      const dark = document.documentElement.classList.contains("dark");
      const ink = dark ? "#e2e8f0" : "#1e293b";
      const grid = dark ? "#334155" : "#e2e8f0";
      const layout = {
        ...figure.layout,
        autosize: true,
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: ink, family: "system-ui, sans-serif" },
        xaxis: { ...((figure.layout.xaxis as object) ?? {}), gridcolor: grid, zerolinecolor: grid },
        yaxis: { ...((figure.layout.yaxis as object) ?? {}), gridcolor: grid, zerolinecolor: grid },
        margin: { l: 50, r: 20, t: 50, b: 50 },
      };
      await Plotly.react(el, figure.data, layout, { responsive: true, displaylogo: false });
    };
    draw();
    const obs = new MutationObserver(() => draw()); // redraw when the theme changes
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => {
      cancelled = true;
      obs.disconnect();
    };
  }, [visible, src]);

  return (
    <div
      ref={ref}
      role="img"
      aria-label={`Chart: ${label}`}
      className="min-h-[360px] w-full rounded border border-slate-200 dark:border-slate-700"
    >
      {!visible && <p className="p-4 text-sm text-slate-700 dark:text-slate-300">Loading chart…</p>}
    </div>
  );
}
