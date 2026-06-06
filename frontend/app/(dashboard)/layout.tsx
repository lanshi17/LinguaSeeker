import type { ReactNode } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";

interface DashboardLayoutPageProps {
  children: ReactNode;
}

export default function Layout({ children }: DashboardLayoutPageProps) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
