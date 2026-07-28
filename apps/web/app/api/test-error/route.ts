import { NextResponse } from "next/server";
import * as Sentry from "@sentry/nextjs";

export async function GET() {
  const error = new Error("Intentional Test Error for Sentry validation in Phase 14 (Web)");
  Sentry.captureException(error);
  throw error;
}
