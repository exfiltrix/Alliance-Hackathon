import { timingSafeEqual } from "crypto";

// Server-only (Node.js runtime — Next 16 Proxy defaults to it, so Node's `crypto` is available
// here and in route handlers alike). Never import this from a "use client" file.
//
// Gates the gateway simulator (/seal page + its API routes) behind HTTP Basic Auth: P1-01.
// Credentials are server-only env vars, never exposed to the browser. Used by both src/proxy.ts
// (first line of defence) and each protected route handler (defence in depth).

function safeEqual(a: string, b: string): boolean {
  const bufA = Buffer.from(a);
  const bufB = Buffer.from(b);
  if (bufA.length !== bufB.length) {
    // Burn the same time as a real comparison so a mismatched length isn't distinguishable
    // from a mismatched value via timing (an early `return false` here would leak length).
    timingSafeEqual(bufA, bufA);
    return false;
  }
  return timingSafeEqual(bufA, bufB);
}

export type GatewayAuthResult = { ok: true } | { ok: false; status: 401 | 503; message: string };

export function checkGatewayAuth(authorizationHeader: string | null): GatewayAuthResult {
  const user = process.env.MEDSEAL_GATEWAY_USER;
  const pass = process.env.MEDSEAL_GATEWAY_PASSWORD;
  if (!user || !pass) {
    // Fail closed, never open: an unconfigured gateway must not become an open gateway.
    return {
      ok: false,
      status: 503,
      message: "Gateway credentials are not configured (MEDSEAL_GATEWAY_USER / MEDSEAL_GATEWAY_PASSWORD)",
    };
  }

  if (authorizationHeader?.startsWith("Basic ")) {
    const decoded = Buffer.from(authorizationHeader.slice(6), "base64").toString("utf-8");
    const sep = decoded.indexOf(":");
    const u = sep === -1 ? decoded : decoded.slice(0, sep);
    const p = sep === -1 ? "" : decoded.slice(sep + 1);
    if (safeEqual(u, user) && safeEqual(p, pass)) return { ok: true };
  }

  return { ok: false, status: 401, message: "Authentication required" };
}

export function unauthorizedResponse(result: Extract<GatewayAuthResult, { ok: false }>) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (result.status === 401) headers["WWW-Authenticate"] = 'Basic realm="MedSeal gateway"';
  return new Response(JSON.stringify({ detail: result.message }), { status: result.status, headers });
}
