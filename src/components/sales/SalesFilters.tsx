import { useState, type FormEvent } from "react";
import { Search, SlidersHorizontal } from "lucide-react";
import type { SalesFilters as Filters } from "../../types/api";

export function SalesFilters({
  onApply,
}: {
  onApply: (filters: Filters) => void;
}) {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [sku, setSku] = useState("");
  const [error, setError] = useState("");
  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (start && end && start > end) {
      setError("Start date must be on or before end date.");
      return;
    }
    if (sku && !sku.trim()) {
      setError("SKU name must not be blank.");
      return;
    }
    setError("");
    onApply({
      start_date: start || undefined,
      end_date: end || undefined,
      sku_name: sku || undefined,
    });
  }
  function clear() {
    setStart("");
    setEnd("");
    setSku("");
    setError("");
    onApply({});
  }
  return (
    <form className="filters" onSubmit={apply} aria-label="Filter sales">
      <div className="filter-heading">
        <span>
          <SlidersHorizontal size={14} />
          FILTER SALES
        </span>
        <button type="button" className="text-button" onClick={clear}>
          Clear filters
        </button>
      </div>
      <div className="filter-grid">
        <div className="field">
          <label htmlFor="start-date">Start date</label>
          <input
            type="date"
            id="start-date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="end-date">End date</label>
          <input
            type="date"
            id="end-date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </div>
        <div className="field sku-field">
          <label htmlFor="sku">SKU name</label>
          <input
            id="sku"
            placeholder="Exact SKU name"
            value={sku}
            onChange={(e) => setSku(e.target.value)}
          />
        </div>
        <button className="button button-secondary filter-submit">
          <Search size={16} />
          Apply
        </button>
      </div>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
