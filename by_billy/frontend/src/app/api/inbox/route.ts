import { NextRequest } from "next/server";
import { checkGatewayAuth, unauthorizedResponse } from "@/lib/gatewayAuth";
import { BACKEND_URL, forward, notConfigured } from "@/lib/serverProxy";

// Server-only: the doctor's inbox holds real medical images (docs/SECURITY.md T11) and must never
// be reachable without the doctor's bearer token, which stays server-side (MEDSEAL_DOCTOR_TOKEN).
// src/proxy.ts gates this route with the same Basic Auth as the gateway simulator first; this
// handler re-checks independently (defence in depth, same reasoning as src/app/api/seal/route.ts).
export async function GET(req: NextRequest) {
  const auth = checkGatewayAuth(req.headers.get("authorization"));
  if (!auth.ok) return unauthorizedResponse(auth);
  const token = process.env.MEDSEAL_DOCTOR_TOKEN;
  if (!BACKEND_URL || !token) return notConfigured("MEDSEAL_DOCTOR_TOKEN");
  return forward(`/inbox${req.nextUrl.search}`, token, { cache: "no-store" });
}

export async function POST(req: NextRequest) {
  const auth = checkGatewayAuth(req.headers.get("authorization"));
  if (!auth.ok) return unauthorizedResponse(auth);
  const token = process.env.MEDSEAL_DOCTOR_TOKEN;
  if (!BACKEND_URL || !token) return notConfigured("MEDSEAL_DOCTOR_TOKEN");
  const form = await req.formData();
  return forward("/inbox", token, { method: "POST", body: form });
}
