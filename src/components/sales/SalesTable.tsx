import { ListFilter, RefreshCw } from "lucide-react";
import type { SalesResponse } from "../../types/api";
import { formatCount, formatDate, formatUnits } from "../../lib/format";
import { ErrorNotice, Spinner } from "../layout/Feedback";
import { SalesFilters } from "./SalesFilters";
import type { SalesFilters as Filters } from "../../types/api";

interface Props {
  data: SalesResponse | null;
  loading: boolean;
  error: string;
  filtered: boolean;
  refresh: () => void;
  onApply: (filters: Filters) => void;
}
export function SalesTable({
  data,
  loading,
  error,
  filtered,
  refresh,
  onApply,
}: Props) {
  return (
    <section className="card sales-card" aria-labelledby="sales-title">
      <div className="section-heading">
        <div>
          <div className="title-row">
            <h2 id="sales-title">Sales records</h2>
            {data && (
              <span className="count-badge">{formatCount(data.total)}</span>
            )}
          </div>
          <p>Your daily sales, down to the details.</p>
        </div>
        <button
          className="icon-button"
          onClick={refresh}
          disabled={loading}
          aria-label="Refresh sales"
          title="Refresh sales"
        >
          <RefreshCw size={17} className={loading ? "spinner" : ""} />
        </button>
      </div>
      <SalesFilters onApply={onApply} />
      <div aria-live="polite" aria-busy={loading}>
        {loading ? (
          <div className="table-state">
            <Spinner label="Loading sales" />
            <p>Loading your sales…</p>
          </div>
        ) : error ? (
          <div className="table-error">
            <ErrorNotice error={error} />
            <button className="button button-secondary" onClick={refresh}>
              Try again
            </button>
          </div>
        ) : data && data.items.length > 0 ? (
          <>
            <div
              className="table-scroll"
              tabIndex={0}
              role="region"
              aria-label="Sales records table"
            >
              <table>
                <thead>
                  <tr>
                    <th scope="col">Date</th>
                    <th scope="col">SKU</th>
                    <th scope="col" className="numeric">
                      Units sold
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((row) => (
                    <tr key={row.id}>
                      <td className="date-cell">{formatDate(row.date)}</td>
                      <td>
                        <span className="sku-name">{row.sku_name}</span>
                      </td>
                      <td className="numeric">
                        {formatUnits(row.num_units_sold)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="table-footer">
              <span>
                {formatCount(data.total)}{" "}
                {data.total === 1 ? "record" : "records"}
                {filtered ? " matching your filters" : " in your shop"}
              </span>
              <span>Oldest first</span>
            </div>
          </>
        ) : (
          <div className="table-state empty-state">
            <span className="empty-icon">
              <ListFilter size={25} />
            </span>
            <h3>
              {filtered ? "No matching sales" : "Your sales story starts here"}
            </h3>
            <p>
              {filtered
                ? "Try a different date range or SKU name."
                : "Upload an Excel workbook to see your shop’s sales."}
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
