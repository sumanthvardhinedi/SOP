import { AlertCircle, CheckCircle2, LoaderCircle } from "lucide-react";
import { ApiError } from "../../services/api";

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <LoaderCircle className="spinner" size={18} role="img" aria-label={label} />
  );
}
export function SuccessNotice({ message }: { message: string }) {
  return (
    <div className="notice notice-success" role="status">
      <CheckCircle2 size={18} aria-hidden="true" />
      <div>
        <p>{message}</p>
      </div>
    </div>
  );
}
export function ErrorNotice({ error }: { error: Error | string }) {
  const issues = error instanceof ApiError ? error.issues : [];
  return (
    <div className="notice notice-error" role="alert">
      <AlertCircle size={18} aria-hidden="true" />
      <div>
        <p>{typeof error === "string" ? error : error.message}</p>
        {issues.length > 0 && (
          <ul className="error-list">
            {issues.map((issue, index) => (
              <li key={index}>
                {issue.row ? `Row ${issue.row}: ` : ""}
                {issue.message}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
