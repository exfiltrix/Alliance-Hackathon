import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { checkGatewayAuth, unauthorizedResponse } from "@/lib/gatewayAuth";

// P1-01: the /seal page (gateway simulator) and every gateway/admin API route require HTTP
// Basic Auth. This is the first line of defence; each route handler re-checks independently
// (defence in depth — see src/lib/gatewayAuth.ts).
export function proxy(request: NextRequest) {
  const result = checkGatewayAuth(request.headers.get("authorization"));
  if (result.ok) return NextResponse.next();
  return unauthorizedResponse(result);
}

export const config = {
  matcher: [
    "/seal",
    "/api/seal",
    "/api/seal/:path*",
    "/api/crash-test",
    "/api/crash-test/:path*",
    "/api/passport",
    "/api/passport/:path*",
  ],
};
