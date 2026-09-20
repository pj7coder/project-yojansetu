import { NextRequest, NextResponse } from "next/server";
import { executeFallbackAgent } from "@/lib/agentFallback";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { query, context, language } = body;

    // Check if an external backend is configured via env and reachable
    const externalApi = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (externalApi && !externalApi.includes("localhost")) {
      try {
        const extResp = await fetch(`${externalApi}/agent/query`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query, context, language }),
        });
        if (extResp.ok) {
          const data = await extResp.json();
          return NextResponse.json(data);
        }
      } catch (e) {
        console.warn("External backend call failed, using built-in agent engine:", e);
      }
    }

    // Execute built-in deterministic Rajasthan welfare agent
    const result = executeFallbackAgent(query || "", context || {}, language || "hi");
    return NextResponse.json(result);
  } catch (error: any) {
    console.error("Agent route error:", error);
    return NextResponse.json(
      { detail: error?.message || "Internal agent execution error" },
      { status: 500 }
    );
  }
}
