import { useRef, useState, type DragEvent } from "react";
import {
  ArrowUpRight,
  CheckCircle2,
  FileSpreadsheet,
  Upload,
  X,
  Info,
} from "lucide-react";
import { api } from "../../services/api";
import type { UploadResponse } from "../../types/api";
import { ErrorNotice, Spinner } from "../layout/Feedback";
import { formatCount } from "../../lib/format";

export function ExcelUpload({ onSuccess }: { onSuccess: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [pending, setPending] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<Error | string>("");
  const [result, setResult] = useState<UploadResponse | null>(null);
  const dragDepth = useRef(0);
  function select(candidate?: File) {
    setResult(null);
    setError("");
    if (!candidate) return;
    if (!candidate.name.toLowerCase().endsWith(".xlsx")) {
      setFile(null);
      setError(
        "Please choose an Excel .xlsx file. CSV and .xls files are not supported.",
      );
      return;
    }
    if (!candidate.size) {
      setFile(null);
      setError(
        "This file is empty. Choose a workbook containing sales records.",
      );
      return;
    }
    setFile(candidate);
  }
  function drop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    if (pending) return;
    if (event.dataTransfer.files.length !== 1) {
      setError("Please select one Excel workbook at a time.");
      return;
    }
    select(event.dataTransfer.files[0]);
  }
  async function upload() {
    if (!file || pending) return;
    setPending(true);
    setError("");
    setResult(null);
    try {
      const response = await api.upload(file);
      setResult(response);
      setFile(null);
      onSuccess();
    } catch (failure) {
      setError(
        failure instanceof Error ? failure : "Upload failed. Please try again.",
      );
    } finally {
      setPending(false);
    }
  }
  return (
    <section className="card upload-card" aria-labelledby="upload-title">
      <div className="section-heading">
        <div>
          <span className="upload-heading-icon">
            <Upload size={19} />
          </span>
          <h2 id="upload-title">Bring your sales together</h2>
          <p>A spreadsheet in. A clearer picture out.</p>
        </div>
      </div>
      <div className="upload-body">
        <input
          ref={input}
          className="visually-hidden"
          type="file"
          id="excel-file"
          tabIndex={-1}
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          aria-label="Choose Excel workbook"
          disabled={pending}
          onChange={(e) => {
            select(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        <div
          className={`dropzone ${dragging ? "is-dragging" : ""} ${pending ? "is-pending" : ""}`}
          onDragOver={(e) => e.preventDefault()}
          onDragEnter={(e) => {
            e.preventDefault();
            dragDepth.current++;
            if (!pending) setDragging(true);
          }}
          onDragLeave={() => {
            dragDepth.current--;
            if (dragDepth.current === 0) setDragging(false);
          }}
          onDrop={drop}
        >
          <span className="file-icon">
            <FileSpreadsheet size={29} strokeWidth={1.5} />
          </span>
          <strong>Drop your workbook here</strong>
          <p>
            or{" "}
            <button
              type="button"
              className="text-button"
              disabled={pending}
              onClick={() => input.current?.click()}
            >
              browse files
            </button>
          </p>
          <span className="file-type">EXCEL .XLSX ONLY</span>
        </div>
        {file && (
          <div className="selected-file">
            <FileSpreadsheet size={20} />
            <div>
              <strong title={file.name}>{file.name}</strong>
              <span>
                {Math.max(1, Math.round(file.size / 1024))} KB · Ready to upload
              </span>
            </div>
            <button
              className="icon-button"
              disabled={pending}
              onClick={() => {
                setFile(null);
                setError("");
              }}
              aria-label="Remove selected file"
            >
              <X size={16} />
            </button>
          </div>
        )}
        <button
          className="button button-primary upload-button"
          disabled={!file || pending}
          onClick={upload}
        >
          {pending ? (
            <>
              <Spinner />
              Uploading…
            </>
          ) : (
            <>
              Upload sales
              <ArrowUpRight size={17} />
            </>
          )}
        </button>
        {pending && (
          <p className="upload-pending" role="status">
            Validating and saving your workbook. Keep this page open.
          </p>
        )}
        {error && <ErrorNotice error={error} />}
        {result && (
          <div className="upload-success" role="status">
            <div>
              <CheckCircle2 size={18} />
              <strong>Upload successful</strong>
            </div>
            <dl>
              <div>
                <dt>Rows processed</dt>
                <dd>{formatCount(result.row_count)}</dd>
              </div>
              <div>
                <dt>Inserted</dt>
                <dd>{formatCount(result.inserted_count)}</dd>
              </div>
              <div>
                <dt>Updated</dt>
                <dd>{formatCount(result.updated_count)}</dd>
              </div>
            </dl>
            <p>Your sales view is refreshing with the latest records.</p>
          </div>
        )}
        <div className="upload-guide">
          <h3>
            <Info size={15} />
            Before you upload
          </h3>
          <p>Include exactly these four columns:</p>
          <div className="column-tags">
            <code>shop_id</code>
            <code>sku_name</code>
            <code>num_units_sold</code>
            <code>date</code>
          </div>
          <p>
            Every row must belong to your shop. Existing sales for the same date
            and SKU are replaced, not added together.
          </p>
        </div>
      </div>
    </section>
  );
}
