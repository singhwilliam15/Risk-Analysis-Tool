/** Static export for GitHub Pages; the site does no calculations (data from site_data/build.py). */
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "/Risk-Analysis-Tool";

export default {
  output: "export",
  basePath,
  trailingSlash: true,
  images: { unoptimized: true },
  env: { NEXT_PUBLIC_BASE_PATH: basePath },
};
