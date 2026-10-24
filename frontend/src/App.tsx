import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchDecision, fetchOverview } from "./api";
import type { Decision, Overview } from "./types";

const DAYS = Array.from({ length: 31 }, (_, i) => {
  const d = i + 1;
  return `2026-01-${String(d).padStart(2, "0")}`;
});

function fmt(n: number | null | undefined, digits = 0) {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("en-GB", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="card">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {hint ? <div className="hint">{hint}</div> : null}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState<"decision" | "accuracy">("decision");
  const [day, setDay] = useState("2026-01-08");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchOverview()
      .then(setOverview)
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    fetchDecision(day)
      .then(setDecision)
      .catch((err: Error) => setError(err.message));
  }, [day]);

  const heatMax = useMemo(() => {
    const values = overview?.byDay.map((d) => d.maeMw ?? 0) ?? [1];
    return Math.max(...values, 1);
  }, [overview]);

  if (error) {
    return (
      <div className="app">
        <h1>Meridian</h1>
        <p>Could not load the desk. Is the API running?</p>
        <p className="muted">{error}</p>
      </div>
    );
  }

  if (!overview || !decision) {
    return (
      <div className="app">
        <p className="muted">Loading GB wind desk…</p>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="top">
        <div>
          <div className="brand">Meridian · pilot</div>
          <h1>Day-ahead wind, before the 09:20 gate</h1>
          <p className="lede">
            National wind the GB wholesale desk could actually see when bidding
            EPEX 60-minute day-ahead for January 2026 delivery — and how wrong
            that vintage was versus Elexon outturn.
          </p>
        </div>
        <div className="tabs">
          <button
            className={tab === "decision" ? "active" : ""}
            onClick={() => setTab("decision")}
          >
            Decision board
          </button>
          <button
            className={tab === "accuracy" ? "active" : ""}
            onClick={() => setTab("accuracy")}
          >
            Forecast skill
          </button>
        </div>
      </header>

      {tab === "decision" ? (
        <DecisionBoard
          overview={overview}
          decision={decision}
          day={day}
          onDay={setDay}
        />
      ) : (
        <AccuracyLab overview={overview} heatMax={heatMax} />
      )}

      <footer className="footer">
        Source: Elexon BMRS FUELHH (WIND) and WINDFOR only. Decision vintage is
        the latest WINDFOR published before 09:20 UK on D-1. WINDFOR is hourly;
        two FUELHH settlement periods are averaged to the matching hour. Error =
        forecast − actual. Persistent bias can mix meteorological error with any
        coverage difference between the two BMRS series.
      </footer>
    </div>
  );
}

function DecisionBoard({
  overview,
  decision,
  day,
  onDay,
}: {
  overview: Overview;
  decision: Decision;
  day: string;
  onDay: (value: string) => void;
}) {
  const used = decision.vintages.find((v) => v.publishTime === decision.publishTimeUsed);
  return (
    <>
      <div className="toolbar">
        <label>
          Delivery day{" "}
          <select value={day} onChange={(e) => onDay(e.target.value)}>
            {DAYS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <span className="muted">
          Bid by {decision.decisionCutoffUk} · vintage{" "}
          {decision.publishTimeUsed ?? "none"}
          {used ? ` (${used.hoursBeforeGate}h before gate)` : ""}
        </span>
      </div>

      <div className="grid">
        <Metric
          label="Forecast energy"
          value={`${fmt(decision.forecastEnergyGwh, 1)} GWh`}
          hint="Hourly WINDFOR, decision vintage"
        />
        <Metric
          label="Metered wind"
          value={`${fmt(decision.actualEnergyGwh, 1)} GWh`}
          hint="FUELHH WIND, hourly average"
        />
        <Metric
          label="Day MAE"
          value={`${fmt(decision.daySummary.maeMw)} MW`}
          hint={`Bias ${fmt(decision.daySummary.biasMw)} MW`}
        />
        <Metric
          label="Uncertainty band"
          value={`±${fmt(decision.uncertaintyBandMw)} MW`}
          hint="January P90 |error| on DA vintages"
        />
      </div>

      <div className="panel">
        <h2>What you would have bought against</h2>
        <p className="muted">
          Peak {fmt(decision.peakForecastMw)} MW · trough{" "}
          {fmt(decision.troughForecastMw)} MW. Dashed lines are the month’s 90th
          percentile absolute error — a buffer for residual thermal / ID cover.
        </p>
        <div className="chart">
          <ResponsiveContainer>
            <ComposedChart data={decision.curve}>
              <CartesianGrid stroke="#2a3833" strokeDasharray="3 3" />
              <XAxis dataKey="hourUk" tick={{ fill: "#9aa89a" }} />
              <YAxis tick={{ fill: "#9aa89a" }} />
              <Tooltip
                contentStyle={{ background: "#141c19", border: "1px solid #2a3833" }}
              />
              <Line
                type="monotone"
                dataKey="bandHighMw"
                stroke="#d6f071"
                strokeDasharray="4 4"
                strokeOpacity={0.4}
                dot={false}
                name="P90 high"
              />
              <Line
                type="monotone"
                dataKey="bandLowMw"
                stroke="#d6f071"
                strokeDasharray="4 4"
                strokeOpacity={0.4}
                dot={false}
                name="P90 low"
              />
              <Line
                type="monotone"
                dataKey="forecastMw"
                stroke="#d6f071"
                dot={false}
                strokeWidth={2}
                name="Decision forecast"
              />
              <Line
                type="monotone"
                dataKey="actualMw"
                stroke="#7ad1c4"
                dot={false}
                strokeWidth={2}
                name="Outturn"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="row">
        <div className="panel">
          <h2>Vintages on D-1</h2>
          <p className="muted">
            Greyed publishes arrived at or after the 09:20 gate and must not be
            used for the 60-minute auction. Latest usable is highlighted.
          </p>
          <div className="vintage">
            {decision.vintages.map((v) => (
              <span
                key={v.publishTime}
                className={`pill ${v.usableAtDaGate ? "ok" : "no"}`}
              >
                {v.publishTime.replace("T", " ").replace("Z", " UTC")}
                {v.publishTime === decision.publishTimeUsed ? " · used" : ""}
              </span>
            ))}
          </div>
        </div>
        <div className="panel">
          <h2>Why this vintage</h2>
          <ul className="notes">
            <li>{overview.meta.decisionRule}</li>
            <li>
              NESO refreshes WINDFOR several times a day. Using “latest” after
              09:20 would leak information the desk did not have at bid time.
            </li>
            <li>
              Month-wide, that honest vintage over-forecast wind by{" "}
              {fmt(overview.summary.biasMw)} MW on average — buy more residual
              cover than a raw forecast suggests.
            </li>
          </ul>
        </div>
      </div>
    </>
  );
}

function AccuracyLab({
  overview,
  heatMax,
}: {
  overview: Overview;
  heatMax: number;
}) {
  const s = overview.summary;
  return (
    <>
      <div className="grid">
        <Metric label="MAE" value={`${fmt(s.maeMw)} MW`} hint={`${s.n} aligned hours`} />
        <Metric label="RMSE" value={`${fmt(s.rmseMw)} MW`} />
        <Metric
          label="Bias"
          value={`${fmt(s.biasMw)} MW`}
          hint={`${fmt(s.overforecastHoursPct, 0)}% of hours over-forecast`}
        />
        <Metric label="MAPE" value={`${fmt(s.mapePct, 1)}%`} />
        <Metric label="P50 |error|" value={`${fmt(s.p50AbsErrorMw)} MW`} />
        <Metric label="P90 |error|" value={`${fmt(s.p90AbsErrorMw)} MW`} />
        <Metric
          label="Energy gap"
          value={`${fmt(s.energyErrorGwh, 1)} GWh`}
          hint={`${fmt(s.forecastEnergyGwh, 0)} vs ${fmt(s.actualEnergyGwh, 0)} GWh`}
        />
        <Metric
          label="Within ±1 GW"
          value={`${fmt(s.within1000MwPct, 1)}%`}
          hint={`${fmt(s.within500MwPct, 1)}% within ±500 MW`}
        />
      </div>

      <div className="panel">
        <h2>What this means for the book</h2>
        <ul className="notes">
          {overview.implications.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </div>

      <div className="row">
        <div className="panel">
          <h2>Error by hour (UK)</h2>
          <div className="chart">
            <ResponsiveContainer>
              <ComposedChart data={overview.byHour}>
                <CartesianGrid stroke="#2a3833" strokeDasharray="3 3" />
                <XAxis dataKey="hourUk" tick={{ fill: "#9aa89a" }} />
                <YAxis tick={{ fill: "#9aa89a" }} />
                <Tooltip
                  contentStyle={{ background: "#141c19", border: "1px solid #2a3833" }}
                />
                <Bar dataKey="maeMw" fill="#d6f071" name="MAE MW" />
                <Line dataKey="biasMw" stroke="#7ad1c4" dot={false} name="Bias MW" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="panel">
          <h2>Error by actual wind level</h2>
          <div className="chart">
            <ResponsiveContainer>
              <ComposedChart data={overview.byWindLevel}>
                <CartesianGrid stroke="#2a3833" strokeDasharray="3 3" />
                <XAxis dataKey="level" tick={{ fill: "#9aa89a" }} />
                <YAxis tick={{ fill: "#9aa89a" }} />
                <Tooltip
                  contentStyle={{ background: "#141c19", border: "1px solid #2a3833" }}
                />
                <Bar dataKey="maeMw" fill="#7ad1c4" name="MAE MW" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>Daily MAE calendar</h2>
        <p className="muted">Darker cells are harder days for the decision-time vintage.</p>
        <div className="heat">
          {overview.byDay.map((d) => {
            const mae = d.maeMw ?? 0;
            const t = mae / heatMax;
            return (
              <div
                key={d.deliveryDate}
                className="cell"
                style={{
                  background: `rgba(214, 240, 113, ${0.08 + t * 0.45})`,
                }}
              >
                <div>{d.deliveryDate.slice(8)}</div>
                <div>{fmt(d.maeMw)} MW</div>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
