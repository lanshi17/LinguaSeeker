import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, useEffect, type ReactNode } from "react";
import { ConfigProvider, App as AntdApp } from "antd";
import zhCN from "antd/locale/zh_CN";
import enUS from "antd/locale/en_US";
import { lightTheme, darkTheme } from "./theme";
import { useAppStore } from "./stores/appStore";

interface QueryProviderProps {
  children: ReactNode;
}

export function QueryProvider({ children }: QueryProviderProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

/** Reads mode from store and applies theme + data-theme attribute. */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const locale = useAppStore((s) => s.locale);
  const mode = useAppStore((s) => s.mode);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", mode);
  }, [mode]);

  return (
    <ConfigProvider theme={mode === "dark" ? darkTheme : lightTheme} locale={locale === "zh" ? zhCN : enUS}>
      {children}
    </ConfigProvider>
  );
}
