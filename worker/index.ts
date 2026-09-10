// SkillTown edge entry point.
//
// Serves the Godot Web build from Workers Assets and answers /api/v1 on the
// same origin, which is what the client relies on: config.gd reads its base URL
// from window.location.origin.
//
// The learning API itself is not implemented here yet. Until it is, API calls
// return a labelled 503 in the same error envelope the client already handles,
// so the page fails honestly instead of looking broken.

interface Env {
  ASSETS: Fetcher;
  API_ORIGIN?: string;
}

const API_PREFIXES = ["/api/", "/health"];

function isApiPath(pathname: string): boolean {
  return API_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(prefix));
}

function errorEnvelope(code: string, message: string, status: number): Response {
  return Response.json(
    {
      error: {
        code,
        message,
        request_id: `edge-${Date.now().toString(36)}`,
        retryable: status >= 500,
      },
    },
    { status },
  );
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (!isApiPath(url.pathname)) {
      return env.ASSETS.fetch(request);
    }

    // Optional escape hatch: point API_ORIGIN at a backend that runs the Python
    // service, and this Worker becomes a same-origin proxy in front of it.
    if (env.API_ORIGIN) {
      const target = new URL(url.pathname + url.search, env.API_ORIGIN);
      return fetch(new Request(target, request));
    }

    return errorEnvelope(
      "api_not_deployed",
      "学习 API 尚未部署到这个环境；页面可以加载，但还不能创建会话。",
      503,
    );
  },
} satisfies ExportedHandler<Env>;
