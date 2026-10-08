import { Layers3, Package, ChartNoAxesColumnIncreasing } from "lucide-react";
import { formatCount, formatUnits, totalUnits } from "../../lib/format";
import type { SalesResponse } from "../../types/api";

export function Overview({
  data,
  loading,
}: {
  data: SalesResponse | null;
  loading: boolean;
}) {
  const metrics = [
    {
      label: "Total records",
      value: data ? formatCount(data.total) : "—",
      detail: "Daily sales entries",
      icon: Layers3,
    },
    {
      label: "Unique SKUs",
      value: data
        ? formatCount(new Set(data.items.map((row) => row.sku_name)).size)
        : "—",
      detail: "Products in this view",
      icon: Package,
    },
    {
      label: "Total units sold",
      value: data ? formatUnits(totalUnits(data.items)) : "—",
      detail: "Across displayed records",
      icon: ChartNoAxesColumnIncreasing,
    },
  ];
  return (
    <section
      className="overview"
      aria-label="Sales overview"
      aria-busy={loading}
    >
      {metrics.map(({ label, value, detail, icon: Icon }) => (
        <article className="card metric" key={label}>
          <div className="metric-top">
            <span>{label}</span>
            <span className="metric-icon">
              <Icon size={18} aria-hidden="true" />
            </span>
          </div>
          <div className={`metric-value ${loading ? "metric-loading" : ""}`}>
            {loading ? <span className="skeleton" /> : value}
          </div>
          <p>{detail}</p>
        </article>
      ))}
    </section>
  );
}
