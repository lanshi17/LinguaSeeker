import type { Metadata } from "next";
import type { ReactNode } from "react";
import { QueryProvider } from "./providers";
import { NotificationToast } from "@/components/ui/Toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "ACMG Lingua",
  description:
    "Multi-Agent infrastructure for medical genetics literature automation and structured evidence extraction.",
};

interface RootLayoutProps {
  children: ReactNode;
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>
          {children}
          <NotificationToast />
        </QueryProvider>
      </body>
    </html>
  );
}
