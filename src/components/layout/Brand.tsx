import { ChartNoAxesColumnIncreasing } from "lucide-react";

export function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark">
        <ChartNoAxesColumnIncreasing
          size={22}
          strokeWidth={2.5}
          aria-hidden="true"
        />
      </span>
      <span>
        SalesFlow<span className="brand-dot">.</span>
      </span>
    </div>
  );
}
