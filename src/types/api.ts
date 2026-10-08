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
