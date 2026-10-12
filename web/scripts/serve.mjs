// Serve out/ under the GitHub Pages base path, for local checks: node scripts/serve.mjs [port]
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import zlib from "node:zlib";

const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "/Risk-Analysis-Tool";
const ROOT = path.resolve("out");
const PORT = Number(process.argv[2] ?? 8600);
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
  ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".txt": "text/plain", ".md": "text/markdown" };

http.createServer((req, res) => {
  let url = decodeURIComponent((req.url ?? "/").split("?")[0]);
  if (!url.startsWith(BASE)) { res.writeHead(302, { Location: `${BASE}/` }); return res.end(); }
  url = url.slice(BASE.length) || "/";
  let file = path.join(ROOT, url);
  if (!file.startsWith(ROOT)) { res.writeHead(403); return res.end(); }
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, "index.html");
  if (!fs.existsSync(file)) { res.writeHead(404); return res.end("not found"); }
  const gzip = /gzip/.test(req.headers["accept-encoding"] ?? ""); // GitHub Pages compresses too
  res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] ?? "application/octet-stream",
    ...(gzip ? { "Content-Encoding": "gzip" } : {}) });
  const stream = fs.createReadStream(file);
  (gzip ? stream.pipe(zlib.createGzip()) : stream).pipe(res);
}).listen(PORT, () => console.log(`http://localhost:${PORT}${BASE}/`));
