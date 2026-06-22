import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider, App as AntdApp } from "antd";
import { theme } from "./theme";
import { App } from "./App";
import { QueryProvider } from "./providers";
import "./globals.css";

const root = document.getElementById("root");
if (!root) throw new Error("Root element not found");

createRoot(root).render(
  <StrictMode>
    <BrowserRouter>
      <ConfigProvider theme={theme}>
        <AntdApp>
          <QueryProvider>
            <App />
          </QueryProvider>
        </AntdApp>
      </ConfigProvider>
    </BrowserRouter>
  </StrictMode>,
);
