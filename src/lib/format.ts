import type { SalesRecord } from "../types/api";

const integers = new Intl.NumberFormat("en-US");
export const formatCount = (value: number) => integers.format(value);

// Sum integer hundredths so NUMERIC(12,2) values do not accumulate float errors.
export function totalUnits(rows: SalesRecord[]): string {
  const cents = rows.reduce((sum, row) => {
    const [whole, fraction = ""] = String(row.num_units_sold).split(".");
    return (
      sum + BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0").slice(0, 2))
    );
  }, 0n);
  return `${cents / 100n}.${(cents % 100n).toString().padStart(2, "0")}`;
}
export function formatUnits(value: string): string {
  const [whole, fraction = ""] = String(value).split(".");
  const decimals = fraction.replace(/0+$/, "");
  return `${integers.format(BigInt(whole))}${decimals ? `.${decimals}` : ""}`;
}
export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}
