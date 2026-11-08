import { useState, type FormEvent } from "react";
import { Button, Panel, StatTile } from "../../design-system/hud";
import { useApiJson } from "../useApi";
import { ResourceState } from "../ui";
import {
  PRODUCTIVITY_BASE,
  formatDay,
  formatMoney,
  send,
  sparklinePoints,
  trendPercent,
  type Page,
  type SalesRecord,
  type SalesSummary,
} from "./api";

function Trend({ summary }: { summary: SalesSummary }) {
  const pct = trendPercent(summary);
  if (pct == null) return <span className="prod-trend" data-direction="flat">No prior sales to compare</span>;
  const direction = pct > 0 ? "up" : pct < 0 ? "down" : "flat";
  const arrow = direction === "up" ? "▲" : direction === "down" ? "▼" : "■";
  return (
    <span className="prod-trend" data-direction={direction}>
      <span aria-hidden="true">{arrow}</span> {Math.abs(pct).toFixed(1)}% vs previous
      <span className="prod-sr"> ({direction === "up" ? "up" : direction === "down" ? "down" : "unchanged"})</span>
    </span>
  );
}

function Tile({ label, state }: { label: string; state: ReturnType<typeof useApiJson<SalesSummary>> }) {
  if (state.status !== "ok" || !state.data) {
    return <StatTile label={label} value="—" hint={state.status === "loading" ? "Loading…" : state.status === "missing" ? "Not available" : "Unavailable"} />;
  }
  return <StatTile label={label} value={formatMoney(state.data.total, state.data.currency)} hint={<Trend summary={state.data} />} />;
}

function Sparkline({ series, currency }: { series: SalesSummary["series"]; currency: string }) {
  const values = series.map((p) => p.total);
  const total = values.reduce((a, b) => a + b, 0);
  return (
    <svg className="prod-spark" viewBox="0 0 240 48" role="img" aria-label={`Daily sales this week, ${formatMoney(total, currency)} in total`} preserveAspectRatio="none">
      <polyline className="prod-spark__line" fill="none" points={sparklinePoints(values, 240, 48)} />
    </svg>
  );
}

export function SalesPanel() {
  const day = useApiJson<SalesSummary>(`${PRODUCTIVITY_BASE}/sales/summary?period=day`);
  const week = useApiJson<SalesSummary>(`${PRODUCTIVITY_BASE}/sales/summary?period=week`);
  const month = useApiJson<SalesSummary>(`${PRODUCTIVITY_BASE}/sales/summary?period=month`);
  const records = useApiJson<Page<SalesRecord>>(`${PRODUCTIVITY_BASE}/sales/records?limit=8`);
  const [form, setForm] = useState({ amount: "", source: "", customer: "", product: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = () => { day.reload(); week.reload(); month.reload(); records.reload(); };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const amount = Number(form.amount);
    if (!form.amount.trim() || !Number.isFinite(amount) || amount <= 0) {
      setError("Enter a sale amount greater than zero.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await send("POST", "/sales/records", { amount, source: form.source, customer: form.customer, product: form.product });
      setForm({ amount: "", source: "", customer: "", product: "" });
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not log the sale");
    } finally {
      setBusy(false);
    }
  };

  const bind = (key: keyof typeof form) => ({
    value: form[key],
    onChange: (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value })),
  });
  const items = records.data?.items ?? [];

  return (
    <Panel title="Sales">
      <div className="shell-stats prod-tiles">
        <Tile label="Today" state={day} />
        <Tile label="This week" state={week} />
        <Tile label="This month" state={month} />
      </div>
      {week.status === "ok" && week.data && week.data.series.length > 1 && (
        <>
          <p className="shell-card__meta" aria-hidden="true">Daily sales this week</p>
          <Sparkline series={week.data.series} currency={week.data.currency} />
        </>
      )}

      <form className="prod-quick" onSubmit={(e) => void submit(e)} noValidate aria-label="Log a sale">
        <label className="prod-field">Amount<input className="shell-input" inputMode="decimal" {...bind("amount")} /></label>
        <label className="prod-field">Channel<input className="shell-input" {...bind("source")} maxLength={80} /></label>
        <label className="prod-field">Customer<input className="shell-input" {...bind("customer")} maxLength={120} /></label>
        <label className="prod-field">Product<input className="shell-input" {...bind("product")} maxLength={120} /></label>
        <Button variant="primary" type="submit" disabled={busy}>Log sale</Button>
      </form>
      {error && <p className="shell-state" data-kind="error" role="alert">{error}</p>}

      <ResourceState status={records.status} error={records.error} empty={items.length === 0} noun="sales" onRetry={records.reload}>
        <table className="prod-table">
          <caption className="prod-sr">Recent sales</caption>
          <thead><tr><th scope="col">Date</th><th scope="col">Amount</th><th scope="col">Channel</th><th scope="col">Customer</th><th scope="col">Product</th></tr></thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.id}>
                <td>{formatDay(r.occurredOn)}</td>
                <td>{formatMoney(r.amount, r.currency)}</td>
                <td>{r.source || "—"}</td>
                <td>{r.customer || "—"}</td>
                <td>{r.product || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ResourceState>
    </Panel>
  );
}
