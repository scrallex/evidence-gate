import type {
  DashboardHealingCase,
  DashboardOverviewResponse,
  DashboardRiskAvoidedItem,
  DashboardSignal,
} from "../lib/types";
import { getDashboardOverview } from "../lib/api";

export const dynamic = "force-dynamic";

function formatPercentage(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatMinutes(value: number | null): string {
  if (value === null) {
    return "n/a";
  }
  if (value < 60) {
    return `${value.toFixed(0)}m`;
  }
  return `${(value / 60).toFixed(1)}h`;
}

function repoLabel(repoPath: string): string {
  const parts = repoPath.split("/").filter(Boolean);
  if (parts.length === 0) {
    return repoPath;
  }
  return parts.slice(-2).join("/");
}

function signalTone(signal: DashboardSignal): string {
  switch (signal.source_kind) {
    case "jira":
      return "signal-jira";
    case "slack":
      return "signal-slack";
    case "pagerduty":
      return "signal-pagerduty";
    case "incident":
      return "signal-incident";
    case "github":
      return "signal-github";
    default:
      return "signal-other";
  }
}

function MetricCard({
  eyebrow,
  value,
  label,
  detail,
}: {
  eyebrow: string;
  value: string;
  label: string;
  detail: string;
}) {
  return (
    <article className="metric-card">
      <p className="eyebrow">{eyebrow}</p>
      <p className="metric-value">{value}</p>
      <h3 className="metric-label">{label}</h3>
      <p className="metric-detail">{detail}</p>
    </article>
  );
}

function EmptyState({
  apiBaseUrl,
  error,
}: {
  apiBaseUrl: string;
  error: string | null;
}) {
  return (
    <section className="panel empty-state">
      <p className="eyebrow">Dashboard Offline</p>
      <h1>Start the FastAPI service and generate a few action decisions.</h1>
      <p>
        The stakeholder dashboard reads from
        {" "}
        <code>{apiBaseUrl}/v1/dashboard/overview</code>
        {" "}
        and turns recent audit history into the Risk Avoided feed and healing
        metrics.
      </p>
      <pre className="code-block">
        <code>{`uvicorn evidence_gate.api.main:app --app-dir app --reload
cd dashboard && npm install && npm run dev`}</code>
      </pre>
      {error ? <p className="error-note">Last load error: {error}</p> : null}
    </section>
  );
}

function RiskFeedCard({ item }: { item: DashboardRiskAvoidedItem }) {
  return (
    <article className="risk-card">
      <header className="risk-card-header">
        <div>
          <p className="eyebrow">{repoLabel(item.repo_path)}</p>
          <h3>{item.action_summary}</h3>
        </div>
        <div className={`status-pill ${item.status}`}>
          {item.status === "healed_on_retry" ? "Healed on retry" : "Still blocked"}
        </div>
      </header>

      <div className="meta-row">
        <span>{formatTimestamp(item.created_at)}</span>
        <span>Decision {item.decision_id.slice(0, 8)}</span>
        {item.healed_at ? <span>Resolved {formatTimestamp(item.healed_at)}</span> : null}
      </div>

      <div className="blast-grid">
        <div>
          <strong>{item.blast_radius.files}</strong>
          <span>files</span>
        </div>
        <div>
          <strong>{item.blast_radius.tests}</strong>
          <span>tests</span>
        </div>
        <div>
          <strong>{item.blast_radius.docs}</strong>
          <span>docs</span>
        </div>
        <div>
          <strong>{item.blast_radius.runbooks}</strong>
          <span>runbooks</span>
        </div>
      </div>

      <div className="card-section">
        <p className="section-label">Signals that influenced the block</p>
        {item.triggering_signals.length > 0 ? (
          <div className="signal-list">
            {item.triggering_signals.map((signal) => (
              <a
                key={`${signal.relation}-${signal.source}`}
                className={`signal-chip ${signalTone(signal)}`}
                href={signal.external_url ?? "#"}
                target={signal.external_url ? "_blank" : undefined}
                rel={signal.external_url ? "noreferrer" : undefined}
              >
                <span>{signal.label}</span>
                <strong>{signal.title}</strong>
              </a>
            ))}
          </div>
        ) : (
          <p className="subtle-copy">No Jira, Slack, or incident precedent was cited on this block.</p>
        )}
      </div>

      <div className="card-section">
        <p className="section-label">Why the gate intervened</p>
        <ul className="compact-list">
          {item.missing_evidence.slice(0, 3).map((entry) => (
            <li key={entry}>{entry}</li>
          ))}
        </ul>
      </div>

      <div className="card-footer">
        <div>
          <p className="section-label">Policy surface</p>
          <p className="subtle-copy">
            {item.policy_labels.length > 0 ? item.policy_labels.join(" • ") : "Default gate thresholds"}
          </p>
        </div>
        <div>
          <p className="section-label">Strongest evidence</p>
          <p className="subtle-copy mono-copy">
            {item.strongest_evidence_sources.slice(0, 2).join(" • ")}
          </p>
        </div>
      </div>
    </article>
  );
}

function HealingCaseRow({ item }: { item: DashboardHealingCase }) {
  return (
    <article className="heal-row">
      <div>
        <p className="eyebrow">{repoLabel(item.repo_path)}</p>
        <h4>{item.action_summary}</h4>
        <p className="subtle-copy mono-copy">
          {item.changed_paths.join(" • ")}
        </p>
      </div>
      <div className="heal-stats">
        <div>
          <strong>{item.retries_before_heal}</strong>
          <span>blocked tries</span>
        </div>
        <div>
          <strong>{formatMinutes(item.time_to_heal_minutes)}</strong>
          <span>to heal</span>
        </div>
      </div>
    </article>
  );
}

function StakeholderView({ overview }: { overview: DashboardOverviewResponse }) {
  const healing = overview.agent_healing;
  const metrics = overview.headline_metrics;
  const protectedSurface = `${metrics.protected_files} files`;
  const feed = overview.risk_avoided_feed;

  return (
    <main className="dashboard-shell">
      <section className="hero panel">
        <div className="hero-copy">
          <p className="eyebrow">Stakeholder View</p>
          <h1>Show the risk the gate prevented, not just the code it blocked.</h1>
          <p className="lede">
            Evidence Gate turns recent PR and agent decisions into an executive
            view: what blast radius was stopped, which operational signals were
            involved, and how often the agent actually repaired the change on retry.
          </p>
        </div>
        <div className="hero-meta">
          <div>
            <span className="hero-kicker">As of</span>
            <strong>{formatTimestamp(overview.generated_at)}</strong>
          </div>
          <div>
            <span className="hero-kicker">Audit Window</span>
            <strong>{overview.scanned_action_decisions} action decisions</strong>
          </div>
          <div>
            <span className="hero-kicker">Method</span>
            <strong>Blocked sequence inference from audit history</strong>
          </div>
        </div>
      </section>

      <section className="metrics-grid">
        <MetricCard
          eyebrow="Risk Avoided"
          value={String(metrics.blocked_actions)}
          label="Blocked actions"
          detail={`${metrics.blocked_sequences} unique sequences intercepted before merge or deploy.`}
        />
        <MetricCard
          eyebrow="Blast Surface"
          value={protectedSurface}
          label="Protected blast radius"
          detail={`${metrics.protected_tests} tests, ${metrics.protected_docs} docs, ${metrics.protected_runbooks} runbooks sat behind those blocks.`}
        />
        <MetricCard
          eyebrow="Operational Context"
          value={String(metrics.incident_linked_blocks)}
          label="Incident-linked blocks"
          detail="Recent decisions that matched Jira, Slack, PagerDuty, or postmortem context."
        />
        <MetricCard
          eyebrow="Healing Loop"
          value={formatPercentage(healing.healing_rate)}
          label="Agent healing rate"
          detail={`${healing.healed_sequences} of ${healing.blocked_sequences} blocked sequences came back green on retry.`}
        />
      </section>

      <section className="content-grid">
        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Risk Avoided</p>
              <h2>What the gate stopped recently</h2>
            </div>
            <p className="subtle-copy">
              Feed of blocked actions with blast radius and the external signals
              that gave stakeholders a reason to care.
            </p>
          </div>
          <div className="risk-feed">
            {feed.length > 0 ? (
              feed.map((item) => <RiskFeedCard key={item.decision_id} item={item} />)
            ) : (
              <div className="panel inset-panel">
                <p className="eyebrow">No blocked actions yet</p>
                <h3>The feed fills once action decisions start landing in the audit ledger.</h3>
                <p className="subtle-copy">
                  Trigger a few `/v1/decide/action` calls or run the GitHub Action to populate it.
                </p>
              </div>
            )}
          </div>
        </section>

        <section className="panel healing-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Agent Healing Rate</p>
              <h2>Did the agent actually repair the blocked change?</h2>
            </div>
            <p className="subtle-copy">{healing.methodology}</p>
          </div>

          <div className="healing-hero">
            <div>
              <p className="mega-stat">{formatPercentage(healing.healing_rate)}</p>
              <p className="subtle-copy">
                {healing.healed_sequences} healed sequences, {healing.unresolved_sequences} still open.
              </p>
            </div>
            <div className="progress-rail" aria-hidden="true">
              <div
                className="progress-fill"
                style={{ width: `${Math.max(healing.healing_rate * 100, 6)}%` }}
              />
            </div>
          </div>

          <div className="healing-metrics">
            <div className="mini-stat">
              <strong>{healing.average_retries_to_heal.toFixed(2)}</strong>
              <span>blocked tries before heal</span>
            </div>
            <div className="mini-stat">
              <strong>{formatMinutes(healing.median_time_to_heal_minutes)}</strong>
              <span>median time to heal</span>
            </div>
            <div className="mini-stat">
              <strong>{healing.blocked_sequences}</strong>
              <span>blocked sequences measured</span>
            </div>
          </div>

          <div className="recent-heals">
            <p className="section-label">Recent healed retries</p>
            {healing.recent_heals.length > 0 ? (
              healing.recent_heals.map((item) => (
                <HealingCaseRow key={item.healed_decision_id} item={item} />
              ))
            ) : (
              <p className="subtle-copy">No healed retries have been observed in the current audit window.</p>
            )}
          </div>
        </section>
      </section>
    </main>
  );
}

export default async function Page() {
  const { data, apiBaseUrl, error } = await getDashboardOverview();
  if (data === null) {
    return <EmptyState apiBaseUrl={apiBaseUrl} error={error} />;
  }
  return <StakeholderView overview={data} />;
}
