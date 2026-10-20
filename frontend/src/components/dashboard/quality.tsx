import { Check, CheckCheck, ChevronRight } from "lucide-react";
import type { Profile } from "@/lib/schemas";
import { label, number } from "@/lib/utils";
export function Quality({ profile }: { profile: Profile }) {
  return (
    <section className="quality-section">
      <div className="section-heading">
        <div>
          <h2>A closer look at data quality</h2>
          <p>Understand the foundation of your analysis.</p>
        </div>
        <span className="tag">
          <CheckCheck size={13} />
          Deterministic profile
        </span>
      </div>
      <div className="panel quality-panel">
        <div className="quality-scroll">
          <table>
            <thead>
              <tr>
                <th>Variable</th>
                <th>Type</th>
                <th>Missing</th>
                <th>Unique</th>
                <th>Mean</th>
                <th>Median</th>
                <th>SD (n−1)</th>
                <th>Min / Max</th>
              </tr>
            </thead>
            <tbody>
              {profile.columns.map((c) => (
                <tr key={c.name}>
                  <td>{label(c.name)}</td>
                  <td>
                    <span className={`type-pill ${c.kind}`}>{c.kind}</span>
                  </td>
                  <td>
                    {number(c.missing_percent)}%{" "}
                    <span className="muted">({c.missing_count})</span>
                  </td>
                  <td>{number(c.unique_count)}</td>
                  <td>{number(c.mean)}</td>
                  <td>{number(c.median)}</td>
                  <td>{number(c.std)}</td>
                  <td>
                    {c.kind === "numeric"
                      ? `${number(c.minimum)} / ${number(c.maximum)}`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {profile.warnings.length > 0 ? (
          <details className="quality-warnings">
            <summary>
              {profile.warnings.length} data quality notes{" "}
              <ChevronRight size={14} />
            </summary>
            <ul>
              {profile.warnings.map((warning, i) => (
                <li key={i}>{warning}</li>
              ))}
            </ul>
          </details>
        ) : (
          <div className="quality-clear">
            <Check size={14} />
            No missing or constant columns detected.
          </div>
        )}
      </div>
    </section>
  );
}
