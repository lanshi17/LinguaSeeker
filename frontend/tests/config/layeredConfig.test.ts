import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

function collectTypeScriptFiles(root: string): string[] {
  const entries = readdirSync(root);
  const files: string[] = [];

  for (const entry of entries) {
    const path = join(root, entry);
    const stat = statSync(path);
    if (stat.isDirectory()) {
      files.push(...collectTypeScriptFiles(path));
      continue;
    }
    if (entry.endsWith(".ts") || entry.endsWith(".tsx")) {
      files.push(path);
    }
  }

  return files;
}

describe("layered frontend config", () => {
  it("uses typed API config for the shared Axios client", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "/api/v1-test";
    process.env.NEXT_PUBLIC_API_TIMEOUT = "4321";

    const { apiClient } = await import("../../src/lib/api/client.js");

    assert.equal(apiClient.defaults.baseURL, "/api/v1-test");
    assert.equal(apiClient.defaults.timeout, 4321);
  });

  it("keeps NEXT_PUBLIC reads inside the config module", () => {
    const srcRoot = join(process.cwd(), "src");
    const directEnvReads = collectTypeScriptFiles(srcRoot)
      .filter((path) => !relative(srcRoot, path).startsWith(`lib${sep}config${sep}`))
      .flatMap((path) => {
        const source = readFileSync(path, "utf8");
        const matches = source.match(/process\.env\.NEXT_PUBLIC_[A-Z0-9_]+/g) ?? [];
        return matches.map((match) => `${relative(srcRoot, path)}: ${match}`);
      });

    assert.deepEqual(directEnvReads, []);
  });
});
