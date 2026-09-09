const ALLOWED_HOSTS = new Set([
  "www1.hkexnews.hk",
  "www.hkexnews.hk",
]);

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Expose-Headers": "Content-Type, Content-Length, Content-Disposition, ETag, Last-Modified",
  };
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...corsHeaders(),
    },
  });
}

export default {
  async fetch(request) {
    const requestUrl = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }

    if (requestUrl.pathname === "/health") {
      return jsonResponse({
        ok: true,
        service: "hkex-pdf-proxy",
        version: "1.0.0",
      });
    }

    if (!["GET", "HEAD"].includes(request.method)) {
      return jsonResponse({ error: "Method not allowed" }, 405);
    }

    const source = requestUrl.searchParams.get("url");
    if (!source) {
      return jsonResponse({ error: "Missing url query parameter" }, 400);
    }

    let upstreamUrl;
    try {
      upstreamUrl = new URL(source);
    } catch {
      return jsonResponse({ error: "Invalid URL" }, 400);
    }

    if (upstreamUrl.protocol !== "https:") {
      return jsonResponse({ error: "Only HTTPS URLs are allowed" }, 400);
    }

    if (!ALLOWED_HOSTS.has(upstreamUrl.hostname)) {
      return jsonResponse({ error: "Host not allowed" }, 403);
    }

    if (!upstreamUrl.pathname.toLowerCase().endsWith(".pdf")) {
      return jsonResponse({ error: "Only PDF paths are allowed" }, 403);
    }

    const upstreamHeaders = new Headers({
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
      "Referer": "https://www1.hkexnews.hk/",
      "Accept": "application/pdf,*/*",
    });

    const upstreamResponse = await fetch(upstreamUrl.toString(), {
      method: request.method,
      headers: upstreamHeaders,
      redirect: "follow",
    });

    const responseHeaders = new Headers(upstreamResponse.headers);
    for (const [key, value] of Object.entries(corsHeaders())) {
      responseHeaders.set(key, value);
    }
    responseHeaders.set("Cache-Control", "public, max-age=3600");
    if (!responseHeaders.get("Content-Type")) {
      responseHeaders.set("Content-Type", "application/pdf");
    }

    return new Response(
      request.method === "HEAD" ? null : upstreamResponse.body,
      {
        status: upstreamResponse.status,
        statusText: upstreamResponse.statusText,
        headers: responseHeaders,
      }
    );
  },
};
