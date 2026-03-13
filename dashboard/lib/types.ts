export type DashboardSignal = {
  source: string;
  source_kind: "jira" | "slack" | "pagerduty" | "incident" | "github" | "other";
  label: string;
  relation: "twin_case" | "evidence_span";
  title: string;
  summary: string | null;
  external_url: string | null;
  timestamp: string | null;
};

export type BlastRadius = {
  files: number;
  tests: number;
  docs: number;
  runbooks: number;
  max_dependency_depth: number;
  impacted_paths: string[];
};

export type DashboardRiskAvoidedItem = {
  decision_id: string;
  created_at: string;
  repo_path: string;
  action_summary: string;
  changed_paths: string[];
  status: "still_blocked" | "healed_on_retry";
  healed_decision_id: string | null;
  healed_at: string | null;
  blast_radius: BlastRadius;
  missing_evidence: string[];
  strongest_evidence_sources: string[];
  triggering_signals: DashboardSignal[];
  policy_labels: string[];
};

export type DashboardHeadlineMetrics = {
  blocked_actions: number;
  blocked_sequences: number;
  incident_linked_blocks: number;
  protected_files: number;
  protected_tests: number;
  protected_docs: number;
  protected_runbooks: number;
};

export type DashboardHealingCase = {
  blocked_decision_id: string;
  healed_decision_id: string;
  blocked_at: string;
  healed_at: string;
  repo_path: string;
  action_summary: string;
  changed_paths: string[];
  missing_before: string[];
  missing_after: string[];
  retries_before_heal: number;
  time_to_heal_minutes: number | null;
};

export type DashboardHealingSummary = {
  blocked_sequences: number;
  healed_sequences: number;
  unresolved_sequences: number;
  healing_rate: number;
  average_retries_to_heal: number;
  median_time_to_heal_minutes: number | null;
  methodology: string;
  recent_heals: DashboardHealingCase[];
};

export type DashboardOverviewResponse = {
  generated_at: string;
  scanned_decisions: number;
  scanned_action_decisions: number;
  headline_metrics: DashboardHeadlineMetrics;
  agent_healing: DashboardHealingSummary;
  risk_avoided_feed: DashboardRiskAvoidedItem[];
};
