/**
 * Market sparklines: one small card per index and sector, drawn from the closes the backend scraped
 * (backend/diary/sources/yahoo.py). Styled in globals.css; the day's theme can restyle them.
 */

import { MarketChart } from "@/types";

const W = 100;
const H = 32;

function points(closes: number[]): string {
  const lo = Math.min(...closes);
  const span = Math.max(...closes) - lo || 1;
  return closes
    .map((v, i) => `${((i / (closes.length - 1)) * W).toFixed(2)},${(H - 2 - ((v - lo) / span) * (H - 4)).toFixed(2)}`)
    .join(" ");
}

const number = (v: number) => v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function MarketCharts({ charts }: { charts: MarketChart[] }) {
  const groups = [...new Set(charts.map((c) => c.group))];
  return (
    <div className="diary-markets-wrap">
      {groups.map((group) => (
        <figure key={group} className="diary-markets-group">
          <figcaption className="diary-markets-label">{group} · last {charts[0].closes.length} sessions</figcaption>
          <ul className="diary-markets">
            {charts
              .filter((c) => c.group === group && c.closes.length >= 2)
              .map((c) => {
                const up = c.change >= 0;
                const first = c.closes[0];
                const last = c.closes[c.closes.length - 1];
                return (
                  <li key={c.symbol} className={`diary-spark ${up ? "is-up" : "is-down"}`}>
                    <span className="diary-spark-label">{c.label}</span>
                    <span className="diary-spark-value">{number(last)}</span>
                    <span className="diary-spark-change">
                      {up ? "▲" : "▼"} {Math.abs(c.change).toFixed(2)}%
                    </span>
                    <svg
                      className="diary-spark-line"
                      viewBox={`0 0 ${W} ${H}`}
                      preserveAspectRatio="none"
                      role="img"
                      aria-label={`${c.label} over ${c.closes.length} sessions: ${number(first)} to ${number(last)}`}
                    >
                      <polyline
                        points={points(c.closes)}
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinejoin="round"
                        strokeLinecap="round"
                        vectorEffect="non-scaling-stroke"
                      />
                    </svg>
                  </li>
                );
              })}
          </ul>
        </figure>
      ))}
    </div>
  );
}
