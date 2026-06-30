import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App as AntdApp } from "antd";
import { App } from "./App";
import { QueryProvider, ThemeProvider } from "./providers";
import "./globals.css";

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
