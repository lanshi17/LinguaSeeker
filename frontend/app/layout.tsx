import type { Metadata } from "next";
import type { ReactNode } from "react";
import { QueryProvider } from "./providers";
import { NotificationToast } from "@/components/ui/Toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cross Evidence",
  description:
    "Multi-Agent infrastructure for medical genetics literature automation and structured evidence extraction.",
};

interface RootLayoutProps {
  children: ReactNode;
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <QueryProvider>
          {children}
          <NotificationToast />
        </QueryProvider>
      </body>
    </html>
  );
}
