import assert from "node:assert/strict";
import { after, afterEach, beforeEach, test } from "node:test";
import { JSDOM } from "jsdom";
import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { PredictionsSection } from "../src/components/predictions/PredictionsSection";
import App from "../src/App";
import { session } from "../src/services/api";
import type { ForecastResponse } from "../src/types/api";

const dom = new JSDOM(
  '<!doctype html><html><body><div id="root"></div></body></html>',
  { url: "http://localhost/dashboard" },
);
for (const key of [
  "window",
  "document",
  "navigator",
  "HTMLElement",
  "Event",
  "MouseEvent",
  "sessionStorage",
] as const) {
  Object.defineProperty(globalThis, key, {
    value: dom.window[key],
    configurable: true,
  });
}
Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
const originalFetch = globalThis.fetch;
let root: Root;
let container: HTMLDivElement;

// Contract fixtures exist only in tests. The shipped UI never supplies predictions.
const forecast: ForecastResponse = {
  status: "ok",
  forecast_date: "2026-10-09",
  total: 3,
  training_rows: 28,
  items: [
    { sku_name: "Apple", predicted_units: 12 },
    { sku_name: "Banana", predicted_units: 7 },
    { sku_name: "Zero", predicted_units: 0 },
  ],
  skipped: [],
  warnings: [],
};
const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const text = () => container.textContent ?? "";
const button = (label: string) => {
  const element = [...container.querySelectorAll("button")].find(
    (item) => item.textContent?.trim() === label,
  );
  assert.ok(element, `Button ${label} exists`);
  return element;
};
async function mount(node: ReactNode = createElement(PredictionsSection)) {
  await act(async () => {
    root.render(node);
  });
}
async function click(label = "Generate Prediction") {
  await act(async () => {
    button(label).click();
  });
}
beforeEach(() => {
  session.clear();
  session.set("test-session");
  dom.window.history.replaceState(null, "", "/dashboard");
  container = dom.window.document.querySelector<HTMLDivElement>("#root")!;
  root = createRoot(container);
  globalThis.fetch = async () => reply(forecast);
});
afterEach(async () => {
  await act(async () => {
    root.unmount();
  });
  globalThis.fetch = originalFetch;
});
after(() => dom.window.close());

test("Generate Prediction renders without fetching or fabricated initial totals", async () => {
  globalThis.fetch = async () => {
    assert.fail("No automatic prediction request");
  };
  await mount();
  assert.equal(button("Generate Prediction").disabled, false);
  assert.match(text(), /Predictions/);
  assert.match(text(), /Sales filters do not apply/);
  assert.equal(container.querySelector(".prediction-summary"), null);
});

test("click posts authenticated request with no body/shop_id and disables repeated clicks while loading", async () => {
  let resolve!: (response: Response) => void;
  let calls = 0;
  globalThis.fetch = async (url, options) => {
    calls++;
    assert.equal(url, "/api/v1/predictions");
    assert.equal(options?.method, "POST");
    assert.equal(options?.body, undefined);
    assert.equal(
      new Headers(options?.headers).get("Authorization"),
      "Bearer test-session",
    );
    return new Promise<Response>((done) => {
      resolve = done;
    });
  };
  await mount();
  await click();
  assert.equal(button("Generating prediction...").disabled, true);
  assert.match(
    container.querySelector('[role="status"]')?.textContent ?? "",
    /Generating prediction\.\.\./,
  );
  await click("Generating prediction...");
  assert.equal(calls, 1);
  await act(async () => {
    resolve(reply(forecast));
  });
  assert.equal(button("Generate Prediction").disabled, false);
});

test("successful response renders API date, every SKU, zero prediction and summed units", async () => {
  await mount();
  await click();
  assert.equal(
    container.querySelector("time")?.getAttribute("datetime"),
    "2026-10-09",
  );
  assert.match(text(), /Prediction date: Oct 09, 2026/);
  assert.deepEqual(
    [...container.querySelectorAll("tbody tr")].map((row) =>
      [...row.querySelectorAll("td")].map((cell) => cell.textContent),
    ),
    [
      ["Apple", "12"],
      ["Banana", "7"],
      ["Zero", "0"],
    ],
  );
  const summary = container.querySelector(
    '[role="group"][aria-label="Prediction summary"]',
  )!;
  assert.ok(summary);
  assert.match(summary.textContent ?? "", /Predicted SKUs3/);
  assert.match(summary.textContent ?? "", /Total Predicted Units19/);
  assert.doesNotMatch(text(), /confidence|accuracy/i);
});

test("summary sums whole units exactly beyond JavaScript's safe sum range", async () => {
  globalThis.fetch = async () =>
    reply({
      ...forecast,
      total: 2,
      items: [
        { sku_name: "A", predicted_units: Number.MAX_SAFE_INTEGER },
        { sku_name: "B", predicted_units: 2 },
      ],
    });
  await mount();
  await click();
  assert.match(
    container.querySelector(".prediction-summary")?.textContent ?? "",
    /9,007,199,254,740,993/,
  );
});

test("insufficient_history explains incomplete histories and renders skipped SKU reasons", async () => {
  globalThis.fetch = async () =>
    reply({
      ...forecast,
      status: "insufficient_history",
      items: [],
      total: 0,
      training_rows: 0,
      skipped: [
        {
          sku_name: "Short history",
          reason: "incomplete_history",
          message: "Requires all 28 consecutive daily sales records.",
        },
      ],
    } satisfies ForecastResponse);
  await mount();
  await click();
  assert.match(
    text(),
    /Not enough historical data to generate predictions yet/,
  );
  assert.match(text(), /29 consecutive days/);
  assert.match(text(), /Short history/);
  assert.match(text(), /Requires all 28 consecutive daily sales records/);
  assert.equal(container.querySelector("table"), null);
  assert.equal(button("Generate Prediction").disabled, false);
});

test("no_sales handles null date without inventing a date or predictions", async () => {
  globalThis.fetch = async () =>
    reply({
      status: "no_sales",
      forecast_date: null,
      items: [],
      total: 0,
      training_rows: 0,
      skipped: [],
      warnings: [],
    } satisfies ForecastResponse);
  await mount();
  await click();
  assert.match(text(), /No sales history yet/);
  assert.match(text(), /Upload sales history/);
  assert.equal(container.querySelector("time"), null);
  assert.equal(container.querySelector(".prediction-summary"), null);
});

test("partial forecasts keep real predictions and expose skips and backend calendar warnings", async () => {
  globalThis.fetch = async () =>
    reply({
      ...forecast,
      skipped: [
        {
          sku_name: "Stale SKU",
          reason: "incomplete_history",
          message: "Missing recent daily sales.",
        },
      ],
      warnings: ["The supplied festival calendar covers only 2026."],
    } satisfies ForecastResponse);
  await mount();
  await click();
  assert.equal(container.querySelectorAll("tbody tr").length, 3);
  assert.match(text(), /1 SKU skipped/);
  assert.match(text(), /Stale SKU/);
  assert.match(
    container.querySelector('[role="note"]')?.textContent ?? "",
    /covers only 2026/,
  );
});

for (const [status, detail, expected] of [
  [404, "Not Found", /No sales data was found for predictions/],
  [
    422,
    "Training requires at least one SKU with 29 consecutive daily sales records.",
    /Training requires at least one SKU with 29 consecutive/,
  ],
  [
    500,
    "Traceback: private server details",
    /server could not complete this request/,
  ],
] as const) {
  test(`${status} shows a useful error and re-enables generation and retry`, async () => {
    globalThis.fetch = async () => reply({ detail }, status);
    await mount();
    await click();
    assert.match(
      container.querySelector('[role="alert"]')?.textContent ?? "",
      expected,
    );
    assert.doesNotMatch(text(), /Traceback/);
    assert.equal(button("Generate Prediction").disabled, false);
    assert.equal(button("Try again").disabled, false);
  });
}

test("structured 422 errors retain backend messages", async () => {
  globalThis.fetch = async () =>
    reply({ detail: [{ msg: "Sales history has unsupported dates." }] }, 422);
  await mount();
  await click();
  assert.match(
    container.querySelector('[role="alert"]')?.textContent ?? "",
    /unsupported dates/,
  );
});

test("network error is retryable and retry renders a fresh success", async () => {
  let attempts = 0;
  globalThis.fetch = async () => {
    if (++attempts === 1) throw new TypeError("Failed to fetch");
    return reply(forecast);
  };
  await mount();
  await click();
  assert.match(text(), /Unable to reach the server/);
  await click("Try again");
  assert.equal(attempts, 2);
  assert.equal(container.querySelector('[role="alert"]'), null);
  assert.equal(container.querySelectorAll("tbody tr").length, 3);
});

test("regeneration clears old results while a new response is pending", async () => {
  await mount();
  await click();
  let resolve!: (response: Response) => void;
  globalThis.fetch = async () =>
    new Promise<Response>((done) => {
      resolve = done;
    });
  await click();
  assert.equal(container.querySelector(".prediction-summary"), null);
  assert.equal(container.querySelector("table"), null);
  await act(async () => {
    resolve(reply({ ...forecast, items: [forecast.items[0]], total: 1 }));
  });
  assert.equal(container.querySelectorAll("tbody tr").length, 1);
});

test("unmount aborts an in-flight prediction request", async () => {
  let signal: AbortSignal | null | undefined;
  globalThis.fetch = async (_url, options) => {
    signal = options?.signal;
    return new Promise<Response>(() => {});
  };
  await mount();
  await click();
  assert.equal(signal?.aborted, false);
  await mount(null);
  assert.equal(signal?.aborted, true);
});

test("existing dashboard features remain present and prediction 401 uses existing login redirect", async () => {
  globalThis.fetch = async (url) => {
    if (url === "/api/v1/auth/me")
      return reply({
        id: 1,
        name: "Test User",
        email: "test@example.com",
        shop_id: 101,
      });
    if (url === "/api/v1/sales") return reply({ items: [], total: 0 });
    if (url === "/api/v1/predictions")
      return reply({ detail: "Token has expired." }, 401);
    assert.fail(`Unexpected URL: ${String(url)}`);
  };
  await mount(createElement(App));
  for (const label of [
    "Sales records",
    "Start date",
    "End date",
    "SKU name",
    "Total records",
    "Unique SKUs",
    "Total units sold",
    "Upload sales",
    "Clear filters",
  ])
    assert.ok(text().includes(label), label);
  assert.ok(container.querySelector('button[aria-label="Log out"]'));
  await click();
  assert.equal(session.get(), null);
  assert.equal(dom.window.location.pathname, "/login");
  assert.ok(button("Sign In"));
  assert.equal(container.querySelector(".predictions-card"), null);
});
