/** Browser smoke test for cached Evidence DB and KG view refreshes. */

const BASE_URL = "http://127.0.0.1:3000";
const SCREENSHOT_DIR = "/tmp/lingua-cache-swr";

interface CdpError {
  code: number;
  message: string;
}

interface CdpMessage {
  error?: CdpError;
  id?: number;
  method?: string;
  params?: unknown;
  result?: unknown;
}

interface FetchPausedParams {
  requestId: string;
  request: {
    headers: Record<string, string>;
    url: string;
  };
}

type EventHandler = (params: unknown) => void;

class CdpClient {
  private nextId = 1;
  private readonly pending = new Map<
    number,
    {
      reject: (reason: Error) => void;
      resolve: (value: unknown) => void;
    }
  >();
  private readonly handlers = new Map<string, EventHandler[]>();

  private constructor(private readonly socket: WebSocket) {
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(String(event.data)) as CdpMessage;
      if (message.id !== undefined) {
        const callback = this.pending.get(message.id);
        if (!callback) return;
        this.pending.delete(message.id);
        if (message.error) {
          callback.reject(new Error(message.error.message));
        } else {
          callback.resolve(message.result);
        }
        return;
      }
      if (!message.method) return;
      for (const handler of this.handlers.get(message.method) ?? []) {
        handler(message.params);
      }
    });
  }

  static async connect(url: string): Promise<CdpClient> {
    const socket = new WebSocket(url);
    await new Promise<void>((resolve, reject) => {
      socket.addEventListener("open", () => resolve(), { once: true });
      socket.addEventListener(
        "error",
        () => reject(new Error("Chrome DevTools websocket failed to open")),
        { once: true },
      );
    });
    return new CdpClient(socket);
  }

  close(): void {
    this.socket.close();
  }

  on(method: string, handler: EventHandler): void {
    const handlers = this.handlers.get(method) ?? [];
    handlers.push(handler);
    this.handlers.set(method, handlers);
  }

  send<T = Record<string, unknown>>(
    method: string,
    params: Record<string, unknown> = {},
  ): Promise<T> {
    const id = this.nextId;
    this.nextId += 1;
    return new Promise<T>((resolve, reject) => {
      this.pending.set(id, {
        reject,
        resolve: (value) => resolve(value as T),
      });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }
}

function evidencePayload(variant: string): Record<string, unknown> {
  return {
    items: [
      {
        group_id: `gene=MECP2|variant=${variant}`,
        source_document_id: `document-${variant}`,
        gene: "MECP2",
        variant,
        disease: "Rett syndrome",
        classification: "Pathogenic",
        field_count: 4,
        avg_confidence: 0.91,
        review_status: "provisional",
      },
    ],
    total: 1,
    page: 1,
    page_size: 1,
  };
}

function graphPayload(nodeCount: number): Record<string, unknown> {
  const nodes: Record<string, unknown>[] = [
    {
      node_id: "gene:EGFR",
      labels: ["Gene"],
      display_name: "EGFR",
      properties: {},
    },
  ];
  const edges: Record<string, unknown>[] = [];
  if (nodeCount === 2) {
    nodes.push({
      node_id: "disease:Lung-cancer",
      labels: ["Disease"],
      display_name: "Lung cancer",
      properties: {},
    });
    edges.push({
      source_id: "gene:EGFR",
      target_id: "disease:Lung-cancer",
      rel_type: "ASSOCIATED_WITH",
      properties: {},
    });
  }
  return { edges, nodes };
}

async function fulfillJson(
  client: CdpClient,
  requestId: string,
  payload: unknown,
): Promise<void> {
  await client.send("Fetch.fulfillRequest", {
    requestId,
    responseCode: 200,
    responseHeaders: [
      { name: "Content-Type", value: "application/json" },
    ],
    body: Buffer.from(JSON.stringify(payload)).toString("base64"),
  });
}

async function evaluate<T>(client: CdpClient, expression: string): Promise<T> {
  const response = await client.send<{
    exceptionDetails?: unknown;
    result: { value?: T };
  }>("Runtime.evaluate", {
    expression,
    returnByValue: true,
  });
  if (response.exceptionDetails) {
    throw new Error(`Browser evaluation failed: ${expression}`);
  }
  return response.result.value as T;
}

async function waitFor(
  client: CdpClient,
  condition: () => boolean | Promise<boolean>,
  description: string,
): Promise<void> {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    if (await condition()) return;
    await Bun.sleep(50);
  }
  const body = await evaluate<string>(client, "document.body?.innerText ?? ''");
  throw new Error(`Timed out waiting for ${description}. Body: ${body.slice(0, 1000)}`);
}

async function waitForText(client: CdpClient, text: string): Promise<void> {
  const literal = JSON.stringify(text);
  await waitFor(
    client,
    () =>
      evaluate<boolean>(
        client,
        `document.body?.innerText.includes(${literal}) ?? false`,
      ),
    `text ${text}`,
  );
}

async function waitForPending(
  client: CdpClient,
  requests: string[],
  description: string,
): Promise<string> {
  await waitFor(client, () => requests.length > 0, description);
  const requestId = requests.shift();
  if (!requestId) throw new Error(`Missing ${description}`);
  return requestId;
}

async function captureScreenshot(client: CdpClient, name: string): Promise<void> {
  const screenshot = await client.send<{ data: string }>("Page.captureScreenshot", {
    captureBeyondViewport: true,
    format: "png",
  });
  await Bun.write(`${SCREENSHOT_DIR}/${name}`, Buffer.from(screenshot.data, "base64"));
}

async function waitForCdp(port: number): Promise<void> {
  const deadline = Date.now() + 20_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (response.ok) return;
    } catch {
      // Chrome is still starting.
    }
    await Bun.sleep(100);
  }
  throw new Error("Chrome DevTools endpoint did not start");
}

async function main(): Promise<void> {
  const remotePort = 9300 + (process.pid % 500);
  const profilePath = `/tmp/lingua-cache-swr-cdp-${process.pid}`;
  const chrome = Bun.spawn(
    [
      "/usr/bin/google-chrome",
      "--headless=new",
      "--no-sandbox",
      "--disable-gpu",
      "--lang=en-US",
      `--remote-debugging-port=${remotePort}`,
      `--user-data-dir=${profilePath}`,
      "about:blank",
    ],
    { stderr: "ignore", stdout: "ignore" },
  );
  let client: CdpClient | undefined;

  try {
    await waitForCdp(remotePort);
    const targetResponse = await fetch(
      `http://127.0.0.1:${remotePort}/json/new?${encodeURIComponent("about:blank")}`,
      { method: "PUT" },
    );
    const target = (await targetResponse.json()) as { webSocketDebuggerUrl: string };
    client = await CdpClient.connect(target.webSocketDebuggerUrl);
    await Promise.all([
      client.send("Page.enable"),
      client.send("Runtime.enable"),
      client.send("Fetch.enable", {
        patterns: [
          { urlPattern: "*api/v1/*" },
          { urlPattern: "*health*" },
        ],
      }),
      client.send("Emulation.setDeviceMetricsOverride", {
        width: 1440,
        height: 1000,
        deviceScaleFactor: 1,
        mobile: false,
      }),
    ]);

    const state: { evidence: "pending" | "seed"; graph: "pending" | "seed" } = {
      evidence: "seed",
      graph: "seed",
    };
    const pendingEvidence: string[] = [];
    const pendingGraph: string[] = [];
    const refreshHeaders: string[] = [];
    let routeFailure: Error | undefined;

    client.on("Fetch.requestPaused", (rawParams) => {
      const params = rawParams as FetchPausedParams;
      void (async () => {
        const path = new URL(params.request.url).pathname;
        if (path.endsWith("/auth/me")) {
          await fulfillJson(client!, params.requestId, {
            authenticated: false,
            account_type: "public",
            user_id: null,
            username: null,
            display_name: "Public account",
          });
          return;
        }
        if (path.endsWith("/evidence/search")) {
          const header = Object.entries(params.request.headers).find(
            ([name]) => name.toLowerCase() === "cache-control",
          );
          refreshHeaders.push(header?.[1] ?? "");
          if (state.evidence === "pending") {
            pendingEvidence.push(params.requestId);
            return;
          }
          await fulfillJson(client!, params.requestId, evidencePayload("c.100A>G"));
          return;
        }
        if (path.endsWith("/graphrag/graph")) {
          const header = Object.entries(params.request.headers).find(
            ([name]) => name.toLowerCase() === "cache-control",
          );
          refreshHeaders.push(header?.[1] ?? "");
          if (state.graph === "pending") {
            pendingGraph.push(params.requestId);
            return;
          }
          await fulfillJson(client!, params.requestId, graphPayload(1));
          return;
        }
        await fulfillJson(client!, params.requestId, { status: "ok" });
      })().catch((error: unknown) => {
        routeFailure = error instanceof Error ? error : new Error(String(error));
      });
    });

    const checkRouteFailure = (): boolean => {
      if (routeFailure) throw routeFailure;
      return false;
    };

    await client.send("Page.navigate", { url: `${BASE_URL}/evidence-db` });
    await waitForText(client, "c.100A>G");

    state.evidence = "pending";
    await client.send("Page.reload", { ignoreCache: false });
    const evidenceRequest = await waitForPending(
      client,
      pendingEvidence,
      "pending Evidence DB refresh",
    );
    checkRouteFailure();
    await waitForText(client, "c.100A>G");
    await captureScreenshot(client, "evidence-cached.png");
    await fulfillJson(client, evidenceRequest, evidencePayload("c.200A>G"));
    await waitForText(client, "c.200A>G");

    state.graph = "seed";
    await client.send("Page.navigate", { url: `${BASE_URL}/graphrag?gene=EGFR` });
    await waitForText(client, "1 nodes");
    await waitForText(client, "0 relations");

    state.graph = "pending";
    await client.send("Page.reload", { ignoreCache: false });
    const graphRequest = await waitForPending(
      client,
      pendingGraph,
      "pending KG refresh",
    );
    checkRouteFailure();
    await waitForText(client, "1 nodes");
    await waitForText(client, "0 relations");
    const canvasHasPixels = `Array.from(document.querySelectorAll('canvas')).some((canvas) => {
      if (canvas.width === 0 || canvas.height === 0) return false;
      const blank = document.createElement('canvas');
      blank.width = canvas.width;
      blank.height = canvas.height;
      return canvas.toDataURL() !== blank.toDataURL();
    })`;
    await waitFor(
      client,
      () => evaluate<boolean>(client!, canvasHasPixels),
      "nonblank cached KG canvas",
    );
    await captureScreenshot(client, "graph-cached.png");
    await fulfillJson(client, graphRequest, graphPayload(2));
    await waitForText(client, "2 nodes");
    await waitForText(client, "1 relations");

    if (refreshHeaders.length === 0) {
      throw new Error("No refresh requests were observed");
    }
    if (refreshHeaders.some((value) => value !== "no-cache")) {
      throw new Error(`Unexpected refresh headers: ${refreshHeaders.join(", ")}`);
    }

    console.log("Evidence DB cached view: c.100A>G -> c.200A>G");
    console.log("KG cached view: 1 node/0 relations -> 2 nodes/1 relation");
    console.log(`Screenshots: ${SCREENSHOT_DIR}`);
  } finally {
    client?.close();
    chrome.kill();
    await chrome.exited;
    Bun.spawnSync(["rm", "-rf", profilePath]);
  }
}

await main();
