import { NextResponse } from "next/server";

const SESSION_COOKIE = "ce_session";

export async function POST() {
  const response = NextResponse.json({ success: true });
  response.cookies.delete(SESSION_COOKIE);
  return response;
}
