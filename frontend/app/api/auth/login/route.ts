import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

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

    const encoder = new TextEncoder();
    const inputBytes = encoder.encode(password);
    const storedBytes = encoder.encode(adminPassword);

    if (inputBytes.length !== storedBytes.length) {
      return NextResponse.json(
        { error: "Invalid password" },
        { status: 401 },
      );
    }

    let result = 0;
    for (let i = 0; i < inputBytes.length; i++) {
      result |= inputBytes[i] ^ storedBytes[i];
    }
    if (result !== 0) {
      return NextResponse.json(
        { error: "Invalid password" },
        { status: 401 },
      );
    }

    const sessionSecret = process.env.SESSION_SECRET || adminPassword;
    const expiresAt = Math.floor(Date.now() / 1000) + SESSION_DURATION_SEC;
    const payload = btoa(JSON.stringify({ exp: expiresAt }))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=/g, "");

    const keyData = encoder.encode(sessionSecret);
    const key = await crypto.subtle.importKey(
      "raw",
      keyData,
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    );

    const signatureBytes = await crypto.subtle.sign(
      "HMAC",
      key,
      encoder.encode(payload)
    );

    const bytes = new Uint8Array(signatureBytes);
    let binary = "";
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    const signature = btoa(binary)
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=/g, "");

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
