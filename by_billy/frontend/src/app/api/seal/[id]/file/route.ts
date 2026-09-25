import { NextRequest, NextResponse } from "next/server";
import { checkGatewayAuth, unauthorizedResponse } from "@/lib/gatewayAuth";

const BACKEND_URL = (process.env.MEDSEAL_BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

export async function GET(req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const auth = checkGatewayAuth(req.headers.get("authorization"));
  if (!auth.ok) return unauthorizedResponse(auth);

  const token = process.env.MEDSEAL_DEVICE_TOKEN;
  if (!BACKEND_URL || !token) {
    return NextResponse.json(
      { detail: "Gateway is not configured: set MEDSEAL_BACKEND_URL and MEDSEAL_DEVICE_TOKEN in .env.local" },
      { status: 503 }
    );
  }
  const { id } = await context.params;
  if (!/^\d+$/.test(id)) return NextResponse.json({ detail: "Invalid seal id" }, { status: 400 });

  const response = await fetch(`${BACKEND_URL}/seal/${id}/file`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!response.ok) {
    return new NextResponse(await response.text(), { status: response.status });
  }
  return new NextResponse(await response.arrayBuffer(), {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/octet-stream",
      "Content-Disposition": response.headers.get("content-disposition") ?? `attachment; filename="medseal-seal-${id}"`,
    },
  });
}
