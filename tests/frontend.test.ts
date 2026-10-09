import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { afterEach, beforeEach, test } from "node:test";
import { api, ApiError, session } from "../src/services/api";
import { formatDate, formatUnits, totalUnits } from "../src/lib/format";
import type { SalesRecord } from "../src/types/api";

const originalFetch = globalThis.fetch;
const storage = new Map<string, string>();
const events = new EventTarget();
Object.defineProperty(globalThis, "sessionStorage", {
  value: {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => storage.set(key, value),
    removeItem: (key: string) => storage.delete(key),
  },
});
Object.defineProperty(globalThis, "window", { value: events });
beforeEach(() => storage.clear());
afterEach(() => {
  globalThis.fetch = originalFetch;
});
const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

// Transport fixtures exist only in tests; the application always calls the real API.
test("login posts JSON without an existing bearer token", async () => {
  session.set("old-session");
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/v1/auth/login");
    assert.equal(options?.method, "POST");
    assert.equal(new Headers(options?.headers).get("Authorization"), null);
    assert.equal(
      new Headers(options?.headers).get("Content-Type"),
      "application/json",
    );
    assert.deepEqual(JSON.parse(String(options?.body)), {
      email: "test@example.com",
      password: "test-password",
    });
    return reply({ access_token: "test-session", token_type: "bearer" });
  };
  assert.equal(
    (await api.login({ email: "test@example.com", password: "test-password" }))
      .access_token,
    "test-session",
  );
});
test("register posts UserRegister JSON without an existing bearer token", async () => {
  session.set("old-session");
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/v1/auth/register");
    assert.equal(options?.method, "POST");
    assert.equal(new Headers(options?.headers).get("Authorization"), null);
    assert.equal(
      new Headers(options?.headers).get("Content-Type"),
      "application/json",
    );
    assert.deepEqual(JSON.parse(String(options?.body)), {
      name: "Jane Doe",
      email: "jane@example.com",
      password: "secure-password-123",
      shop_id: 101,
    });
    return reply(
      { id: 10, name: "Jane Doe", email: "jane@example.com", shop_id: 101 },
      201,
    );
  };
  assert.deepEqual(
    await api.register({
      name: "Jane Doe",
      email: "jane@example.com",
      password: "secure-password-123",
      shop_id: 101,
    }),
    { id: 10, name: "Jane Doe", email: "jane@example.com", shop_id: 101 },
  );
});
test("sales query encodes only supported filters and sends bearer authentication", async () => {
  session.set("test-session");
  globalThis.fetch = async (url, options) => {
    const parsed = new URL(String(url), "http://localhost");
    assert.equal(parsed.pathname, "/api/v1/sales");
    assert.deepEqual(Object.fromEntries(parsed.searchParams), {
      start_date: "2026-01-01",
      end_date: "2026-10-08",
      sku_name: "A & B",
    });
    assert.equal(
      new Headers(options?.headers).get("Authorization"),
      "Bearer test-session",
    );
    return reply({ items: [], total: 0 });
  };
  const filters = {
    start_date: "2026-01-01",
    end_date: "2026-10-08",
    sku_name: "A & B",
    shop_id: 999,
  };
  assert.deepEqual(await api.sales(filters), { items: [], total: 0 });
});
test("upload uses multipart file and bearer header without overriding the boundary", async () => {
  session.set("test-session");
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/v1/sales/upload");
    assert.equal(options?.method, "POST");
    assert.ok(options?.body instanceof FormData);
    assert.equal((options.body.get("file") as File).name, "sales.xlsx");
    assert.equal(
      new Headers(options.headers).get("Authorization"),
      "Bearer test-session",
    );
    assert.equal(new Headers(options.headers).get("Content-Type"), null);
    return reply({
      success: true,
      row_count: 1,
      inserted_count: 1,
      updated_count: 0,
    });
  };
  assert.equal(
    (await api.upload(new File(["test workbook"], "sales.xlsx")))
      .inserted_count,
    1,
  );
});
test("401 clears the active token and notifies authentication state", async () => {
  session.set("expired");
  let notified = false;
  const off = session.onUnauthorized(() => {
    notified = true;
  });
  globalThis.fetch = async () => reply({ detail: "expired" }, 401);
  await assert.rejects(
    api.me(),
    (error: unknown) => error instanceof ApiError && error.status === 401,
  );
  assert.equal(session.get(), null);
  assert.equal(notified, true);
  off();
});
test("a late 401 cannot clear a newer authenticated session", async () => {
  session.set("old");
  globalThis.fetch = async () => {
    session.set("new");
    return reply({}, 401);
  };
  await assert.rejects(api.me());
  assert.equal(session.get(), "new");
});
test("row-level Excel errors preserve row numbers and messages", async () => {
  globalThis.fetch = async () =>
    reply(
      {
        detail: {
          errors: [
            {
              row: 5,
              column: "num_units_sold",
              message: "num_units_sold must be >= 0",
            },
          ],
        },
      },
      422,
    );
  await assert.rejects(
    api.upload(new File(["bad"], "sales.xlsx")),
    (error: unknown) => {
      assert.ok(error instanceof ApiError);
      assert.deepEqual(error.issues, [
        {
          row: 5,
          column: "num_units_sold",
          message: "num_units_sold must be >= 0",
        },
      ]);
      return true;
    },
  );
});
test("Pydantic validation errors have usable messages", async () => {
  globalThis.fetch = async () =>
    reply(
      { detail: [{ loc: ["query"], msg: "Start date must precede end date" }] },
      422,
    );
  await assert.rejects(
    api.sales({}),
    (error: unknown) =>
      error instanceof ApiError &&
      error.issues[0].message.includes("Start date"),
  );
});
test("server errors never expose stack traces", async () => {
  globalThis.fetch = async () =>
    reply({ detail: "Traceback: private database credentials" }, 500);
  await assert.rejects(
    api.me(),
    (error: unknown) =>
      error instanceof ApiError &&
      !error.message.includes("Traceback") &&
      !error.message.includes("credentials"),
  );
});
test("network failures have an actionable message", async () => {
  globalThis.fetch = async () => {
    throw new TypeError("Failed to fetch");
  };
  await assert.rejects(
    api.me(),
    (error: unknown) =>
      error instanceof ApiError &&
      error.status === 0 &&
      error.message.includes("connection"),
  );
});
test("canceled sales requests preserve AbortError", async () => {
  globalThis.fetch = async () => {
    throw new DOMException("Aborted", "AbortError");
  };
  await assert.rejects(
    api.sales({}),
    (error: unknown) =>
      error instanceof DOMException && error.name === "AbortError",
  );
});
test("non-JSON successful responses fail clearly", async () => {
  globalThis.fetch = async () => new Response("<html>proxy error</html>");
  await assert.rejects(
    api.me(),
    (error: unknown) =>
      error instanceof ApiError &&
      error.message.includes("unexpected response"),
  );
});
test("decimal totals avoid floating-point drift and preserve large sums", () => {
  const rows = ["0.10", "0.20", "9999999999.99"].map(
    (num_units_sold, id): SalesRecord => ({
      id,
      date: "2026-10-01",
      shop_id: 101,
      sku_name: "Test",
      num_units_sold,
    }),
  );
  assert.equal(totalUnits(rows), "10000000000.29");
  assert.equal(totalUnits([]), "0.00");
  assert.equal(formatUnits("10000000000.29"), "10,000,000,000.29");
  assert.equal(formatUnits("20.50"), "20.5");
  assert.equal(formatUnits("0.00"), "0");
});
test("date rendering preserves the API calendar day independently of timezone", () => {
  assert.equal(formatDate("2026-10-01"), "Oct 01, 2026");
});
test("project routes /api through Vite proxy to FastAPI with no Express server", () => {
  const rootDir = path.resolve(import.meta.dirname, "..");
  assert.equal(fs.existsSync(path.join(rootDir, "server.ts")), false);
  assert.equal(fs.existsSync(path.join(rootDir, "server.js")), false);

  const pkg = JSON.parse(
    fs.readFileSync(path.join(rootDir, "package.json"), "utf-8"),
  ) as {
    scripts?: Record<string, string>;
    dependencies?: Record<string, string>;
    devDependencies?: Record<string, string>;
  };
  assert.match(pkg.scripts?.dev ?? "", /^vite\b/);
  assert.equal(pkg.dependencies?.express, undefined);
  assert.equal(pkg.devDependencies?.["@types/express"], undefined);

  const viteConfig = fs.readFileSync(
    path.join(rootDir, "vite.config.ts"),
    "utf-8",
  );
  assert.match(viteConfig, /"\/api"/);
  assert.match(viteConfig, /http:\/\/127\.0\.0\.1:8000/);

  const authRouter = fs.readFileSync(
    path.join(rootDir, "backend", "app", "auth", "router.py"),
    "utf-8",
  );
  assert.match(authRouter, /prefix="\/auth"/);
  assert.match(authRouter, /"\/register"/);
});
