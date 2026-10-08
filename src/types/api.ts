export interface User {
  id: number;
  name: string;
  email: string;
  shop_id: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}
export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface SalesRecord {
  id: number;
  date: string;
  shop_id: number;
  sku_name: string;
  /** PostgreSQL NUMERIC is serialized as a decimal string by the API. */
  num_units_sold: string;
}
export interface SalesResponse {
  items: SalesRecord[];
  total: number;
}
export interface SalesFilters {
  start_date?: string;
  end_date?: string;
  sku_name?: string;
}
export interface UploadResponse {
  success: true;
  row_count: number;
  inserted_count: number;
  updated_count: number;
}
export interface ValidationIssue {
  row?: number | null;
  column?: string | null;
  message: string;
}
export interface APIError {
  status: number;
  message: string;
  issues: ValidationIssue[];
}

/** Matches backend/app/ml/schemas.py; prediction values are whole units. */
export interface ForecastItem {
  sku_name: string;
  predicted_units: number;
}
export interface SkippedSKU {
  sku_name: string;
  reason: "incomplete_history" | "insufficient_training_data";
  message: string;
}
export interface ForecastResponse {
  status: "ok" | "no_sales" | "insufficient_history";
  forecast_date: string | null;
  items: ForecastItem[];
  total: number;
  training_rows: number;
  skipped: SkippedSKU[];
  warnings: string[];
}
