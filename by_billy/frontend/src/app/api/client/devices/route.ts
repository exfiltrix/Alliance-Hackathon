import { NextRequest } from "next/server";
import { checkGatewayAuth, unauthorizedResponse } from "@/lib/gatewayAuth";
import { BACKEND_URL, forward, notConfigured } from "@/lib/serverProxy";

// Server-only: the client (hospital/clinic) cabinet is scoped to one organisation by its own
// bearer token (MEDSEAL_CLIENT_TOKEN, backend docs/API.md "Client cabinet") — never sent to the
// browser. Same Basic Auth barrier as the rest of the internal site (src/proxy.ts).
export async function GET(req: NextRequest) {
  const auth = checkGatewayAuth(req.headers.get("authorization"));
  if (!auth.ok) return unauthorizedResponse(auth);
  const token = process.env.MEDSEAL_CLIENT_TOKEN;
  if (!BACKEND_URL || !token) return notConfigured("MEDSEAL_CLIENT_TOKEN");
  return forward("/client/devices", token, { cache: "no-store" });
}
