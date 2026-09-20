import { NextResponse } from "next/server";
import { getFallbackTools } from "@/lib/agentFallback";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(getFallbackTools());
}
