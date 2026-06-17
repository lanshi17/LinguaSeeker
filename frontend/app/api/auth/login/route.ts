import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import crypto from "node:crypto";

const SESSION_COOKIE = "ce_session";
const SESSION_DURATION_SEC = 60 * 60 * 8; // 8 hours

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { password } = body as { password?: string };

    if (!password) {
      return NextResponse.json(
        { error: "Password is required" },
        { status: 400 },
      );
    }

    const adminPassword = process.env.ADMIN_PASSWORD || process.env.API_KEY;

    if (!adminPassword) {
      return NextResponse.json(
        { error: "Authentication not configured" },
        { status: 500 },
      );
    }

    // Constant-time comparison
    const inputBuf = Buffer.from(password);
    const storedBuf = Buffer.from(adminPassword);
    const match =
      inputBuf.length === storedBuf.length &&
      crypto.timingSafeEqual(inputBuf, storedBuf);

    if (!match) {
      return NextResponse.json(
        { error: "Invalid password" },
        { status: 401 },
      );
    }

    // Create a signed session token (HMAC)
    const sessionSecret = process.env.SESSION_SECRET || adminPassword;
    const expiresAt = Math.floor(Date.now() / 1000) + SESSION_DURATION_SEC;
    const payload = Buffer.from(JSON.stringify({ exp: expiresAt })).toString(
      "base64url",
    );
    const signature = crypto
      .createHmac("sha256", sessionSecret)
      .update(payload)
      .digest("base64url");
    const token = `${payload}.${signature}`;

    const response = NextResponse.json({ success: true });
    response.cookies.set(SESSION_COOKIE, token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "strict",
      maxAge: SESSION_DURATION_SEC,
      path: "/",
    });

    return response;
  } catch {
    return NextResponse.json(
      { error: "Invalid request" },
      { status: 400 },
    );
  }
}
