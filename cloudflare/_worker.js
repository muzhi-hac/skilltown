// Cloudflare Pages advanced-mode worker.
//
// Pages hosts the static Godot Web build. It cannot run the FastAPI backend
// (no Python runtime, no persistent SQLite), so /api/*, /health and /ready are proxied
// to API_ORIGIN. The browser therefore still sees one origin, which is what the
// client relies on: config.gd reads window.location.origin.
//
// Deploy copies this file into the build directory; see tools/deploy_pages.sh.
const API_PREFIXES = ["/api/", "/health", "/ready"];

function isApiPath(pathname) {
  return API_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(prefix));
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!isApiPath(url.pathname)) {
      return env.ASSETS.fetch(request);
    }
    if (!env.API_ORIGIN) {
      return Response.json(
        {
          error: {
            code: "api_origin_missing",
            message: "Pages 项目未配置 API_ORIGIN，后端不可用。",
            request_id: "pages-proxy",
            retryable: false,
          },
        },
        { status: 503 },
      );
    }
    const target = new URL(url.pathname + url.search, env.API_ORIGIN);
    // Preserve method, headers (including Authorization) and body.
    return fetch(new Request(target, request));
  },
};
