import axios from "axios";
import type { AxiosAdapter } from "axios";
import { beforeEach, describe, expect, it } from "vitest";

import { createResponseCacheAdapter } from "../../src/lib/api/responseCache";

function createNetworkAdapter(payloads: unknown[]): {
  adapter: AxiosAdapter;
  calls: () => number;
} {
  let callCount = 0;

  return {
    adapter: async (config) => {
      const data = payloads[Math.min(callCount, payloads.length - 1)];
      callCount += 1;
      return {
        data,
        status: 200,
        statusText: "OK",
        headers: { "content-type": "application/json" },
        config,
      };
    },
    calls: () => callCount,
  };
}

describe("response cache adapter", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("persists GET responses in browser storage and serves them to a new client", async () => {
    const firstNetwork = createNetworkAdapter([{ value: "backend" }]);
    const firstClient = axios.create({
      baseURL: "/api/v1",
      adapter: createResponseCacheAdapter(firstNetwork.adapter, {
        now: () => 1_000,
        storage: window.localStorage,
        uncachedPathPatterns: [],
      }),
    });

    await expect(
      firstClient.get("/evidence/search", { params: { gene: "MECP2", page: 1 } }),
    ).resolves.toMatchObject({ data: { value: "backend" } });
    expect(firstNetwork.calls()).toBe(1);

    const secondNetwork = createNetworkAdapter([{ value: "network" }]);
    const secondClient = axios.create({
      baseURL: "/api/v1",
      adapter: createResponseCacheAdapter(secondNetwork.adapter, {
        now: () => 2_000,
        storage: window.localStorage,
        uncachedPathPatterns: [],
      }),
    });

    await expect(
      secondClient.get("/evidence/search", { params: { page: 1, gene: "MECP2" } }),
    ).resolves.toMatchObject({ data: { value: "backend" } });
    expect(secondNetwork.calls()).toBe(0);
  });

  it("refreshes expired browser cache entries from the backend adapter", async () => {
    let now = 1_000;
    const network = createNetworkAdapter([{ version: 1 }, { version: 2 }]);
    const client = axios.create({
      baseURL: "/api/v1",
      adapter: createResponseCacheAdapter(network.adapter, {
        now: () => now,
        storage: window.localStorage,
        ttlMs: 500,
        uncachedPathPatterns: [],
      }),
    });

    await expect(client.get("/evidence/search")).resolves.toMatchObject({
      data: { version: 1 },
    });

    now = 2_000;

    await expect(client.get("/evidence/search")).resolves.toMatchObject({
      data: { version: 2 },
    });
    expect(network.calls()).toBe(2);
  });

  it("invalidates cached GET responses after successful mutations", async () => {
    const network = createNetworkAdapter([
      { version: 1 },
      { ok: true },
      { version: 2 },
    ]);
    const client = axios.create({
      baseURL: "/api/v1",
      adapter: createResponseCacheAdapter(network.adapter, {
        now: () => 1_000,
        storage: window.localStorage,
        uncachedPathPatterns: [],
      }),
    });

    await expect(client.get("/evidence/search")).resolves.toMatchObject({
      data: { version: 1 },
    });
    await expect(client.get("/evidence/search")).resolves.toMatchObject({
      data: { version: 1 },
    });
    expect(network.calls()).toBe(1);

    await expect(client.patch("/evidence/123", { review_status: "approved" }))
      .resolves.toMatchObject({ data: { ok: true } });

    await expect(client.get("/evidence/search")).resolves.toMatchObject({
      data: { version: 2 },
    });
    expect(network.calls()).toBe(3);
  });

  it("bypasses cache for realtime backend paths", async () => {
    const network = createNetworkAdapter([
      { status: "running" },
      { status: "completed" },
      { gene: "OLD" },
      { gene: "BRCA1" },
      { items: [] },
      { items: [{ id: "annotation-1" }] },
    ]);
    const client = axios.create({
      baseURL: "/api/v1",
      adapter: createResponseCacheAdapter(network.adapter, {
        now: () => 1_000,
        storage: window.localStorage,
      }),
    });

    await expect(client.get("/pipeline/runs/abc/status")).resolves.toMatchObject({
      data: { status: "running" },
    });
    await expect(client.get("/pipeline/runs/abc/status")).resolves.toMatchObject({
      data: { status: "completed" },
    });

    await expect(client.get("/evidence/groups/detail", {
      params: { group_id: "group-1" },
    })).resolves.toMatchObject({
      data: { gene: "OLD" },
    });
    await expect(client.get("/evidence/groups/detail", {
      params: { group_id: "group-1" },
    })).resolves.toMatchObject({
      data: { gene: "BRCA1" },
    });

    await expect(client.get("/documents/doc-1/annotations")).resolves.toMatchObject({
      data: { items: [] },
    });
    await expect(client.get("/documents/doc-1/annotations")).resolves.toMatchObject({
      data: { items: [{ id: "annotation-1" }] },
    });
    expect(network.calls()).toBe(6);
  });
});
