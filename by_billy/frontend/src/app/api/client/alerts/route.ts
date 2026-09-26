import { NextRequest } from "next/server";
import { checkGatewayAuth, unauthorizedResponse } from "@/lib/gatewayAuth";
import { BACKEND_URL, forward, notConfigured } from "@/lib/serverProxy";

export async function GET(req: NextRequest) {
  const auth = checkGatewayAuth(req.headers.get("authorization"));
  if (!auth.ok) return unauthorizedResponse(auth);
  const token = process.env.MEDSEAL_CLIENT_TOKEN;
  if (!BACKEND_URL || !token) return notConfigured("MEDSEAL_CLIENT_TOKEN");
  return forward(`/client/alerts${req.nextUrl.search}`, token, { cache: "no-store" });
}
