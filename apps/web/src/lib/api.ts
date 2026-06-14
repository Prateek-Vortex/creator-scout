const API_TOKEN = process.env.NEXT_PUBLIC_CREATOR_SCOUT_API_TOKEN;
const API_BASE_URL =
  process.env.NEXT_PUBLIC_CREATOR_SCOUT_API_URL ?? "http://127.0.0.1:8765";

function getRequestUrl(path: string): string {
  // Server-side: always use the configured backend URL.
  if (typeof window === "undefined") {
    return `${API_BASE_URL}${path}`;
  }
  // Browser-side: if NEXT_PUBLIC_CREATOR_SCOUT_API_URL is set, talk to the
  // FastAPI directly. The Next dev-server rewrite has a short proxy timeout
  // that aborts long-running endpoints like POST /v1/campaigns (which runs
  // brand-scan + AI brief + outreach drafts inline, ~15–20 s) and surfaces it
  // as a bare "500 Internal Server Error". Going direct keeps the original
  // FastAPI status + JSON envelope intact. CORS is open on the API.
  if (process.env.NEXT_PUBLIC_CREATOR_SCOUT_API_URL) {
    return `${process.env.NEXT_PUBLIC_CREATOR_SCOUT_API_URL}${path}`;
  }
  if (path === "/health") {
    return "/api/health";
  }
  if (path.startsWith("/v1/")) {
    return `/api${path}`;
  }
  return path;
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
  if (!headers.has("Content-Type") && (options.method === "POST" || options.method === "PUT" || options.method === "PATCH")) {
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
  job_summary: JobSummary;
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
  suppressed_at?: string | null;
  suppression_reason?: string | null;
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
  notes: string | null;
  outreach_draft: { subject?: string; body?: string } | null;
  outreach_messages?: OutreachMessage[];
  created_at: string;
  updated_at: string;
  creator: CreatorProfile | null;
}

export interface OutreachMessage {
  id: string;
  campaign_creator_id: string;
  recipient_contact_id: string | null;
  recipient_email: string | null;
  channel: string;
  subject: string | null;
  body: string;
  status: string;
  provider: string | null;
  provider_message_id: string | null;
  provider_response: Record<string, unknown>;
  error: string | null;
  unsubscribe_group_id: string | null;
  sent_at: string | null;
  delivered_at: string | null;
  opened_at: string | null;
  replied_at: string | null;
  bounced_at: string | null;
  spam_reported_at: string | null;
  unsubscribed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface OutreachConfig {
  enabled: boolean;
  connected: boolean;
  from_email: string | null;
  from_name: string | null;
  provider: "gmail";
}

export interface GmailIntegrationStatus {
  connected: boolean;
  email: string | null;
  from_email: string | null;
  from_name: string | null;
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
  status: "queued" | "running" | "passed" | "failed";
  input: unknown;
  output: unknown;
  error: string | null;
  attempt_count: number;
  max_attempts: number;
  next_run_at: string | null;
  locked_at: string | null;
  locked_by: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface JobSummary {
  queued: number;
  running: number;
  passed: number;
  failed: number;
  pending: number;
  total: number;
}

export interface CampaignExport {
  id: string;
  org_id: string | null;
  campaign_id: string;
  storage_key: string;
  file_url: string;
  row_count: number;
  created_at: string;
  updated_at: string;
}

export const api = {
  async checkHealth(): Promise<{ ok: boolean }> {
    return apiRequest("/health");
  },

  async getUsage(): Promise<{ data: CreditUsage }> {
    return apiRequest("/v1/usage");
  },

  async listCampaigns(limit: number = 20): Promise<{ data: Campaign[] }> {
    return apiRequest(`/v1/campaigns?limit=${limit}`);
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
    discovery_mode?: "safe_fanout" | "single_provider";
    query_limit?: number;
    per_query_limit?: number;
    max_providers_per_query?: number;
    max_enrichment_urls_per_query?: number;
  }): Promise<{ data: { campaign: Campaign; discovery_job_ids: string[] } }> {
    return apiRequest("/v1/campaigns", {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  async buildShortlist(
    campaignId: string,
    params: { limit?: number; query_limit?: number } = {}
  ): Promise<{ data: { campaign_id: string; shortlist: CampaignCreator[]; candidate_count: number; job_summary: JobSummary } }> {
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

  async updateCampaignCreator(
    campaignId: string,
    creatorId: string,
    params: { status?: string; recommended_pitch?: string; notes?: string | null }
  ): Promise<{ data: CampaignCreator }> {
    return apiRequest(`/v1/campaigns/${campaignId}/creators/${creatorId}`, {
      method: "PATCH",
      body: JSON.stringify(params),
    });
  },

  async exportCampaign(campaignId: string): Promise<{ data: CampaignExport }> {
    return apiRequest(`/v1/campaigns/${campaignId}/export`, {
      method: "POST",
      body: JSON.stringify({}),
    });
  },

  async getOutreachConfig(): Promise<{ data: OutreachConfig }> {
    return apiRequest("/v1/outreach/config");
  },

  async sendOutreach(
    campaignId: string,
    creatorId: string,
    params: { subject?: string; body?: string }
  ): Promise<{ data: { outreach_message: OutreachMessage; campaign_creator: CampaignCreator } }> {
    return apiRequest(`/v1/campaigns/${campaignId}/creators/${creatorId}/outreach/send`, {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  async refineOutreachDraft(
    campaignId: string,
    creatorId: string
  ): Promise<{ data: CampaignCreator }> {
    return apiRequest(`/v1/campaigns/${campaignId}/creators/${creatorId}/outreach/draft`, {
      method: "POST",
      body: JSON.stringify({}),
    });
  },

  async createBillingCheckout(params: {
    plan: "starter" | "growth" | "agency";
    name?: string;
    email?: string;
    return_url?: string;
  }): Promise<{ checkout_url: string; session_id: string }> {
    return apiRequest("/v1/billing/checkout", {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  async startGraphRun(params: {
    campaign_id: string;
    brand_url: string;
    goal?: string;
    geo?: string;
    org_id?: string;
  }): Promise<{ thread_id: string; status: string; next_node: string | null }> {
    return apiRequest("/v1/graph/run", {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  async resumeGraphRun(
    threadId: string,
    params: { approved: boolean; feedback?: string }
  ): Promise<{ thread_id: string; status: string; run_status: Record<string, unknown> | null }> {
    return apiRequest(`/v1/graph/run/${threadId}/resume`, {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  async getGraphStatus(threadId: string): Promise<{
    thread_id: string;
    paused: boolean;
    current_node: string;
    next_node: string | null;
    shortlist: unknown[];
    outreach_drafts: unknown[];
    brand_brief: Record<string, unknown> | null;
    error: string | null;
  }> {
    return apiRequest(`/v1/graph/run/${threadId}/status`);
  },

  async getDeveloperKeys(userId: string): Promise<{ data: { keys: DeveloperKey[]; credits: CreditStatus } }> {
    return apiRequest(`/v1/settings/developer-keys?user_id=${userId}`);
  },

  async createDeveloperKey(userId: string, name: string): Promise<{ data: { id: string; plain_key: string } }> {
    return apiRequest("/v1/settings/developer-keys", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, name }),
    });
  },

  async revokeDeveloperKey(userId: string, keyId: string): Promise<{ success: boolean }> {
    return apiRequest(`/v1/settings/developer-keys/${keyId}?user_id=${userId}`, {
      method: "DELETE",
    });
  },

  async updateProfile(userId: string, name: string, email: string): Promise<{ success: boolean }> {
    return apiRequest("/v1/settings/profile", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, name, email }),
    });
  },

  async getGmailStatus(): Promise<{ data: GmailIntegrationStatus }> {
    return apiRequest("/v1/integrations/gmail");
  },

  async getGmailAuthUrl(): Promise<{ data: { url: string; state: string } }> {
    return apiRequest("/v1/integrations/gmail/auth-url");
  },

  async disconnectGmail(): Promise<{ success: boolean }> {
    return apiRequest("/v1/integrations/gmail", { method: "DELETE" });
  },
};

export interface DeveloperKey {
  id: string;
  name: string;
  scopes: string[];
  rate_limit_per_minute: number;
  monthly_credit_limit: number;
  created_at: string;
}

export interface CreditStatus {
  used: number;
  limit: number;
  remaining: number;
}
