import { ArrowUpRight, ShieldCheck } from "lucide-react";
import { Header } from "../components/layout/Header";
import { Overview } from "../components/sales/Overview";
import { SalesTable } from "../components/sales/SalesTable";
import { ExcelUpload } from "../components/upload/ExcelUpload";
import { useSales } from "../hooks/useSales";

export function DashboardPage() {
  const sales = useSales();
  const filtered = Object.values(sales.filters).some(Boolean);
  return (
    <>
      <Header />
      <main className="dashboard">
        <div className="page-heading">
          <div>
            <span className="eyebrow">YOUR WORKSPACE</span>
            <h1>
              Sales, at a glance<span>.</span>
            </h1>
            <p>A clear view of what’s selling in your shop.</p>
          </div>
          <a href="#upload-title" className="button button-primary">
            Upload Excel
            <ArrowUpRight size={17} />
          </a>
        </div>
        <div className="overview-label">
          <span>Overview</span>
          <span>
            {filtered ? "Based on your active filters" : "All available sales"}
          </span>
        </div>
        <Overview data={sales.data} loading={sales.loading} />
        <div className="workspace-grid">
          <SalesTable
            {...sales}
            filtered={filtered}
            onApply={sales.setFilters}
          />
          <ExcelUpload onSuccess={sales.refresh} />
        </div>
        <footer className="dashboard-footer">
          <span>
            SalesFlow <span className="footer-divider">/</span> A little clarity
            goes a long way.
          </span>
          <span>
            <ShieldCheck size={14} />
            Only your shop. Always.
          </span>
        </footer>
      </main>
    </>
  );
}
