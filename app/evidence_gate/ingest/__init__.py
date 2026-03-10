"""Ingestion abstractions for repository and external evidence sources."""

from evidence_gate.ingest.base import BaseIngestor
from evidence_gate.ingest.confluence_export import ConfluenceExportIngestor
from evidence_gate.ingest.jira_export import JiraExportIngestor
from evidence_gate.ingest.local_repo import LocalRepoIngestor
from evidence_gate.ingest.markdown_incident import MarkdownIncidentIngestor
from evidence_gate.ingest.pagerduty_incident import PagerDutyIncidentIngestor
from evidence_gate.ingest.slack_incident import SlackIncidentIngestor

__all__ = [
    "BaseIngestor",
    "ConfluenceExportIngestor",
    "JiraExportIngestor",
    "LocalRepoIngestor",
    "MarkdownIncidentIngestor",
    "PagerDutyIncidentIngestor",
    "SlackIncidentIngestor",
]
