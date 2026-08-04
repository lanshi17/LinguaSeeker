import axios from "axios";
import type { AxiosAdapter } from "axios";
import { beforeEach, describe, expect, it } from "vitest";

import {
  createResponseCacheAdapter,
  createResponseCacheController,
} from "../../src/lib/api/responseCache";

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

  it("reads cached data synchronously before a no-cache request refreshes it", async () => {
    const initialNetwork = createNetworkAdapter([{ version: 1 }]);
    const initialController = createResponseCacheController(
      initialNetwork.adapter,
      {
        now: () => 1_000,
        storage: window.localStorage,
        uncachedPathPatterns: [],
      },
    );
    const initialClient = axios.create({
      baseURL: "/api/v1",
      adapter: initialController.adapter,
    });
    await initialClient.get("/graphrag/graph", {
      params: { gene_symbol: "EGFR" },
      responseCache: { scope: "user-a" },
    });

    const refreshNetwork = createNetworkAdapter([{ version: 2 }]);
    const refreshController = createResponseCacheController(
      refreshNetwork.adapter,
      {
        now: () => 2_000,
        storage: window.localStorage,
        uncachedPathPatterns: [],
      },
    );
    const lookup = {
      baseURL: "/api/v1",
      url: "/graphrag/graph",
      params: { gene_symbol: "EGFR" },
      scope: "user-a",
    };

    expect(refreshController.read(lookup)).toEqual({ version: 1 });
    expect(refreshController.read({ ...lookup, scope: "user-b" })).toBeUndefined();

    const refreshClient = axios.create({
      baseURL: "/api/v1",
      adapter: refreshController.adapter,
    });
    await expect(
      refreshClient.get("/graphrag/graph", {
        headers: { "Cache-Control": "no-cache" },
        params: { gene_symbol: "EGFR" },
        responseCache: { scope: "user-a" },
      }),
    ).resolves.toMatchObject({ data: { version: 2 } });

    expect(refreshNetwork.calls()).toBe(1);
    expect(refreshController.read(lookup)).toEqual({ version: 2 });
  });

  it("parses raw browser JSON when reading directly from the adapter cache", async () => {
    const network = createNetworkAdapter(['{"items":[{"id":"cached"}]}']);
    const controller = createResponseCacheController(network.adapter, {
      now: () => 1_000,
      storage: window.localStorage,
      uncachedPathPatterns: [],
    });
    const client = axios.create({
      baseURL: "/api/v1",
      adapter: controller.adapter,
    });
    await client.get("/evidence/search", {
      responseCache: { scope: "public" },
    });

    expect(
      controller.read({
        baseURL: "/api/v1",
        scope: "public",
        url: "/evidence/search",
      }),
    ).toEqual({ items: [{ id: "cached" }] });
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
      { account_type: "public" },
      { account_type: "user" },
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
    await expect(client.get("/auth/me")).resolves.toMatchObject({
      data: { account_type: "public" },
    });
    await expect(client.get("/auth/me")).resolves.toMatchObject({
      data: { account_type: "user" },
    });
    expect(network.calls()).toBe(8);
  });
});
