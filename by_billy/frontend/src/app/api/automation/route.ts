import { NextRequest } from "next/server";
import { checkGatewayAuth, unauthorizedResponse } from "@/lib/gatewayAuth";
import { BACKEND_URL, forward, notConfigured } from "@/lib/serverProxy";

export async function GET(req: NextRequest) {
  const auth = checkGatewayAuth(req.headers.get("authorization"));
  if (!auth.ok) return unauthorizedResponse(auth);
  const token = process.env.MEDSEAL_DOCTOR_TOKEN;
  if (!BACKEND_URL || !token) return notConfigured("MEDSEAL_DOCTOR_TOKEN");
  return forward("/automation", token, { cache: "no-store" });
}
