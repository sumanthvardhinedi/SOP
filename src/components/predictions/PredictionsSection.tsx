import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  CalendarDays,
  ChartNoAxesCombined,
  Info,
  Package,
} from "lucide-react";
import { api, ApiError } from "../../services/api";
import type { ForecastResponse } from "../../types/api";
import { formatCount, formatDate, formatUnits } from "../../lib/format";
import { ErrorNotice, Spinner } from "../layout/Feedback";

export function PredictionsSection() {
  const [result, setResult] = useState<ForecastResponse | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const request = useRef<AbortController | null>(null);

  useEffect(() => () => request.current?.abort(), []);

  async function generate() {
    // Guard rapid clicks as well as disabling the button while React updates.
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setPending(true);
    setError(null);
    setResult(null);
    try {
      const response = await api.generatePrediction(controller.signal);
      if (!controller.signal.aborted) setResult(response);
    } catch (failure) {
      if (!controller.signal.aborted) {
        setError(
          failure instanceof ApiError && failure.status === 404
            ? new ApiError(
                404,
                "No sales data was found for predictions. Upload sales history and try again.",
              )
            : failure instanceof Error
              ? failure
              : new Error("Unable to generate a prediction. Please try again."),
        );
      }
    } finally {
      if (!controller.signal.aborted) setPending(false);
      if (request.current === controller) request.current = null;
    }
  }

  // Display-only summation of returned integer predictions, never client inference.
  const totalUnits =
    result?.items.reduce(
      (sum, item) => sum + BigInt(item.predicted_units),
      0n,
    ) ?? 0n;

  return (
    <section
      className="card predictions-card"
      aria-labelledby="predictions-title"
    >
      <div className="section-heading predictions-heading">
        <div className="predictions-heading-copy">
          <span className="prediction-icon">
            <ChartNoAxesCombined size={21} aria-hidden="true" />
          </span>
          <div>
            <h2 id="predictions-title">Predictions</h2>
            <p>A look ahead, grounded in your shop’s sales history.</p>
          </div>
        </div>
        <button
          className="button button-primary"
          onClick={() => void generate()}
          disabled={pending}
        >
          {pending ? (
            <>
              <Spinner />
              Generating prediction...
            </>
          ) : (
            <>
              Generate Prediction
              <ArrowRight size={16} aria-hidden="true" />
            </>
          )}
        </button>
      </div>
      <p className="prediction-context">
        Uses all available shop history. Sales filters do not apply.
      </p>
      <div className="prediction-content" aria-busy={pending}>
        {pending && (
          <div className="prediction-state" role="status">
            <Spinner label="Computing forecast" />
            <p>Generating prediction...</p>
            <span>
              This may take a moment while your sales history is analyzed.
            </span>
          </div>
        )}
        {error && (
          <div className="prediction-error">
            <ErrorNotice error={error} />
            <button
              className="button button-secondary"
              onClick={() => void generate()}
            >
              Try again
            </button>
          </div>
        )}
        {!pending && !error && !result && (
          <div className="prediction-state prediction-initial">
            <CalendarDays size={25} aria-hidden="true" />
            <h3>Turn your sales history into a look ahead</h3>
            <p>
              Generate SKU predictions for the day after your shop’s latest
              recorded sale.
            </p>
          </div>
        )}
        {result && (
          <>
            <p className="prediction-date" role="status">
              {result.forecast_date ? (
                <>
                  Prediction date:{" "}
                  <time dateTime={result.forecast_date}>
                    {formatDate(result.forecast_date)}
                  </time>
                </>
              ) : (
                "No prediction date available yet."
              )}
            </p>
            {result.items.length > 0 ? (
              <>
                <div
                  className="prediction-summary"
                  role="group"
                  aria-label="Prediction summary"
                >
                  <div className="metric">
                    <div className="metric-top">
                      <span>Predicted SKUs</span>
                      <Package size={17} aria-hidden="true" />
                    </div>
                    <p className="prediction-value">
                      {formatCount(result.total)}
                    </p>
                  </div>
                  <div className="metric">
                    <div className="metric-top">
                      <span>Total Predicted Units</span>
                      <ChartNoAxesCombined size={17} aria-hidden="true" />
                    </div>
                    <p className="prediction-value">
                      {formatUnits(totalUnits.toString())}
                    </p>
                  </div>
                </div>
                <div
                  className="table-scroll"
                  tabIndex={0}
                  role="region"
                  aria-label="SKU predictions"
                >
                  <table>
                    <caption className="visually-hidden">
                      Predicted units per SKU for {result.forecast_date}
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">SKU</th>
                        <th scope="col" className="numeric">
                          Predicted Units
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.items.map((item) => (
                        <tr key={item.sku_name}>
                          <td>
                            <span className="sku-name">{item.sku_name}</span>
                          </td>
                          <td className="numeric">
                            {formatUnits(
                              BigInt(item.predicted_units).toString(),
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <div className="prediction-state" role="status">
                <span className="empty-icon">
                  <CalendarDays size={24} aria-hidden="true" />
                </span>
                <h3>
                  {result.status === "no_sales"
                    ? "No sales history yet"
                    : "Not enough historical data to generate predictions yet."}
                </h3>
                <p>
                  {result.status === "no_sales"
                    ? "Upload sales history to get started. "
                    : ""}
                  The current model skips incomplete histories. Prediction needs
                  28 consecutive daily records per SKU; training needs at least
                  one SKU with 29 consecutive days.
                </p>
              </div>
            )}
            {result.skipped.length > 0 && (
              <details className="prediction-skipped">
                <summary>
                  {formatCount(result.skipped.length)}{" "}
                  {result.skipped.length === 1 ? "SKU skipped" : "SKUs skipped"}{" "}
                  — view history requirements
                </summary>
                <ul>
                  {result.skipped.map((item) => (
                    <li key={item.sku_name}>
                      <strong>{item.sku_name}</strong>
                      <span>{item.message}</span>
                    </li>
                  ))}
                </ul>
              </details>
            )}
            {result.warnings.length > 0 && (
              <div
                className="prediction-warnings"
                role="note"
                aria-label="Prediction notices"
              >
                <Info size={16} aria-hidden="true" />
                <ul>
                  {result.warnings.map((warning, index) => (
                    <li key={index}>{warning}</li>
                  ))}
                </ul>
              </div>
            )}
            <p className="prediction-footnote">
              Based on stored sales at generation time. Regenerate after
              uploading new sales.
            </p>
          </>
        )}
      </div>
    </section>
  );
}
