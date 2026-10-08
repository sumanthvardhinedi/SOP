# SalesFlow frontend

React 19 + TypeScript + Vite. An authenticated workspace for viewing, filtering,
uploading your shop's sales, and requesting next-day predictions. All sales and
predictions come from the API; there is no embedded sample data.

## Run locally

Use Node.js 24+ and npm (the repository includes `package-lock.json`).

```sh
npm ci
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000. Run the existing backend separately using its
[setup instructions](backend/README.md). The frontend does not change backend
code or database configuration.

### API configuration

For local development, leave `VITE_API_BASE_URL` empty. Vite forwards `/api/*`
to `API_PROXY_TARGET`, which defaults to `http://127.0.0.1:8000`.
This works with the current backend without requiring CORS changes.

To use a separately hosted API that already permits your frontend origin via CORS:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Use the API **origin**, without `/api/v1`. Restart Vite after environment changes;
Vite substitutes `VITE_` values at build time. Never put secrets in `VITE_`
variables: they are public browser configuration. `.env` and `.env.*` are ignored,
except for the placeholder-only `.env.example`.

## Application flow

- `/login`: email/password login using `POST /api/v1/auth/login` (JSON).
- The JWT is stored in **sessionStorage**, scoped to the browser tab, and never
  displayed or included in URLs. Reloads restore the profile through
  `GET /api/v1/auth/me`; closing the tab ends local persistence. Use HTTPS in
  production and treat browser storage as accessible to scripts on your origin.
- `/dashboard`: authenticated users see their name, email, and authoritative shop
  ID from `/auth/me`. No shop selector or client shop authorization is used.
- `GET /api/v1/sales` supplies the table and overview. Overview totals reflect the
  currently applied filters, including zero for an empty result. Loading/errors
  show placeholders instead of invented totals. Decimal units use integer
  hundredths for exact summation.
- Filters are inclusive `start_date`, inclusive `end_date`, and exact `sku_name`
  (case and spaces preserved). Apply submits all filters; Clear filters resets
  the form and fetches all available sales. No `shop_id` is sent as a filter.
- Drag or pick one `.xlsx` workbook. Upload calls `POST /api/v1/sales/upload`
  with multipart field `file` and the bearer token. The backend validates and
  persists the whole workbook. Required columns: `shop_id`, `sku_name`,
  `num_units_sold`, `date`. CSV and `.xls` are rejected locally and by the API.
- A successful upload shows processed/inserted/updated counts and refreshes sales
  with the active filters. Existing date/SKU records are replaced by the backend.
  Row errors are listed without showing server stack traces. The backend remains
  authoritative for format, size, duplicate keys, and shop authorization.
- Logout clears the token and profile. An authenticated request returning 401
  does the same and returns to login. Invalid login displays an inline error.

## Frontend structure

- `src/services/api.ts`: fetch, JSON/FormData, bearer headers, errors, 401 events.
- `src/hooks/`: authentication lifecycle and cancelable sales requests.
- `src/types/api.ts`: API contracts, including string decimal values.
- `src/components/`: layout, sales table/filters/overview, Excel upload, and predictions.
- `src/pages/`: login and dashboard.
- `src/lib/format.ts`: date/number display and exact decimal totals.

## Predictions

The dashboard's **Generate Prediction** button calls `POST /api/v1/predictions`
through the shared typed API client, using the existing bearer token. It sends no
body, `shop_id`, or sales filters. The backend selects the authenticated shop.

The UI follows the real `ForecastResponse` contract: `status`, `forecast_date`,
`items` (`sku_name`, `predicted_units`), `total`, `training_rows`, `skipped`, and
`warnings`. It displays the returned date, predicted SKU count, integer-unit sum,
and SKU table. Only the display total is calculated locally; no forecasting or
confidence/accuracy values are computed or invented. Prediction units are
summed with BigInt to avoid rounding when adding large integers.

Generation disables the button and announces progress. Empty/insufficient history
explains the model's consecutive-day requirements. Skipped SKU reasons and calendar
warnings are displayed. A 404 shows a no-sales message, 422 retains useful backend
validation detail, and network/server errors allow retry. A 401 uses the existing
session-expiry redirect. Leaving the dashboard cancels the frontend request.

Predictions use all shop history independently of sales filters. The prediction
date is the day after the latest stored sale, not necessarily tomorrow. Regenerate
after uploading new sales; the existing upload and sales-refresh flow is unchanged.

## Verification and production

```sh
npm run lint   # strict TypeScript checks
npm test       # API/format tests plus prediction component interaction tests
npm run build # production assets in dist/
```

Serve `dist/` with SPA fallback to `index.html` for `/login` and `/dashboard`.
When using the default relative API URL, configure your production web server to
proxy `/api/*` to FastAPI **before** its SPA fallback. Vite's development proxy
is not part of the production bundle. Alternatively, build with a CORS-enabled
`VITE_API_BASE_URL`. `npm run preview` serves built assets only, not the API proxy.

For a browser smoke check against an isolated test backend, sign in with a test
account, upload a generated workbook, check decimal overview totals, apply/clear
date and SKU filters, and upload an update to verify counts and automatic refresh.
Also check invalid credentials, row errors, unsupported file types, expiration,
logout, reload restoration, keyboard use, and a narrow mobile viewport. Use only
test accounts and a disposable test database for upload checks.

Prediction component tests use the existing Node test runner and React act with
a development-only jsdom environment. Synthetic API responses are confined to
tests; the application always requests the real backend.
