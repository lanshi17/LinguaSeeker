import "@testing-library/jest-dom/vitest";

import { readFileSync } from "node:fs";
import path from "node:path";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { Sidebar } from "../../src/components/layout/Sidebar";

const envAppVersion =
  readFileSync(path.resolve(__dirname, "../../.env"), "utf-8")
    .match(/^VITE_APP_VERSION=(.+)$/m)?.[1]
    .trim() ?? "";

describe("Sidebar", () => {
  it("renders the app version from VITE_APP_VERSION", () => {
    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <Sidebar />
      </MemoryRouter>,
    );

    expect(
      screen.getByText(`Lingua Seeker v${envAppVersion}`),
    ).toBeInTheDocument();
  });
});
