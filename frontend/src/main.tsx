import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider, App as AntdApp } from "antd";
import zhCN from "antd/locale/zh_CN";
import enUS from "antd/locale/en_US";
import { lightTheme, darkTheme } from "./theme";
import { App } from "./App";
import { QueryProvider } from "./providers";
import { useAppStore } from "./stores/appStore";
import "./globals.css";

/** Reads mode from store and applies theme + data-theme attribute. */
function ThemeProvider({ children }: { children: React.ReactNode }) {
  const locale = useAppStore((s) => s.locale);
  const mode = useAppStore((s) => s.mode);

  // Sync data-theme on mount (first paint)
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", mode);
  }, [mode]);

  return (
    <ConfigProvider theme={mode === "dark" ? darkTheme : lightTheme} locale={locale === "zh" ? zhCN : enUS}>
      {children}
    </ConfigProvider>
  );
}

const root = document.getElementById("root");
if (!root) throw new Error("Root element not found");

// basename follows the Vite base (SPA mount point), e.g. "/linguaseeker".
// import.meta.env.BASE_URL always ends with "/"; strip the trailing slash so
// BrowserRouter gets a clean prefix (empty string → root, no basename).
const routerBasename = import.meta.env.BASE_URL.replace(/\/+$/, "") || undefined;

createRoot(root).render(
  <StrictMode>
    <BrowserRouter basename={routerBasename}>
      <ThemeProvider>
        <AntdApp>
          <QueryProvider>
            <App />
          </QueryProvider>
        </AntdApp>
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>,
);
