import "@testing-library/jest-dom/vitest";

import { readFileSync } from "node:fs";
import path from "node:path";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { Sidebar } from "../../src/components/layout/Sidebar";

const packageJson = JSON.parse(
  readFileSync(path.resolve(__dirname, "../../package.json"), "utf-8"),
) as { version: string };

describe("Sidebar", () => {
  it("renders the app version", () => {
    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <Sidebar />
      </MemoryRouter>,
    );

    expect(
      screen.getByText(`Lingua Seeker v${packageJson.version}`),
    ).toBeInTheDocument();
  });

  it("puts Evidence Database first in the navigation menu", () => {
    render(
      <MemoryRouter initialEntries={["/evidence-db"]}>
        <Sidebar />
      </MemoryRouter>,
    );

    const menuItems = screen.getAllByRole("menuitem");
    expect(menuItems[0]).toHaveTextContent("Evidence Database");
  });
});
