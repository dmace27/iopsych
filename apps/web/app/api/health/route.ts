import { NextResponse } from "next/server";

/** Return a dependency-free liveness response for platform health probes. */
export function GET(): NextResponse {
  return NextResponse.json({
    status: "ok",
    service: "web",
    version: "0.1.0",
  });
}
