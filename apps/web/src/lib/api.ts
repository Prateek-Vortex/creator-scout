const API_TOKEN = process.env.NEXT_PUBLIC_CREATOR_SCOUT_API_TOKEN;
const API_BASE_URL =
  process.env.NEXT_PUBLIC_CREATOR_SCOUT_API_URL ?? "http://127.0.0.1:8765";

function getRequestUrl(path: string): string {
  if (typeof window === "undefined") {
    return `${API_BASE_URL}${path}`;
  }

  return `/api${path}`;
}

async function apiRequest<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = getRequestUrl(path);
  const headers = new Headers(options.headers);
  
  if (!headers.has("Authorization") && path !== "/health") {
    if (!API_TOKEN) {
      throw new Error(
        "Missing NEXT_PUBLIC_CREATOR_SCOUT_API_TOKEN. Seed the Python API and add the demo key to apps/web/.env.local."
      );
    }
    headers.set("Authorization", `Bearer ${API_TOKEN}`);
  }
  if (!headers.has("Content-Type") && (options.method === "POST" || options.method === "PUT")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMessage = `API error: ${response.status} ${response.statusText}`;
    try {
      const errorJson = await response.json();
      if (errorJson?.error?.message) {
        errorMessage = errorJson.error.message;
      }
    } catch {}
    throw new Error(errorMessage);
  }

  return response.json();
}

export interface CampaignBrief {
  brand_name: string;
  category: string;
  products: string[];
  target_audience: string;
  price_positioning: string;
  tone: string[];
  value_props: string[];
  avoid_creator_types: string[];
  best_creator_niches: string[];
  campaign_angles: string[];
  search_queries: string[];
  confidence: number;
  evidence: Array<{
    field: string;
    source_url: string;
    page_type: string;
    title: string;
  }>;
}

export interface Campaign {
  id: string;
  org_id: string | null;
  brand_id: string;
  brand_url: string;
  goal: string;
  geo: string;
  platforms: string[];
  status: string;
  brief: CampaignBrief;
  search_queries: string[];
  created_at: string;
  updated_at: string;
  jobs: Array<{
    id: string;
    campaign_id: string;
    job_id: string;
    query: string;
    provider: string;
    created_at: string;
    status: string;
    error: string | null;
  }>;
}

export interface CreatorAccount {
  platform: string;
  handle: string;
  profile_url: string;
  follower_count: number | null;
  subscriber_count: number | null;
  avg_views: number | null;
  engagement_rate: number | null;
  bio: string;
  last_verified_at: string;
  raw: Record<string, unknown>;
}

export interface CreatorContact {
  contact_type: string;
  value: string;
  source_url: string;
  permission_basis: string;
  confidence: number;
  do_not_contact: boolean;
  last_verified_at: string;
}

export interface SourceEvidence {
  source_url: string;
  source_type: string;
  fields_found: Record<string, unknown>;
  confidence: number;
  fetched_at: string;
}

export interface CreatorProfile {
  creator_id: string;
  display_name: string;
  primary_niche: string;
  location: string | null;
  languages: string[];
  summary: string;
  topics: string[];
  accounts: CreatorAccount[];
  contacts: CreatorContact[];
  sources: SourceEvidence[];
  updated_at: string;
  raw: Record<string, unknown>;
}

export interface CampaignCreator {
  id: string;
  campaign_id: string;
  creator_id: string;
  status: string;
  bucket: "contact_first" | "review" | "backup" | "avoid";
  fit_score: number;
  evidence: Array<{
    source_url?: string;
    source_type?: string;
    confidence?: number;
    fields_found?: Record<string, unknown>;
    fit_score?: number;
    match_reasons?: string[];
  }>;
  risks: string[];
  unknowns: string[];
  recommended_pitch: string;
  outreach_draft: { subject?: string; body?: string } | null;
  created_at: string;
  updated_at: string;
  creator: CreatorProfile | null;
}

export interface CreditUsage {
  org_id: string;
  api_key_id: string;
  credits_used: number;
  monthly_credit_limit: number;
  credits_remaining: number;
}

export interface JobStatus {
  id: string;
  org_id: string | null;
  requested_by_api_key_id: string | null;
  job_type: string;
  provider: string | null;
  status: "queued" | "running" | "finished" | "failed";
  input: unknown;
  output: unknown;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export const api = {
  async checkHealth(): Promise<{ ok: boolean }> {
    return apiRequest("/health");
  },

  async getUsage(): Promise<{ data: CreditUsage }> {
    return apiRequest("/v1/usage");
  },

  async getCampaign(campaignId: string): Promise<{ data: Campaign }> {
    return apiRequest(`/v1/campaigns/${campaignId}`);
  },

  async createCampaign(params: {
    brand_url: string;
    geo?: string;
    goal?: string;
    platforms?: string[];
    provider?: string;
    query_limit?: number;
    per_query_limit?: number;
  }): Promise<{ data: { campaign: Campaign; discovery_job_ids: string[] } }> {
    return apiRequest("/v1/campaigns", {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  async buildShortlist(
    campaignId: string,
    params: { limit?: number; query_limit?: number } = {}
  ): Promise<{ data: { campaign_id: string; shortlist: CampaignCreator[]; candidate_count: number } }> {
    return apiRequest(`/v1/campaigns/${campaignId}/shortlist`, {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  async getCampaignCreators(
    campaignId: string,
    limit: number = 50
  ): Promise<{ data: CampaignCreator[] }> {
    return apiRequest(`/v1/campaigns/${campaignId}/creators?limit=${limit}`);
  },

  async getCreator(creatorId: string): Promise<{ data: CreatorProfile }> {
    return apiRequest(`/v1/creators/${creatorId}`);
  },

  async getJobStatus(jobId: string): Promise<{ data: JobStatus }> {
    return apiRequest(`/v1/jobs/${jobId}`);
  },

  async retryJob(jobId: string): Promise<{ data: unknown }> {
    return apiRequest(`/v1/jobs/${jobId}/retry`, {
      method: "POST",
    });
  },
};
