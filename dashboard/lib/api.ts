import type { DashboardOverviewResponse } from "./types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

function buildOverviewUrl(): string {
  const baseUrl = process.env.EVIDENCE_GATE_API_BASE_URL ?? DEFAULT_API_BASE_URL;
  const url = new URL("/v1/dashboard/overview", baseUrl);
  url.searchParams.set("limit", "250");
  url.searchParams.set("feed_limit", "8");
  return url.toString();
}

export async function getDashboardOverview(): Promise<{
  data: DashboardOverviewResponse | null;
  apiBaseUrl: string;
  error: string | null;
}> {
  const apiBaseUrl = process.env.EVIDENCE_GATE_API_BASE_URL ?? DEFAULT_API_BASE_URL;
  try {
    const response = await fetch(buildOverviewUrl(), {
      cache: "no-store",
    });
    if (!response.ok) {
      return {
        data: null,
        apiBaseUrl,
        error: `FastAPI returned ${response.status} for /v1/dashboard/overview.`,
      };
    }
    const data = (await response.json()) as DashboardOverviewResponse;
    return { data, apiBaseUrl, error: null };
  } catch (error) {
    return {
      data: null,
      apiBaseUrl,
      error:
        error instanceof Error
          ? error.message
          : "Unknown error while loading the dashboard overview.",
    };
  }
}
