"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { motion, useScroll, useTransform, useSpring } from "framer-motion";
import { api } from "@/lib/api";
import type { Campaign, CampaignCreator, CreatorContact, OutreachConfig, OutreachMessage } from "@/lib/api";
import { getInsForgeClient, hasInsForgeConfig } from "@/lib/insforge";

// ─── Constants ────────────────────────────────────────────────────────────────
const PLATFORM_OPTIONS = ["youtube", "instagram", "tiktok"];
const CRM_COLUMNS = [
  { id: "shortlisted",     label: "Shortlisted",      color: "text-[#7a7a7a]" },
  { id: "contacted",       label: "Contacted",        color: "text-ink" },
  { id: "replied",         label: "Replied",          color: "text-accent-teal" },
  { id: "negotiating",     label: "Negotiating",      color: "text-ink" },
  { id: "accepted",        label: "Accepted",         color: "text-success" },
  { id: "content_pending", label: "Content Pending",  color: "text-warning" },
  { id: "live",            label: "Live",             color: "text-success" },
  { id: "done",            label: "Done",             color: "text-[#7a7a7a]" },
];

const AVATAR_COLORS = [
  "bg-[#fde8e4] text-[#c4402d] border-[#f5c4ba]",
  "bg-[#e0f5f3] text-[#1e7a72] border-[#b5e5e0]",
  "bg-[#ece4fb] text-[#6b4ec0] border-[#cebdf5]",
  "bg-[#fdf0db] text-[#b07920] border-[#f0d9a6]",
];

const STICKER_ROTATIONS = [-2, 1.5, -1, 2.5, -1.5, 2, -0.5, 1];
const FINDER_LOGS = [
  "Checking campaign job status...",
  "Reading cached creator index...",
  "Computing alignment scores...",
  "Drafting templates...",
  "Complete",
];
const CRAWLER_LOGS = [
  "Resolving domain...",
  "Crawling pages...",
  "Extracting brand DNA...",
  "Building campaign brief...",
  "Done!",
];

// ─── Types ────────────────────────────────────────────────────────────────────
type ApiHealth = "checking" | "online" | "offline";
type ActiveTab = "brief" | "strategy" | "shortlist" | "outreach" | "crm" | "export" | "billing";
type AuthUser = {
  email?: string | null;
  profile?: {
    name?: string | null;
  } | null;
} | null;

function jobSummaryFor(campaign: Campaign) {
  const fallback = { queued: 0, running: 0, passed: 0, failed: 0, pending: 0, total: 0 };
  const summary = campaign.job_summary ?? fallback;
  return {
    ...fallback,
    ...summary,
    pending: summary.pending ?? ((summary.queued ?? 0) + (summary.running ?? 0)),
    total: summary.total ?? campaign.jobs.length,
  };
}

function latestOutreachMessage(item: CampaignCreator | null): OutreachMessage | null {
  const messages = item?.outreach_messages ?? [];
  return messages.length ? messages[0] : null;
}

function sendableEmailContact(item: CampaignCreator | null): CreatorContact | null {
  return (item?.creator?.contacts ?? []).find((contact) => {
    const permission = contact.permission_basis?.toLowerCase();
    return (
      contact.contact_type?.toLowerCase() === "email" &&
      contact.value.includes("@") &&
      permission === "public_business_contact" &&
      !contact.do_not_contact &&
      !contact.suppressed_at &&
      Boolean(contact.source_url)
    );
  }) ?? null;
}

function outreachBlockReason(
  item: CampaignCreator | null,
  config: OutreachConfig | null,
  isSending: boolean
): string | null {
  if (!item) return "Select a creator";
  if (isSending) return "Sending...";
  if (!config) return "Checking AutoSend";
  if (!config.has_api_key || !config.has_from_email) return "AutoSend config missing";
  if (!config.has_unsubscribe_group) return "Unsubscribe group missing";
  const emailContacts = item.creator?.contacts.filter((contact) => contact.contact_type?.toLowerCase() === "email") ?? [];
  if (!sendableEmailContact(item)) {
    if (emailContacts.some((contact) => contact.do_not_contact || contact.suppressed_at)) return "Contact suppressed";
    return "No valid public business email";
  }
  const latest = latestOutreachMessage(item);
  if (latest && ["sent", "delivered", "opened"].includes(latest.status)) return `Already ${latest.status}`;
  return null;
}

function defaultOutreachText(campaign: Campaign, item: CampaignCreator): string {
  if (item.outreach_draft && typeof item.outreach_draft === "object") {
    return `Subject: ${item.outreach_draft.subject || ""}\n\n${item.outreach_draft.body || ""}`.trim();
  }
  return `Subject: Partnership - ${campaign.brief.brand_name}\n\nHi ${item.creator?.display_name || "there"},\n\nI discovered your content and think you'd be a great fit for ${campaign.brief.brand_name}'s upcoming ${campaign.goal} campaign.\n\n${item.recommended_pitch}\n\nOpen to a chat?\n\nBest,\n${campaign.brief.brand_name}`;
}

function parseOutreachComposer(text: string, fallbackSubject: string): { subject: string; body: string } {
  const normalized = text.replace(/\r\n/g, "\n").trim();
  const lines = normalized.split("\n");
  const firstLine = lines[0] ?? "";
  const subjectMatch = firstLine.match(/^Subject:\s*(.*)$/i);
  if (subjectMatch) {
    return {
      subject: subjectMatch[1].trim() || fallbackSubject,
      body: lines.slice(1).join("\n").trim(),
    };
  }
  return {
    subject: fallbackSubject,
    body: normalized,
  };
}

// ─── Tiny SVG Icon Kit ────────────────────────────────────────────────────────
const Icon = {
  brief: () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
    </svg>
  ),
  strategy: () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
    </svg>
  ),
  shortlist: () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z" />
    </svg>
  ),
  outreach: () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75" />
    </svg>
  ),
  crm: () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 0 1 6 3.75h2.25A2.25 2.25 0 0 1 10.5 6v2.25a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 8.25V6ZM3.75 15.75A2.25 2.25 0 0 1 6 13.5h2.25a2.25 2.25 0 0 1 2.25 2.25V18a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 18v-2.25ZM13.5 6a2.25 2.25 0 0 1 2.25-2.25H18A2.25 2.25 0 0 1 20.25 6v2.25A2.25 2.25 0 0 1 18 10.5h-2.25a2.25 2.25 0 0 1-2.25-2.25V6ZM13.5 15.75a2.25 2.25 0 0 1 2.25-2.25H18a2.25 2.25 0 0 1 2.25 2.25V18A2.25 2.25 0 0 1 18 20.25h-2.25A2.25 2.25 0 0 1 13.5 18v-2.25Z" />
    </svg>
  ),
  export: () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
    </svg>
  ),
  check: () => (
    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
    </svg>
  ),
  copy: () => (
    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0 0 13.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 0 1-.75.75H9a.75.75 0 0 1-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 0 1-2.25 2.25H6.75A2.25 2.25 0 0 1 4.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 0 1 1.927-.184" />
    </svg>
  ),
  external: () => (
    <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 0 0 3 8.25v10.5A2.25 2.25 0 0 0 5.25 21h10.5A2.25 2.25 0 0 0 18 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
    </svg>
  ),
  chevronDown: () => (
    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
    </svg>
  ),
  sparkle: () => (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
      <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" />
    </svg>
  ),
};

// ─── Small helper components ───────────────────────────────────────────────────
function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-2 text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a]">
      {label}
      {children}
    </label>
  );
}

function PlatformPill({ platform }: { platform: string }) {
  const badgeMap: Record<string, string> = {
    youtube:   "badge-coral",
    instagram: "badge-lavender",
    tiktok:    "badge-teal",
  };
  const cls = badgeMap[platform.toLowerCase()] ?? "badge-amber";
  return (
    <span className={`badge-sticker ${cls} text-[9px]`}>
      {platform}
    </span>
  );
}

function MetricCard({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className={`rounded-xl border p-5 ${accent ? "border-accent/20 bg-accent/5" : "border-[#e8e4df] bg-white"}`}>
      <p className="text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a]">{label}</p>
      <p className={`mt-2 text-base font-medium truncate ${accent ? "text-accent" : "text-ink"}`}>{value || "—"}</p>
    </div>
  );
}

function ChipList({ label, values, variant = "default" }: { label: string; values: string[]; variant?: "success" | "danger" | "default" }) {
  if (!values.length) return null;
  const chipCls = variant === "success" ? "border-success/20 bg-success/5 text-success"
    : variant === "danger" ? "border-danger/20 bg-danger/5 text-danger"
    : "border-[#e8e4df] bg-[#f8f6f2] text-[#5a5a5a]";
  return (
    <div className="rounded-xl border border-[#e8e4df] bg-white p-5">
      <p className="mb-3.5 text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a]">{label}</p>
      <div className="flex flex-wrap gap-2">
        {values.map((v) => (
          <span className={`rounded-md border px-3 py-1.5 text-[11px] font-medium ${chipCls}`} key={v}>{v}</span>
        ))}
      </div>
    </div>
  );
}

function Avatar({ name, size = "md" }: { name: string; size?: "sm" | "md" | "lg" }) {
  const initials = name.split(" ").slice(0, 2).map((w) => w[0]).join("").toUpperCase() || name.slice(0, 2).toUpperCase();
  const colorCls = AVATAR_COLORS[name.length % AVATAR_COLORS.length];
  const sizeClass = size === "sm" ? "w-8 h-8 text-[10px]" : size === "lg" ? "w-14 h-14 text-sm" : "w-10 h-10 text-xs";
  return (
    <div className={`${sizeClass} rounded-full ${colorCls} border flex items-center justify-center font-semibold shrink-0`}>
      {initials}
    </div>
  );
}

// ─── Navbar ───────────────────────────────────────────────────────────────────
function Navbar({
  onGetStarted,
  user,
  onSignOut,
}: {
  onGetStarted: () => void;
  user: AuthUser;
  onSignOut: () => void;
}) {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handler);
    return () => window.removeEventListener("scroll", handler);
  }, []);

  return (
    <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${scrolled ? "bg-[#faf9f6]/90 backdrop-blur-md border-b border-[#e8e4df] shadow-sm" : "bg-transparent border-b border-transparent"}`}>
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-[#1a1a1a] flex items-center justify-center text-[#faf9f6] font-bold text-[10px] shadow-sm">
            CS
          </div>
          <span className="text-sm font-semibold text-ink tracking-tight">Creator Scout</span>
        </div>

        {/* Nav links */}
        <div className="hidden md:flex items-center gap-1">
          {["Features", "Pricing", "Docs", "Blog"].map((item) => (
            <button key={item} className="px-3.5 py-2 rounded-md text-xs font-medium text-[#7a7a7a] hover:text-ink hover:bg-[#f3f0eb] transition-all cursor-pointer">
              {item}
            </button>
          ))}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-4">
          {user ? (
            <>
              <span className="text-xs text-[#7a7a7a]">
                Hi, <span className="font-semibold text-ink">{user.profile?.name || user.email}</span>
              </span>
              <Link
                href="/settings"
                className="px-3 py-1.5 rounded-lg border border-[#e8e4df] text-xs font-semibold text-ink bg-white hover:bg-[#f3f0eb] transition cursor-pointer"
              >
                Settings
              </Link>
              <button
                onClick={onSignOut}
                className="px-3 py-1.5 rounded-lg border border-[#e8e4df] text-xs font-semibold text-ink bg-[#f5f2ed] hover:bg-[#e8e4df] transition cursor-pointer"
              >
                Log out
              </button>
            </>
          ) : (
            <>
              <Link href="/sign-in" className="px-4 py-2 rounded-md text-xs font-medium text-[#7a7a7a] hover:text-ink transition-colors">
                Log in
              </Link>
              <button
                onClick={onGetStarted}
                className="glow-btn px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer"
              >
                Start free
              </button>
            </>
          )}
        </div>

      </div>
    </nav>
  );
}

// ─── Landing Page ─────────────────────────────────────────────────────────────
function LandingPage({
  onLaunch,
  apiHealth,
}: {
  onLaunch: (params: { brand_url: string; goal: string; geo: string; platforms: string[] }) => void;
  apiHealth: ApiHealth;
}) {
  const [brandUrl, setBrandUrl] = useState("");
  const formRef = useRef<HTMLDivElement>(null);
  const heroRef = useRef<HTMLDivElement>(null);

  const [goal, setGoal] = useState("ugc");
  const [geoCountry, setGeoCountry] = useState("India");
  const [geoCustom, setGeoCustom] = useState("");
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(["youtube", "instagram", "tiktok"]);

  // Scroll-linked hero effect
  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ["start start", "end start"],
  });
  const heroOpacity = useTransform(scrollYProgress, [0, 0.8], [1, 0]);
  const heroScale = useTransform(scrollYProgress, [0, 0.8], [1, 0.95]);
  const heroY = useTransform(scrollYProgress, [0, 1], [0, -60]);
  const smoothOpacity = useSpring(heroOpacity, { stiffness: 80, damping: 20 });
  const smoothScale = useSpring(heroScale, { stiffness: 80, damping: 20 });

  function scrollToForm() {
    formRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function handleHeroSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    onLaunch({ brand_url: brandUrl, goal: "ugc", geo: "India", platforms: ["youtube", "instagram", "tiktok"] });
  }

  function handleDetailedSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const finalGeo = geoCountry === "Custom"
      ? geoCustom.trim()
      : geoCustom.trim()
        ? `${geoCountry} (${geoCustom.trim()})`
        : geoCountry;
    
    onLaunch({
      brand_url: brandUrl,
      goal,
      geo: finalGeo || "India",
      platforms: selectedPlatforms.length ? selectedPlatforms : ["youtube"],
    });
  }

  function fillDemo() {
    setBrandUrl("https://glowlabskincare.com");
  }

  const STATS = [
    { value: "12,400+", label: "Creators indexed", badge: "badge-coral" },
    { value: "500+",    label: "Campaigns launched", badge: "badge-teal" },
    { value: "3.2×",   label: "Avg. ROI uplift", badge: "badge-lavender" },
    { value: "98%",    label: "Deliverability", badge: "badge-amber" },
  ];

  const FEATURES = [
    {
      icon: "◇",
      title: "Brand Intelligence",
      desc: "Crawls your website and extracts positioning, tone, audience, and ideal creator profile automatically.",
      tags: ["Claude 4.5", "Extraction"],
      badge: "badge-coral",
    },
    {
      icon: "◒",
      title: "Semantic Matching",
      desc: "Vector embeddings rank creators by genuine audience overlap — not just keyword similarity.",
      tags: ["pgvector", "PostgreSQL"],
      badge: "badge-teal",
    },
    {
      icon: "✉",
      title: "Compliant Outreach",
      desc: "Generates personalized pitches grounded in each creator's actual content and public contacts.",
      tags: ["GDPR", "Auto-draft"],
      badge: "badge-lavender",
    },
    {
      icon: "≡",
      title: "Full Campaign CRM",
      desc: "Track every negotiation from shortlist to live content and export your pipeline as CSV.",
      tags: ["Kanban", "CSV"],
      badge: "badge-amber",
    },
  ];

  return (
    <div className="min-h-screen bg-[#faf9f6] text-ink">
      {/* ── Hero ── */}
      <section ref={heroRef} className="relative pt-28 pb-20 px-6 grid-overlay overflow-hidden" style={{ minHeight: "90vh" }}>
        <motion.div
          className="relative z-10 max-w-4xl mx-auto text-center"
          style={{ opacity: smoothOpacity, scale: smoothScale, y: heroY }}
        >
          {/* Floating accent stickers */}
          <motion.div
            className="absolute -top-4 -left-8 md:left-12 badge-sticker badge-coral text-[10px] select-none pointer-events-none"
            animate={{ y: [0, -8, 0], rotate: [-3, -1, -3] }}
            transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
          >
            ✦ AI-Powered
          </motion.div>
          <motion.div
            className="absolute top-8 -right-4 md:right-8 badge-sticker badge-teal text-[10px] select-none pointer-events-none"
            animate={{ y: [0, -6, 0], rotate: [2, 4, 2] }}
            transition={{ duration: 5, repeat: Infinity, ease: "easeInOut", delay: 1 }}
          >
            GDPR Compliant
          </motion.div>
          <motion.div
            className="absolute bottom-16 -left-4 md:left-4 badge-sticker badge-lavender text-[10px] select-none pointer-events-none hidden md:inline-flex"
            animate={{ y: [0, -10, 0], rotate: [-2, 1, -2] }}
            transition={{ duration: 6, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
          >
            Vector Search
          </motion.div>

          <motion.div
            className="inline-flex items-center gap-2 rounded-full border border-[#e8e4df] bg-white px-4 py-1.5 text-[10px] font-semibold text-[#7a7a7a] mb-8 shadow-sm"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.5 }}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
            SOC 2 Type II in Progress
          </motion.div>

          <motion.h1
            className="text-4xl sm:text-6xl font-semibold tracking-tight text-ink leading-tight mb-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.6 }}
          >
            Find creators that
            <br />
            <span className="handwriting text-5xl sm:text-7xl text-accent" style={{ fontFamily: "var(--font-caveat)" }}>
              actually fit
            </span>
            {" "}your brand
          </motion.h1>

          <motion.p
            className="text-sm sm:text-base text-[#7a7a7a] font-normal leading-relaxed max-w-2xl mx-auto mb-10"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35, duration: 0.6 }}
          >
            Paste your website URL. Creator Scout crawls it, extracts your brand DNA,
            semantically matches compliant creators, and drafts personalized pitches — all inside one workspace.
          </motion.p>

          {/* ── Inline URL form ── */}
          <motion.form
            className="max-w-xl mx-auto"
            onSubmit={handleHeroSubmit}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.6 }}
          >
            <div className="notebook-page p-2 flex items-center gap-2">
              <input
                id="hero-url-input"
                className="flex-1 px-4 py-3.5 text-sm font-mono bg-transparent border-none outline-none text-ink placeholder:text-[#c4bfb7]"
                onChange={(e) => setBrandUrl(e.target.value)}
                placeholder="https://yourbrand.com"
                required
                type="url"
                value={brandUrl}
              />
              <button
                className="glow-btn-accent px-6 py-3.5 text-sm font-semibold cursor-pointer shrink-0 rounded-xl"
                type="submit"
              >
                Analyze →
              </button>
            </div>
          </motion.form>

          <motion.div
            className="mt-4 flex items-center justify-center gap-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.7, duration: 0.5 }}
          >
            <button
              onClick={() => { fillDemo(); scrollToForm(); }}
              className="text-xs font-medium text-[#7a7a7a] hover:text-ink transition-colors cursor-pointer underline decoration-dotted underline-offset-4"
            >
              Try with demo brand
            </button>
            <span className="text-[#d4cfc8]">·</span>
            <span className="text-[10px] text-[#b5afa6]">No credit card required</span>
          </motion.div>
        </motion.div>
      </section>

      {/* ── Stats bar (floating sticker badges) ── */}
      <section className="relative -mt-12 mb-8 px-6 z-20">
        <div className="max-w-4xl mx-auto flex flex-wrap justify-center gap-6">
          {STATS.map((s, i) => (
            <motion.div
              key={s.label}
              className="sticker-card px-6 py-4 text-center"
              style={{ rotate: STICKER_ROTATIONS[i] }}
              initial={{ opacity: 0, y: 30, rotate: 0 }}
              whileInView={{ opacity: 1, y: 0, rotate: STICKER_ROTATIONS[i] }}
              viewport={{ once: true, amount: 0.5 }}
              transition={{ delay: i * 0.1, duration: 0.5 }}
              whileHover={{ rotate: 0, scale: 1.05 }}
            >
              <p className="text-2xl font-semibold text-ink">{s.value}</p>
              <p className="text-[10px] text-[#7a7a7a] font-semibold mt-1 uppercase tracking-wider">{s.label}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ── Features (Polaroid sticker cards) ── */}
      <section className="py-20 px-6 bg-[#faf9f6]">
        <div className="max-w-6xl mx-auto">
          <motion.div
            className="mb-14 text-center"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
          >
            <h2 className="text-2xl sm:text-3xl font-semibold text-ink tracking-tight">
              Everything you need,{" "}
              <span style={{ fontFamily: "var(--font-caveat)" }} className="text-accent-teal text-3xl sm:text-4xl">
                nothing you don&apos;t
              </span>
            </h2>
            <p className="text-sm text-[#7a7a7a] mt-3 max-w-lg mx-auto">
              Built for precision, scale, and compliance from day one.
            </p>
          </motion.div>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.title}
                className="sticker-card p-6 flex flex-col group"
                style={{ rotate: STICKER_ROTATIONS[i] }}
                initial={{ opacity: 0, y: 40, rotate: 0 }}
                whileInView={{ opacity: 1, y: 0, rotate: STICKER_ROTATIONS[i] }}
                viewport={{ once: true, amount: 0.3 }}
                transition={{ delay: i * 0.12, duration: 0.5 }}
                whileHover={{ rotate: 0, y: -6, scale: 1.02 }}
              >
                <div className="text-2xl mb-4">{f.icon}</div>
                <h3 className="text-sm font-semibold text-ink mb-2">{f.title}</h3>
                <p className="text-xs text-[#7a7a7a] leading-relaxed mb-4 flex-1">{f.desc}</p>
                <div className="flex flex-wrap gap-1.5">
                  {f.tags.map((t) => (
                    <span key={t} className={`badge-sticker ${f.badge} text-[9px]`}>
                      {t}
                    </span>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Demo Form (simplified URL-only) ── */}
      <section className="py-20 px-6 bg-[#f5f2ed]" ref={formRef} id="try-form">
        <div className="max-w-2xl mx-auto">
          <motion.div
            className="mb-10 text-center"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-2xl font-semibold text-ink tracking-tight">
              Ready to{" "}
              <span style={{ fontFamily: "var(--font-caveat)" }} className="text-accent text-3xl">scout?</span>
            </h2>
            <p className="text-sm text-[#7a7a7a] mt-2">
              Paste a URL. We handle the rest.
            </p>
          </motion.div>

          <motion.div
            className="notebook-page p-8"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <form className="grid gap-5" onSubmit={handleDetailedSubmit}>
              <Field label="Your brand website">
                <input
                  id="form-url-input"
                  className="glass-input focus-ring w-full px-4 py-3.5 text-sm font-mono"
                  onChange={(e) => setBrandUrl(e.target.value)}
                  placeholder="https://example.com"
                  required
                  type="url"
                  value={brandUrl}
                />
              </Field>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Target Country">
                  <select
                    value={geoCountry}
                    onChange={(e) => setGeoCountry(e.target.value)}
                    className="glass-input focus-ring w-full px-4 py-3.5 text-sm bg-white cursor-pointer"
                  >
                    <option value="India">India</option>
                    <option value="United States">United States</option>
                    <option value="United Kingdom">United Kingdom</option>
                    <option value="Germany">Germany</option>
                    <option value="France">France</option>
                    <option value="Australia">Australia</option>
                    <option value="Custom">Custom Region/City/Language...</option>
                  </select>
                </Field>

                <Field label={geoCountry === "Custom" ? "Target Details (Required)" : "City / Language / Region (Optional)"}>
                  <input
                    type="text"
                    value={geoCustom}
                    onChange={(e) => setGeoCustom(e.target.value)}
                    placeholder={geoCountry === "Custom" ? "e.g. US (Spanish), Berlin" : "e.g. Mumbai, English speakers"}
                    required={geoCountry === "Custom"}
                    className="glass-input focus-ring w-full px-4 py-3.5 text-sm font-mono"
                  />
                </Field>
              </div>

              <Field label="Campaign Goal">
                <select
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  className="glass-input focus-ring w-full px-4 py-3.5 text-sm bg-white cursor-pointer"
                >
                  <option value="ugc">UGC (User Generated Content)</option>
                  <option value="awareness">Brand Awareness</option>
                  <option value="conversion">Conversions & Sales</option>
                  <option value="affiliate">Affiliate Partnership</option>
                </select>
              </Field>

              <Field label="Target Platforms">
                <div className="flex flex-wrap gap-3 mt-1.5">
                  {PLATFORM_OPTIONS.map((p) => {
                    const isSelected = selectedPlatforms.includes(p);
                    const activeColor = p === "youtube" ? "badge-coral" : p === "instagram" ? "badge-lavender" : "badge-teal";
                    return (
                      <button
                        key={p}
                        type="button"
                        onClick={() => {
                          setSelectedPlatforms((prev) =>
                            prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]
                          );
                        }}
                        className={`px-4 py-2 rounded-lg border text-xs font-semibold capitalize cursor-pointer transition-all ${
                          isSelected
                            ? `badge-sticker ${activeColor} border-transparent shadow-sm`
                            : "border-[#e8e4df] bg-white text-[#7a7a7a] hover:border-[#d4cfc8]"
                        }`}
                      >
                        {p}
                      </button>
                    );
                  })}
                </div>
              </Field>

              <button
                id="analyze-btn"
                className="glow-btn-accent focus-ring w-full rounded-xl py-3.5 text-sm font-semibold cursor-pointer mt-1"
                type="submit"
              >
                Analyze &amp; Generate Campaign
              </button>
            </form>

            {/* Trust strip */}
            <div className="mt-6 pt-5 border-t border-[#e8e4df] flex flex-wrap items-center justify-center gap-5 text-[10px] text-[#b5afa6] font-semibold">
              {["SOC 2", "GDPR", "No Scraping", "Encrypted"].map((t) => (
                <span key={t} className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#d4cfc8]" />
                  {t}
                </span>
              ))}
            </div>
          </motion.div>

          {/* API Health indicator */}
          <div className="mt-6 flex justify-center">
            <div className="flex items-center gap-2 text-xs font-medium">
              <span className="text-[#b5afa6]">API</span>
              <span className={`w-1.5 h-1.5 rounded-full ${apiHealth === "online" ? "bg-success" : apiHealth === "offline" ? "bg-danger" : "bg-warning animate-pulse"}`} />
              <span className="text-[#7a7a7a] capitalize font-mono text-[10px]">{apiHealth}</span>
            </div>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-[#e8e4df] py-8 px-6 bg-white">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-[#7a7a7a]">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-ink">Creator Scout</span>
            <span>© 2026</span>
          </div>
          <div className="flex gap-5">
            {["Privacy", "Terms", "Security", "Status"].map((l) => (
              <button key={l} className="hover:text-ink transition-colors cursor-pointer">{l}</button>
            ))}
          </div>
        </div>
      </footer>
    </div>
  );
}

// ─── Workspace ────────────────────────────────────────────────────────────────
function Workspace({
  campaign,
  creators,
  onReset,
  onFindCreators,
  onRefreshCreators,
  onStatusChange,
  onPitchChange,
  onPitchSave,
  onNotesChange,
  onNotesSave,
  onExport,
  onSendOutreach,
  isFindingCreators,
  isExporting,
  isSendingOutreach,
  outreachConfig,
  message,
  onDismissMessage,
}: {
  campaign: Campaign;
  creators: CampaignCreator[];
  onReset: () => void;
  onFindCreators: () => void;
  onRefreshCreators: () => void;
  onStatusChange: (id: string, status: string) => void;
  onPitchChange: (id: string, pitch: string) => void;
  onPitchSave: (id: string, pitch: string) => void;
  onNotesChange: (id: string, notes: string) => void;
  onNotesSave: (id: string, notes: string) => void;
  onExport: () => void;
  onSendOutreach: (id: string, subject: string, body: string) => void;
  isFindingCreators: boolean;
  isExporting: boolean;
  isSendingOutreach: boolean;
  outreachConfig: OutreachConfig | null;
  message: string;
  onDismissMessage: () => void;
}) {
  const [activeTab, setActiveTab] = useState<ActiveTab>("brief");
  const [selectedId, setSelectedId] = useState<string | null>(creators[0]?.creator_id ?? null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const jobSummary = jobSummaryFor(campaign);
  const hasPendingJobs = jobSummary.pending > 0;

  // ── Agentic Mode state ────────────────────────────────────────────────────
  const [agentThreadId, setAgentThreadId] = useState<string | null>(null);
  const [agentStatus, setAgentStatus] = useState<{
    paused: boolean;
    next_node: string | null;
    shortlist: any[];
    outreach_drafts: any[];
    brand_brief: Record<string, any> | null;
    error: string | null;
  } | null>(null);
  const [agentTokens, setAgentTokens] = useState<string[]>([]);
  const [isAgentRunning, setIsAgentRunning] = useState(false);

  // Load thread ID for this campaign on mount/change
  useEffect(() => {
    if (typeof window === "undefined" || !campaign?.id) return;
    const stored = localStorage.getItem(`cs_agent_thread_${campaign.id}`);
    if (stored) {
      setAgentThreadId(stored);
      setIsAgentRunning(true);
      api.getGraphStatus(stored)
        .then((status) => {
          setAgentStatus({
            paused: status.paused,
            next_node: status.next_node,
            brand_brief: status.brand_brief || null,
            shortlist: status.shortlist || [],
            outreach_drafts: status.outreach_drafts || [],
            error: status.error || null,
          });
          if (status.shortlist && status.shortlist.length > 0) {
            onRefreshCreators();
          }
        })
        .catch((err) => {
          console.error("Failed to restore agent status:", err);
          localStorage.removeItem(`cs_agent_thread_${campaign.id}`);
          setAgentThreadId(null);
        })
        .finally(() => {
          setIsAgentRunning(false);
        });
    } else {
      setAgentThreadId(null);
      setAgentStatus(null);
    }
  }, [campaign?.id]);

  // Wire up InsForge Realtime websocket subscription
  useEffect(() => {
    if (!agentThreadId || !hasInsForgeConfig) return;
    let active = true;
    const client = getInsForgeClient();
    
    const setupRealtime = async () => {
      try {
        await client.realtime.connect();
        if (!active) return;
        
        await client.realtime.subscribe(`graph_runs:${agentThreadId}`);
        if (!active) return;
        
        // Listen for realtime events (SocketMessage)
        const handleEvent = (msg: any) => {
          if (!active) return;
          console.log("[realtime] event received:", msg);
          
          if (msg.channel === `graph_runs:${agentThreadId}`) {
            if (msg.event === "graph.paused") {
              setAgentStatus({
                paused: true,
                next_node: msg.payload.next_node,
                brand_brief: msg.payload.brand_brief || null,
                shortlist: msg.payload.shortlist || [],
                outreach_drafts: msg.payload.outreach_drafts || [],
                error: msg.payload.error || null,
              });
              setIsAgentRunning(false);
              onRefreshCreators();
            } else if (msg.event === "graph.completed") {
              setAgentStatus({
                paused: false,
                next_node: null,
                brand_brief: null,
                shortlist: msg.payload.shortlist || [],
                outreach_drafts: msg.payload.outreach_drafts || [],
                error: msg.payload.error || null,
              });
              setIsAgentRunning(false);
              localStorage.removeItem(`cs_agent_thread_${campaign.id}`);
              setAgentThreadId(null);
              onRefreshCreators();
            }
          }
        };
        
        client.realtime.on("graph.paused", handleEvent);
        client.realtime.on("graph.completed", handleEvent);
        
        return () => {
          active = false;
          client.realtime.off("graph.paused", handleEvent);
          client.realtime.off("graph.completed", handleEvent);
          client.realtime.unsubscribe(`graph_runs:${agentThreadId}`);
        };
      } catch (err) {
        console.error("[realtime] setup error:", err);
      }
    };
    
    const cleanupPromise = setupRealtime();
    
    return () => {
      active = false;
      cleanupPromise.then((cleanup) => {
        if (cleanup) cleanup();
      });
    };
  }, [agentThreadId, campaign?.id]);

  async function startAgentRun() {
    if (!campaign?.id || !campaign?.brand_url) return;
    setIsAgentRunning(true);
    setAgentTokens([]);
    setAgentStatus(null);
    setAgentThreadId(null);
    try {
      const es = new EventSource(
        `/api/v1/graph/run/stream?campaign_id=${encodeURIComponent(campaign.id)}&brand_url=${encodeURIComponent(campaign.brand_url)}&goal=${encodeURIComponent(campaign.goal || "ugc")}`
      );
      es.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.event === "start") {
            setAgentThreadId(data.thread_id);
            localStorage.setItem(`cs_agent_thread_${campaign.id}`, data.thread_id);
          }
          if (data.event === "token") setAgentTokens((t) => [...t, data.text]);
          if (data.event === "paused") {
            setAgentStatus({ paused: true, next_node: data.next_node, brand_brief: data.brand_brief, shortlist: [], outreach_drafts: [], error: null });
            setAgentThreadId(data.thread_id);
            localStorage.setItem(`cs_agent_thread_${campaign.id}`, data.thread_id);
            es.close();
            setIsAgentRunning(false);
          }
          if (data.event === "error") {
            setAgentStatus({ paused: false, next_node: null, brand_brief: null, shortlist: [], outreach_drafts: [], error: data.message });
            es.close();
            setIsAgentRunning(false);
          }
        } catch {}
      };
      es.onerror = () => { es.close(); setIsAgentRunning(false); };
    } catch (err) {
      setIsAgentRunning(false);
      setAgentStatus((s) => (s ? { ...s, error: err instanceof Error ? err.message : "Agent error" } : { paused: false, next_node: null, brand_brief: null, shortlist: [], outreach_drafts: [], error: err instanceof Error ? err.message : "Agent error" }));
    }
  }

  async function resumeAgent(approved: boolean) {
    if (!agentThreadId) return;
    setIsAgentRunning(true);
    try {
      if (!approved) {
        localStorage.removeItem(`cs_agent_thread_${campaign.id}`);
        setAgentThreadId(null);
        setAgentStatus(null);
      }
      const result = await api.resumeGraphRun(agentThreadId, { approved });
      if (approved) {
        const rs = result.run_status as any;
        if (rs) {
          setAgentStatus(rs);
          if (rs.shortlist && rs.shortlist.length > 0) {
            onRefreshCreators();
          }
          if (!rs.paused) {
            localStorage.removeItem(`cs_agent_thread_${campaign.id}`);
            setAgentThreadId(null);
          }
        }
      }
    } catch (err) {
      setAgentStatus((s) => (s ? { ...s, error: err instanceof Error ? err.message : "Resume error" } : null));
    } finally {
      setIsAgentRunning(false);
    }
  }


  const activeCreator = useMemo(
    () => creators.find((c) => c.creator_id === selectedId) ?? creators[0] ?? null,
    [creators, selectedId]
  );
  const activeSendableContact = sendableEmailContact(activeCreator);
  const activeOutreachMessage = latestOutreachMessage(activeCreator);
  const sendBlockReason = outreachBlockReason(activeCreator, outreachConfig, isSendingOutreach);

  const TABS = [
    { id: "brief",     label: "Brand Brief",      icon: <Icon.brief /> },
    { id: "strategy",  label: "Discovery",        icon: <Icon.strategy /> },
    { id: "shortlist", label: "Shortlist",         icon: <Icon.shortlist />, badge: creators.length || undefined },
    { id: "outreach",  label: "Outreach",          icon: <Icon.outreach /> },
    { id: "crm",       label: "Pipeline",          icon: <Icon.crm /> },
    { id: "export",    label: "Export",            icon: <Icon.export /> },
    { id: "billing",   label: "Plans & Billing",   icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg> },
  ] as const;

  const [finderLogIdx, setFinderLogIdx] = useState(0);
  useEffect(() => {
    if (!isFindingCreators) return;
    const t = setInterval(() => setFinderLogIdx((p) => (p + 1) % FINDER_LOGS.length), 1500);
    return () => clearInterval(t);
  }, [isFindingCreators]);

  function copyText(text: string, id: string) {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1800);
  }

  return (
    <div className="flex h-screen bg-[#faf9f6] text-ink overflow-hidden">
      {/* ── Sidebar ── */}
      <aside className="w-60 shrink-0 flex flex-col border-r border-[#e8e4df] bg-white">
        {/* Top */}
        <div className="px-5 py-5 border-b border-[#e8e4df]">
          <div className="flex items-center gap-2.5 mb-5">
            <div className="w-6 h-6 rounded-md bg-[#1a1a1a] flex items-center justify-center text-[#faf9f6] font-bold text-[9px] shrink-0">CS</div>
            <div>
              <p className="text-xs font-semibold text-ink leading-none">Creator Scout</p>
            </div>
          </div>

          <div className="rounded-lg border border-[#e8e4df] bg-[#f8f6f2] p-3 relative overflow-hidden">
            <p className="text-[9px] font-bold uppercase tracking-widest text-[#7a7a7a] mb-1">Project</p>
            <p className="text-xs font-semibold text-ink truncate">{campaign.brief.brand_name || "Campaign"}</p>
            <a
              href={campaign.brand_url}
              target="_blank"
              rel="noreferrer"
              className="text-[10px] text-[#7a7a7a] hover:text-ink transition-colors truncate flex items-center gap-1 mt-1 font-mono"
            >
              {campaign.brand_url.replace(/^https?:\/\//, "")}
            </a>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 grid gap-1">
          {TABS.map((tab) => {
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-all cursor-pointer text-left group ${
                  active
                    ? "bg-[#f3f0eb] text-ink shadow-sm"
                    : "text-[#7a7a7a] hover:text-ink hover:bg-[#f8f6f2]"
                }`}
              >
                <span className="flex items-center gap-2.5">
                  <span className={active ? "text-accent" : "text-[#b5afa6]"}>{tab.icon}</span>
                  {tab.label}
                </span>
                {"badge" in tab && tab.badge ? (
                  <span className="text-[10px] badge-sticker badge-coral py-0 px-1.5">{tab.badge}</span>
                ) : null}
              </button>
            );
          })}
        </nav>

        {/* Bottom */}
        <div className="px-3 py-4 border-t border-[#e8e4df] grid gap-2">
          <button
            onClick={onReset}
            className="w-full text-xs font-medium text-[#7a7a7a] hover:text-ink hover:bg-[#f3f0eb] rounded-lg py-2 transition-all cursor-pointer text-left px-3"
          >
            ← New Campaign
          </button>
        </div>
      </aside>

      {/* ── Main pane ── */}
      <div className="flex-1 flex flex-col overflow-hidden bg-[#faf9f6]">
        {/* Top bar */}
        <header className="shrink-0 h-12 border-b border-[#e8e4df] bg-white flex items-center px-6 gap-4">
          <div className="flex-1 flex items-center gap-2 text-xs font-mono">
            <span className="text-[#7a7a7a]">{campaign.brief.brand_name || campaign.brand_url}</span>
            <span className="text-[#d4cfc8]">/</span>
            <span className="text-ink capitalize font-semibold">{activeTab}</span>
          </div>
          {message && (
            <div className="flex items-center gap-2 bg-[#f8f6f2] border border-[#e8e4df] rounded-lg px-3 py-1 text-[10px] font-mono text-ink max-w-md truncate">
              <span>{message}</span>
              <button onClick={onDismissMessage} className="ml-1 text-[#7a7a7a] hover:text-ink cursor-pointer shrink-0">✕</button>
            </div>
          )}
        </header>

        {/* Scrollable content */}
        <main className="flex-1 overflow-y-auto scrollbar-thin px-8 py-8">
          <div className="max-w-5xl mx-auto">

            {/* ── Tab: Brief ── */}
            {activeTab === "brief" && (
              <motion.div className="grid gap-6" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
                <div>
                  <h2 className="text-xl font-semibold text-ink tracking-tight">Brand Intelligence</h2>
                  <p className="text-xs text-[#7a7a7a] mt-1 font-mono">Extracted positioning and audience profile.</p>
                </div>

                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <MetricCard label="Brand" value={campaign.brief.brand_name} accent />
                  <MetricCard label="Category" value={campaign.brief.category} />
                  <MetricCard label="Positioning" value={campaign.brief.price_positioning} />
                  <div className="rounded-xl border border-[#e8e4df] bg-white p-5 flex items-center justify-between">
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a]">Confidence</p>
                      <p className="text-xl font-semibold text-ink mt-1">{Math.round(campaign.brief.confidence * 100)}%</p>
                    </div>
                    <div className="w-12 h-12 rounded-full border-4 border-success/30 flex items-center justify-center">
                      <Icon.check />
                    </div>
                  </div>
                </div>

                <div className="rounded-xl border border-[#e8e4df] bg-white p-6">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a] mb-3">Target Customer</p>
                  <p className="text-ink text-sm leading-relaxed">{campaign.brief.target_audience}</p>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <ChipList label="Target Niches" values={campaign.brief.best_creator_niches} />
                  <ChipList label="Avoid Niches" values={campaign.brief.avoid_creator_types} />
                  <ChipList label="Tone" values={campaign.brief.tone} />
                  <ChipList label="Angles" values={campaign.brief.campaign_angles} />
                </div>

                {campaign.brief.evidence.length > 0 && (
                  <div className="rounded-xl border border-[#e8e4df] bg-white p-6">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a] mb-4">Evidence Sources</p>
                    <div className="grid gap-2">
                      {campaign.brief.evidence.map((ev, i) => (
                        <a key={i} href={ev.source_url} target="_blank" rel="noreferrer"
                          className="flex items-center justify-between rounded-lg bg-[#f8f6f2] border border-[#e8e4df] hover:border-[#d4cfc8] px-4 py-3 transition-all group"
                        >
                          <div className="truncate mr-3">
                            <span className="text-xs font-medium text-ink">{ev.title || ev.page_type}</span>
                            <span className="text-[10px] text-[#7a7a7a] ml-2 font-mono">{ev.source_url.replace(/^https?:\/\//, "").slice(0, 40)}</span>
                          </div>
                          <span className="badge-sticker badge-amber text-[9px] py-0">{ev.field}</span>
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                {/* ── Agentic Mode Panel ── */}
                <motion.div
                  className="sticker-card p-6"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, delay: 0.15 }}
                >
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <p className="text-xs font-bold text-ink flex items-center gap-2">
                        <span className="text-accent">⬡</span> Agentic Mode
                        <span style={{ fontFamily: "var(--font-caveat)" }} className="text-sm text-[#7a7a7a] font-normal">
                          LangGraph multi-agent
                        </span>
                      </p>
                      <p className="text-[10px] text-[#7a7a7a] mt-0.5">
                        Brand scan → discovery → scoring → shortlist with human approval gates.
                      </p>
                    </div>
                    {!agentThreadId && !isAgentRunning && (
                      <button
                        id="agentic-start-btn"
                        onClick={startAgentRun}
                        className="glow-btn-accent text-white text-xs font-semibold px-4 py-2 rounded-lg cursor-pointer"
                      >
                        ▶ Start Agent Run
                      </button>
                    )}
                    {isAgentRunning && (
                      <span className="badge-sticker badge-lavender text-[9px] animate-pulse">Running…</span>
                    )}
                  </div>

                  {agentTokens.length > 0 && (
                    <div className="bg-[#f8f6f2] border border-[#e8e4df] rounded-lg p-4 mb-4 font-mono text-xs text-ink whitespace-pre-wrap max-h-32 overflow-y-auto">
                      {agentTokens.join("")}
                    </div>
                  )}

                  {agentStatus?.paused && (
                    <motion.div
                      initial={{ opacity: 0, scale: 0.97 }}
                      animate={{ opacity: 1, scale: 1 }}
                      className="border border-accent/30 bg-accent/5 rounded-xl p-4 grid gap-3"
                    >
                      <div className="flex items-center gap-2">
                        <span className="badge-sticker badge-amber text-[9px]">Gate</span>
                        <p className="text-xs font-semibold text-ink">
                          Waiting at{" "}
                          <span className="font-mono text-accent">
                            {agentStatus.next_node?.replace(/_node$/, "") ?? "…"}
                          </span>
                        </p>
                      </div>

                      {agentStatus.next_node === "query_planner_node" && agentStatus.brand_brief && (
                        <div className="grid grid-cols-2 gap-2 text-[10px] text-[#7a7a7a]">
                          {(["brand_name", "primary_category", "price_positioning"] as const).map((k) => (
                            <div key={k}>
                              <p className="font-bold uppercase tracking-widest mb-0.5">{k.replace(/_/g, " ")}</p>
                              <p className="text-ink font-medium">{String(agentStatus.brand_brief![k] ?? "—")}</p>
                            </div>
                          ))}
                        </div>
                      )}

                      {agentStatus.next_node === "outreach_draft_node" && (
                        <p className="text-xs text-[#7a7a7a]">
                          {agentStatus.shortlist.length} creators shortlisted — approve to draft outreach.
                        </p>
                      )}

                      {agentStatus.next_node === "send_outreach_node" && (
                        <p className="text-xs text-[#7a7a7a]">
                          {agentStatus.outreach_drafts.length} drafts ready — approve to send emails.
                        </p>
                      )}

                      <div className="flex gap-2">
                        <button
                          id="agent-approve-btn"
                          onClick={() => resumeAgent(true)}
                          disabled={isAgentRunning}
                          className="flex-1 glow-btn-accent text-white text-xs font-semibold py-2 rounded-lg cursor-pointer disabled:opacity-50"
                        >
                          ✓ Approve & Continue
                        </button>
                        <button
                          id="agent-reject-btn"
                          onClick={() => resumeAgent(false)}
                          disabled={isAgentRunning}
                          className="flex-1 text-xs font-semibold py-2 rounded-lg border border-[#e8e4df] text-[#7a7a7a] hover:text-ink hover:bg-[#f3f0eb] transition cursor-pointer disabled:opacity-50"
                        >
                          ✕ Reject
                        </button>
                      </div>
                    </motion.div>
                  )}

                  {agentStatus?.error && (
                    <p className="text-xs text-red-500 font-mono mt-2">{agentStatus.error}</p>
                  )}

                  {agentThreadId && !agentStatus?.paused && !agentStatus?.error && !isAgentRunning && (
                    <p className="text-xs text-success font-semibold mt-2">✓ Agent run completed.</p>
                  )}
                </motion.div>

              </motion.div>
            )}


            {/* ── Tab: Strategy ── */}
            {activeTab === "strategy" && (
              <motion.div className="grid gap-6" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
                <div>
                  <h2 className="text-xl font-semibold text-ink tracking-tight">Discovery Pipeline</h2>
                  <p className="text-xs text-[#7a7a7a] mt-1 font-mono">YouTube query discovery runs through the worker; shortlists rank cached/indexed creators.</p>
                </div>

                <div className="notebook-page p-6">
                  <div className="grid gap-3 sm:grid-cols-4 mb-5">
                    {([
                      ["Queued", jobSummary.queued, "badge-amber"],
                      ["Running", jobSummary.running, "badge-lavender"],
                      ["Passed", jobSummary.passed, "badge-teal"],
                      ["Failed", jobSummary.failed, "badge-coral"],
                    ] as const).map(([label, value, badge]) => (
                      <div key={label} className="rounded-xl border border-[#e8e4df] bg-white p-4">
                        <p className="text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a]">{label}</p>
                        <div className="mt-2 flex items-center justify-between">
                          <span className="text-lg font-semibold text-ink font-mono">{value}</span>
                          <span className={`badge-sticker ${badge} text-[9px] py-0`}>jobs</span>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-5">
                    <div>
                      <h3 className="text-sm font-semibold text-ink">Build shortlist</h3>
                      <div className="flex flex-wrap gap-2 mt-3">
                        {[`goal:${campaign.goal}`, `geo:${campaign.geo}`, `platforms:${campaign.platforms.join(",")}`].map((t) => (
                          <span key={t} className="badge-sticker badge-teal text-[10px]">{t}</span>
                        ))}
                      </div>
                      <p className="text-[11px] leading-relaxed text-[#7a7a7a] mt-3 max-w-xl">
                        Instagram and TikTok are filters over cached/indexed profiles only. They are not live scraping providers until official adapters are added.
                      </p>
                    </div>
                    <button
                      id="run-discovery-btn"
                      onClick={onFindCreators}
                      disabled={isFindingCreators || hasPendingJobs}
                      className="glow-btn-accent px-6 py-2.5 rounded-xl text-xs font-semibold cursor-pointer disabled:opacity-50 shrink-0"
                      title={hasPendingJobs ? "Wait for queued/running discovery jobs before building a fresh shortlist." : undefined}
                    >
                      {isFindingCreators ? "Building..." : hasPendingJobs ? "Waiting on worker" : "Build shortlist"}
                    </button>
                  </div>

                  {hasPendingJobs && (
                    <div className="mt-5 rounded-lg border border-[#f0d9a6] bg-[#fdf0db] p-4">
                      <p className="text-xs font-semibold text-[#b07920]">Discovery jobs are still queued or running.</p>
                      <p className="text-[11px] leading-relaxed text-[#7a7a7a] mt-1">
                        Start the worker to process fresh YouTube results, then build the shortlist. Existing cached creators remain available once jobs finish or fail.
                      </p>
                    </div>
                  )}

                  {isFindingCreators && (
                    <div className="mt-6 rounded-lg border border-[#e8e4df] bg-[#f8f6f2] p-4 font-mono text-[10px]">
                      {FINDER_LOGS.map((log, i) => {
                        const done = i < finderLogIdx;
                        const active = i === finderLogIdx;
                        return (
                          <div key={i} className={`flex items-center gap-2 py-1 ${done ? "text-[#b5afa6]" : active ? "text-ink" : "text-[#d4cfc8]"}`}>
                            <span>{done ? "✓" : active ? "▸" : "○"}</span>
                            <span>{log}</span>
                            {active && <span className="w-1.5 h-3 bg-accent inline-block animate-pulse rounded-sm" />}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {campaign.search_queries.length > 0 && (
                  <ChipList label="Queries" values={campaign.search_queries} />
                )}
              </motion.div>
            )}

            {/* ── Tab: Shortlist ── */}
            {activeTab === "shortlist" && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="text-xl font-semibold text-ink tracking-tight">Shortlist</h2>
                  </div>
                  {creators.length > 0 && (
                    <button onClick={() => setActiveTab("crm")} className="text-xs font-semibold text-ink border border-[#e8e4df] bg-white hover:bg-[#f3f0eb] px-4 py-2 rounded-lg transition cursor-pointer shadow-sm">
                      Pipeline →
                    </button>
                  )}
                </div>

                {creators.length === 0 ? (
                  <div className="notebook-page p-16 text-center">
                    <p className="text-ink font-semibold text-sm">Empty shortlist</p>
                    <p className="text-[#7a7a7a] text-xs mt-1 mb-4 font-mono">Execute discovery to populate.</p>
                  </div>
                ) : (
                  <div className="grid gap-3 xl:grid-cols-[1fr_340px]">
                    {/* List */}
                    <div className="grid gap-2 max-h-[calc(100vh-220px)] overflow-y-auto scrollbar-thin pr-1">
                      {creators.map((item) => {
                        const name = item.creator?.display_name || item.creator_id;
                        const selected = selectedId === item.creator_id;
                        const score = item.fit_score;

                        return (
                          <motion.div
                            key={item.id}
                            onClick={() => setSelectedId(item.creator_id)}
                            className={`flex items-center gap-4 p-3 rounded-xl border cursor-pointer transition-all ${
                              selected
                                ? "border-accent/30 bg-accent/5 shadow-sm"
                                : "border-[#e8e4df] bg-white hover:border-[#d4cfc8] hover:shadow-sm"
                            }`}
                            whileHover={{ x: 2 }}
                          >
                            <Avatar name={name} size="sm" />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-sm font-semibold text-ink truncate">{name}</span>
                                <PlatformPill platform={item.creator?.accounts[0]?.platform || "unknown"} />
                              </div>
                              <div className="flex items-center gap-2 mt-1 text-[10px] text-[#7a7a7a] font-mono flex-wrap">
                                <span>{item.creator?.primary_niche || "—"}</span>
                                <span className="text-[#d4cfc8]">/</span>
                                <span className={item.risks.length ? "text-danger" : "text-success"}>
                                  {item.risks.length ? item.risks[0] : "Clean"}
                                </span>
                              </div>
                            </div>
                            <div className="text-right shrink-0 pr-2">
                              <span className="text-[10px] font-mono text-[#b5afa6] block leading-none mb-1">Score</span>
                              <span className="text-sm font-semibold text-ink leading-none">{score}</span>
                            </div>
                          </motion.div>
                        );
                      })}
                    </div>

                    {/* Detail panel */}
                    <div className="notebook-page p-5 h-fit sticky top-0 max-h-[calc(100vh-140px)] overflow-y-auto scrollbar-thin">
                      {!activeCreator?.creator ? (
                        <div className="py-8 text-center text-xs text-[#7a7a7a] font-mono">
                          Select a record.
                        </div>
                      ) : (
                        <div className="grid gap-5">
                          {/* Header / Avatar */}
                          <div className="flex items-start gap-3">
                            <Avatar name={activeCreator.creator.display_name} size="md" />
                            <div className="min-w-0">
                              <p className="text-sm font-semibold text-ink">{activeCreator.creator.display_name}</p>
                              <p className="text-[10px] text-[#7a7a7a] font-mono mt-0.5">{activeCreator.creator.primary_niche}</p>
                              <div className="mt-2">
                                <PlatformPill platform={activeCreator.creator.accounts[0]?.platform || "unknown"} />
                              </div>
                            </div>
                          </div>

                          <p className="text-xs text-[#7a7a7a] leading-relaxed">{activeCreator.creator.summary}</p>

                          {/* Compliance Status */}
                          <div className="rounded-lg border border-[#e8e4df] bg-[#f8f6f2] p-3">
                            <p className="text-[9px] font-bold uppercase tracking-widest text-[#7a7a7a] mb-1.5">Compliance Status</p>
                            <div className="flex flex-wrap gap-1.5">
                              <span className={`badge-sticker ${
                                activeCreator.creator.contacts[0]?.permission_basis?.toLowerCase() === "opt-in" || activeCreator.creator.contacts[0]?.permission_basis?.toLowerCase() === "public"
                                  ? "badge-teal"
                                  : "badge-amber"
                              } text-[9px] py-0.5`}>
                                ✓ {activeCreator.creator.contacts[0]?.permission_basis || "Public Data"}
                              </span>
                              {activeCreator.risks && activeCreator.risks.length > 0 ? (
                                <span className="badge-sticker badge-coral text-[9px] py-0.5">
                                  ⚠ Risk: {activeCreator.risks[0]}
                                </span>
                              ) : (
                                <span className="badge-sticker badge-teal text-[9px] py-0.5">
                                  ✓ Low Risk
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Evidence Grid / Match Reasons */}
                          <div className="rounded-lg border border-[#e8e4df] bg-white p-3">
                            <p className="text-[9px] font-bold uppercase tracking-widest text-[#7a7a7a] mb-1.5">Match Alignment ({activeCreator.fit_score}%)</p>
                            {activeCreator.evidence?.[0]?.match_reasons && activeCreator.evidence[0].match_reasons.length > 0 ? (
                              <div className="flex flex-wrap gap-1.5 mt-1.5">
                                {activeCreator.evidence[0].match_reasons.map((reason, idx) => (
                                  <span key={idx} className="badge-sticker badge-lavender text-[9px] py-0.5">
                                    ✦ {reason}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <p className="text-[10px] text-[#7a7a7a] italic mt-1 font-mono">Matched on niche interests.</p>
                            )}
                          </div>

                          {/* Pitch Composition Box */}
                          <div className="rounded-lg border border-[#e8e4df] bg-[#f8f6f2] p-3">
                            <p className="text-[9px] font-bold uppercase tracking-widest text-[#7a7a7a] mb-2">Personalized Pitch</p>
                            <textarea
                              className="w-full h-28 rounded-lg border border-[#e8e4df] bg-white p-2.5 font-mono text-[10px] leading-relaxed text-ink resize-none focus:outline-none focus:border-[#c4bfb7] focus:shadow-sm transition-all"
                              value={activeCreator.recommended_pitch}
                              onChange={(e) => onPitchChange(activeCreator.creator_id, e.target.value)}
                              onBlur={(e) => onPitchSave(activeCreator.creator_id, e.target.value)}
                            />
                            <div className="flex gap-2 mt-2">
                              <button
                                type="button"
                                onClick={() => copyText(activeCreator.recommended_pitch, 'drawer-pitch')}
                                className="flex-1 py-1.5 rounded-lg border border-[#e8e4df] text-[10px] font-semibold text-ink bg-white hover:bg-[#f3f0eb] transition cursor-pointer flex items-center justify-center gap-1"
                              >
                                {copiedId === 'drawer-pitch' ? (
                                  <span className="text-[9px] text-success font-mono">Copied!</span>
                                ) : (
                                  <>
                                    <Icon.copy />
                                    <span>Copy Pitch</span>
                                  </>
                                )}
                              </button>
                            </div>
                          </div>

                          <div className="rounded-lg border border-[#e8e4df] bg-white p-3">
                            <p className="text-[9px] font-bold uppercase tracking-widest text-[#7a7a7a] mb-2">Private Notes</p>
                            <textarea
                              className="w-full h-20 rounded-lg border border-[#e8e4df] bg-[#f8f6f2] p-2.5 font-mono text-[10px] leading-relaxed text-ink resize-none focus:outline-none focus:border-[#c4bfb7] focus:shadow-sm transition-all"
                              value={activeCreator.notes ?? ""}
                              onChange={(e) => onNotesChange(activeCreator.creator_id, e.target.value)}
                              onBlur={(e) => onNotesSave(activeCreator.creator_id, e.target.value)}
                            />
                          </div>

                          {/* Contact Details */}
                          {activeCreator.creator.contacts.length > 0 && (
                            <div className="rounded-lg border border-[#e8e4df] bg-[#f8f6f2] p-3">
                              <p className="text-[9px] font-bold uppercase tracking-widest text-[#7a7a7a] mb-2">Contact Details</p>
                              {activeCreator.creator.contacts.map((c, i) => (
                                <div key={i} className="flex items-center justify-between py-1.5 border-b border-[#e8e4df] last:border-0">
                                  <div>
                                    <p className="text-[10px] text-ink font-mono">{c.value}</p>
                                  </div>
                                  <button
                                    onClick={() => copyText(c.value, `${activeCreator.creator_id}-${i}`)}
                                    className="text-[#7a7a7a] hover:text-ink transition cursor-pointer px-2"
                                  >
                                    {copiedId === `${activeCreator.creator_id}-${i}` ? (
                                      <span className="text-[9px] text-success font-mono">Copied</span>
                                    ) : <Icon.copy />}
                                  </button>
                                </div>
                              ))}
                            </div>
                          )}

                          <div className="grid gap-1.5">
                            {activeCreator.creator.accounts.map((acc, i) => (
                              <a key={i} href={acc.profile_url} target="_blank" rel="noreferrer"
                                className="flex items-center justify-between rounded-lg border border-[#e8e4df] bg-white hover:bg-[#f8f6f2] px-3 py-2 transition-all text-[11px]"
                              >
                                <span className="font-semibold text-ink capitalize">{acc.platform}</span>
                                <span className="text-[#7a7a7a] font-mono">@{acc.handle}</span>
                              </a>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </motion.div>
            )}

            {/* ── Tab: Outreach ── */}
            {activeTab === "outreach" && (
              <motion.div className="grid gap-6 lg:grid-cols-[240px_1fr]" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
                {/* Sidebar */}
                <div className="notebook-page p-5 h-fit">
                  <p className="text-[9px] font-bold uppercase tracking-widest text-[#7a7a7a] mb-4">Meta</p>
                  {!activeCreator ? (
                    <p className="text-xs text-[#7a7a7a] font-mono">No selection.</p>
                  ) : (
                    <div className="grid gap-4">
                      <div className="flex items-center gap-2">
                        <Avatar name={activeCreator.creator?.display_name || "?"} size="sm" />
                        <p className="text-sm font-semibold text-ink truncate">{activeCreator.creator?.display_name}</p>
                      </div>
                      <div className="border-t border-[#e8e4df] pt-4 grid gap-3 text-xs">
                        <div>
                          <p className="text-[9px] font-bold uppercase text-[#7a7a7a] mb-1">Score</p>
                          <p className="text-ink font-mono font-semibold">{activeCreator.fit_score}</p>
                        </div>
                        <div>
                          <p className="text-[9px] font-bold uppercase text-[#7a7a7a] mb-1">Compliance</p>
                          <p className="text-ink font-mono text-[10px]">{activeSendableContact?.permission_basis || sendBlockReason || "Ready"}</p>
                        </div>
                        <div>
                          <p className="text-[9px] font-bold uppercase text-[#7a7a7a] mb-1">Last Send</p>
                          <p className="text-ink font-mono text-[10px]">{activeOutreachMessage?.status || "No send"}</p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Composer */}
                <div className="notebook-page p-6">
                  <div className="flex items-center justify-between mb-5">
                    <h2 className="text-lg font-semibold text-ink">Composer</h2>
                  </div>

                  {!activeCreator ? (
                    <p className="text-[#7a7a7a] text-sm">Select a creator.</p>
                  ) : (
                    <div className="grid gap-4">
                      <div className="rounded-lg border border-[#e8e4df] bg-[#f8f6f2] p-3 text-[11px] font-mono grid gap-1.5">
                        <div className="flex"><span className="text-[#7a7a7a] w-12">From:</span><span className="text-ink">{outreachConfig?.from_email || "AutoSend sender"}</span></div>
                        <div className="flex"><span className="text-[#7a7a7a] w-12">To:</span><span className="text-ink">{activeSendableContact?.value || "-"}</span></div>
                        <div className="flex"><span className="text-[#7a7a7a] w-12">Status:</span><span className={sendBlockReason ? "text-warning" : "text-success"}>{sendBlockReason || "Ready to send"}</span></div>
                      </div>

                      <textarea
                        key={activeCreator.creator_id}
                        id="outreach-composer"
                        className="w-full min-h-[260px] rounded-lg border border-[#e8e4df] bg-white p-4 font-mono text-[11px] leading-relaxed text-ink resize-none focus:outline-none focus:border-[#c4bfb7] focus:shadow-sm transition-all"
                        defaultValue={defaultOutreachText(campaign, activeCreator)}
                      />

                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            copyText(`Hi ${activeCreator.creator?.display_name || "there"},\n\nPartnership inquiry from ${campaign.brief.brand_name}`, "draft");
                          }}
                          className="px-4 py-2 rounded-lg border border-[#e8e4df] text-xs font-semibold text-ink hover:bg-[#f3f0eb] transition cursor-pointer"
                        >
                          Copy
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            const composer = document.getElementById("outreach-composer") as HTMLTextAreaElement | null;
                            const fallback = activeCreator.outreach_draft?.subject || `Partnership - ${campaign.brief.brand_name}`;
                            const parsed = parseOutreachComposer(
                              composer?.value || defaultOutreachText(campaign, activeCreator),
                              fallback
                            );
                            onSendOutreach(activeCreator.creator_id, parsed.subject, parsed.body);
                          }}
                          disabled={Boolean(sendBlockReason)}
                          title={sendBlockReason || "Send with AutoSend"}
                          className="px-4 py-2 rounded-lg glow-btn-accent text-xs font-semibold cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {isSendingOutreach ? "Sending..." : "Send with AutoSend"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {/* ── Tab: CRM ── */}
            {activeTab === "crm" && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
                <div className="mb-6">
                  <h2 className="text-xl font-semibold text-ink tracking-tight">Pipeline</h2>
                </div>

                {creators.length === 0 ? (
                  <div className="notebook-page p-16 text-center">
                    <p className="text-ink font-semibold text-sm">Empty pipeline</p>
                  </div>
                ) : (
                  <div className="flex gap-4 overflow-x-auto scrollbar-thin pb-4 -mx-8 px-8">
                    {CRM_COLUMNS.map((col) => {
                      const colCreators = creators.filter((c) => c.status === col.id);
                      return (
                        <div key={col.id} className="shrink-0 w-56 flex flex-col rounded-xl border border-[#e8e4df] bg-white" style={{ minHeight: 400 }}>
                          <div className="flex items-center justify-between px-3 py-2.5 border-b border-[#e8e4df] bg-[#f8f6f2] rounded-t-xl">
                            <span className="text-[11px] font-semibold text-ink">{col.label}</span>
                            <span className="text-[10px] font-mono text-[#7a7a7a]">{colCreators.length}</span>
                          </div>
                          <div className="flex-1 p-2 grid gap-2 content-start overflow-y-auto scrollbar-thin">
                            {colCreators.map((c) => {
                              const name = c.creator?.display_name || c.creator_id;
                              return (
                                <div key={c.id} className="rounded-lg border border-[#e8e4df] bg-[#faf9f6] p-3 hover:border-[#d4cfc8] hover:shadow-sm transition-all">
                                  <div className="flex items-center gap-2 mb-2">
                                    <Avatar name={name} size="sm" />
                                    <p className="text-xs font-semibold text-ink truncate">{name}</p>
                                  </div>
                                  <div className="flex items-center justify-between gap-1 mt-3">
                                    <span className="text-[9px] font-mono text-[#7a7a7a]">Score: {c.fit_score}</span>
                                    <select
                                      value={c.status}
                                      onChange={(e) => onStatusChange(c.creator_id, e.target.value)}
                                      className="text-[9px] font-semibold bg-white border border-[#e8e4df] rounded-md px-1.5 py-1 text-ink appearance-none cursor-pointer hover:border-[#d4cfc8] focus:outline-none"
                                    >
                                      {CRM_COLUMNS.map((col) => (
                                        <option key={col.id} value={col.id}>{col.label}</option>
                                      ))}
                                    </select>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </motion.div>
            )}

            {/* ── Tab: Billing & Plans ── */}
            {activeTab === "billing" && (
              <motion.div className="max-w-3xl mx-auto" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
                <div className="mb-8">
                  <h2 className="text-xl font-semibold text-ink tracking-tight mb-1">Plans & Billing</h2>
                  <p className="text-sm text-[#7a7a7a]">Choose a plan that grows with your outreach.
                    <span style={{ fontFamily: "var(--font-caveat)" }} className="text-accent text-base ml-1">no hidden fees.</span>
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                  {([
                    {
                      id: "free",
                      name: "Free",
                      price: "$0",
                      period: "/mo",
                      badge: "badge-teal",
                      color: "#1e7a72",
                      features: ["1 brand scan", "5 creator previews", "Basic scoring"],
                      cta: "Current",
                      ctaDisabled: true,
                      rotate: -1.5,
                    },
                    {
                      id: "starter",
                      name: "Starter",
                      price: "$29",
                      period: "/mo",
                      badge: "badge-coral",
                      color: "#c4402d",
                      features: ["3 campaigns/mo", "150 creator profiles", "Email outreach drafts"],
                      cta: "Upgrade",
                      ctaDisabled: false,
                      rotate: 1,
                    },
                    {
                      id: "growth",
                      name: "Growth",
                      price: "$79",
                      period: "/mo",
                      badge: "badge-lavender",
                      color: "#6b4ec0",
                      features: ["15 campaigns/mo", "1,000 creator profiles", "CSV export + CRM"],
                      cta: "Upgrade",
                      ctaDisabled: false,
                      rotate: -1,
                      popular: true,
                    },
                    {
                      id: "agency",
                      name: "Agency",
                      price: "$249",
                      period: "/mo",
                      badge: "badge-amber",
                      color: "#b07920",
                      features: ["Unlimited campaigns", "Multi-brand workspace", "Team seats + API"],
                      cta: "Upgrade",
                      ctaDisabled: false,
                      rotate: 1.5,
                    },
                  ] as const).map((plan) => (
                    <motion.div
                      key={plan.id}
                      className="sticker-card p-5 flex flex-col gap-3 relative"
                      style={{ rotate: `${plan.rotate}deg` }}
                      whileHover={{ rotate: 0, y: -4, scale: 1.02 }}
                      transition={{ type: "spring", stiffness: 280, damping: 20 }}
                    >
                      {"popular" in plan && plan.popular && (
                        <span className="absolute -top-2 left-1/2 -translate-x-1/2 badge-sticker badge-lavender text-[9px] px-2 py-0.5 shadow-sm">⭐ Popular</span>
                      )}
                      <div className="flex items-start justify-between">
                        <span className={`badge-sticker ${plan.badge} text-[9px]`}>{plan.name}</span>
                      </div>
                      <div>
                        <span className="text-2xl font-bold text-ink">{plan.price}</span>
                        <span className="text-xs text-[#7a7a7a]">{plan.period}</span>
                      </div>
                      <ul className="flex-1 grid gap-1.5">
                        {plan.features.map((f) => (
                          <li key={f} className="text-xs text-[#7a7a7a] flex items-start gap-1.5">
                            <span className="text-success mt-0.5 shrink-0">✓</span>{f}
                          </li>
                        ))}
                      </ul>
                      <button
                        id={`billing-plan-${plan.id}`}
                        disabled={plan.ctaDisabled}
                        onClick={async () => {
                          const planId = plan.id as string;
                          if (plan.ctaDisabled || planId === "free") return;
                          try {
                            const result = await api.createBillingCheckout({
                              plan: plan.id as "starter" | "growth" | "agency",
                              return_url: typeof window !== "undefined" ? window.location.origin + "/" : "/",
                            });
                            if (result.checkout_url) {
                              window.location.href = result.checkout_url;
                            }
                          } catch (err) {
                            console.error("Billing error:", err);
                          }
                        }}
                        className={`w-full text-xs font-semibold py-2 rounded-lg transition-all cursor-pointer ${
                          plan.ctaDisabled
                            ? "bg-[#f3f0eb] text-[#7a7a7a] cursor-not-allowed"
                            : "glow-btn-accent text-white"
                        }`}
                      >
                        {plan.cta}
                      </button>
                    </motion.div>
                  ))}
                </div>

                <div className="notebook-page p-5">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a] mb-3">What's included on all plans</p>
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      ["✦", "AI brand intelligence extraction"],
                      ["✦", "Compliance-first email verification"],
                      ["✦", "YouTube & multi-adapter discovery"],
                      ["✦", "Evidence-backed creator scoring"],
                      ["✦", "Outreach draft generation"],
                      ["✦", "GDPR/CAN-SPAM compliant pipeline"],
                    ].map(([icon, text]) => (
                      <div key={text} className="flex items-start gap-2 text-xs text-[#7a7a7a]">
                        <span className="text-accent shrink-0 font-bold">{icon}</span>
                        <span>{text}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}

            {/* ── Tab: Export ── */}
            {activeTab === "export" && (
              <motion.div className="max-w-2xl mx-auto" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
                <div className="mb-8">
                  <h2 className="text-xl font-semibold text-ink tracking-tight">Export Data</h2>
                </div>

                <div className="notebook-page p-6">
                  <div className="grid grid-cols-2 gap-4 mb-6 text-xs border-b border-[#e8e4df] pb-6">
                    {[
                      ["Campaign", campaign.brief.brand_name || "—"],
                      ["Goal", campaign.goal],
                      ["Records", String(creators.length)],
                    ].map(([label, val]) => (
                      <div key={label}>
                        <p className="text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a] mb-1">{label}</p>
                        <p className="font-semibold text-ink font-mono">{val}</p>
                      </div>
                    ))}
                  </div>

                  <button
                    id="export-csv-btn"
                    onClick={onExport}
                    disabled={creators.length === 0 || isExporting}
                    className="glow-btn w-full rounded-xl py-3 text-sm font-semibold cursor-pointer disabled:opacity-50"
                  >
                    {isExporting ? "Creating export..." : "Create CSV Export"}
                  </button>
                </div>
              </motion.div>
            )}

          </div>
        </main>
      </div>
    </div>
  );
}

// ─── Root Component ────────────────────────────────────────────────────────────
export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser>(null);
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [creators, setCreators] = useState<CampaignCreator[]>([]);
  const [apiHealth, setApiHealth] = useState<ApiHealth>("checking");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isFindingCreators, setIsFindingCreators] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isSendingOutreach, setIsSendingOutreach] = useState(false);
  const [outreachConfig, setOutreachConfig] = useState<OutreachConfig | null>(null);
  const [message, setMessage] = useState("");

  const [crawlerLogIdx, setCrawlerLogIdx] = useState(0);
  useEffect(() => {
    if (!isAnalyzing) return;
    const t = setInterval(() => setCrawlerLogIdx((p) => (p + 1) % CRAWLER_LOGS.length), 1200);
    return () => clearInterval(t);
  }, [isAnalyzing]);

  useEffect(() => {
    api.checkHealth()
      .then(() => setApiHealth("online"))
      .catch(() => setApiHealth("offline"));
  }, []);

  useEffect(() => {
    api.getOutreachConfig()
      .then((res) => setOutreachConfig(res.data))
      .catch((err) => {
        console.error("Outreach config check failed:", err);
        setOutreachConfig(null);
      });
  }, []);

  useEffect(() => {
    async function checkUser() {
      try {
        const insforge = getInsForgeClient();
        const { data } = await insforge.auth.getCurrentUser();
        if (data?.user) {
          setUser(data.user);
        }
      } catch (err) {
        console.error("Not authenticated with InsForge:", err);
      }
    }
    if (hasInsForgeConfig) {
      checkUser();
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    const pending = sessionStorage.getItem("cs_pending_campaign");
    if (pending) {
      sessionStorage.removeItem("cs_pending_campaign");
      try {
        const payload = JSON.parse(pending);
        handleLaunch(payload);
      } catch (err) {
        console.error("Failed to parse pending campaign:", err);
      }
    }
  }, [user]);

  useEffect(() => {
    if (!campaign || jobSummaryFor(campaign).pending === 0) return;
    const timer = setInterval(async () => {
      try {
        const refreshed = await api.getCampaign(campaign.id);
        setCampaign(refreshed.data);
      } catch (err) {
        console.error("Campaign refresh failed:", err);
      }
    }, 8000);
    return () => clearInterval(timer);
  }, [campaign]);

  async function handleSignOut() {
    try {
      const insforge = getInsForgeClient();
      await insforge.auth.signOut();
      setUser(null);
    } catch (err) {
      console.error("Sign out failed:", err);
    }
  }

  async function handleLaunch({ brand_url, goal, geo, platforms }: { brand_url: string; goal: string; geo: string; platforms: string[] }) {
    if (!user) {
      sessionStorage.setItem("cs_pending_campaign", JSON.stringify({ brand_url, goal, geo, platforms }));
      router.push("/sign-in");
      return;
    }
    setIsAnalyzing(true);
    setCrawlerLogIdx(0);
    setMessage("");
    try {
      const res = await api.createCampaign({
        brand_url,
        goal,
        geo,
        platforms,
        provider: "youtube",
        discovery_mode: "safe_fanout",
        query_limit: 5,
        per_query_limit: 10,
        max_providers_per_query: 2,
        max_enrichment_urls_per_query: 5,
      });
      setCampaign(res.data.campaign);
      const summary = jobSummaryFor(res.data.campaign);
      setMessage(`Success: queued ${summary.queued} discovery jobs for ${res.data.campaign.brief.brand_name || brand_url}.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Error analyzing brand.");
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function handleFindCreators() {
    if (!campaign) return;
    const summary = jobSummaryFor(campaign);
    if (summary.pending > 0) {
      setMessage(`Wait for ${summary.pending} queued/running discovery jobs before building a fresh shortlist.`);
      return;
    }
    setIsFindingCreators(true);
    setMessage("");
    try {
      const res = await api.buildShortlist(campaign.id, { limit: 30 });
      setCreators(res.data.shortlist);
      const refreshed = await api.getCampaign(campaign.id);
      setCampaign(refreshed.data);
      setMessage(`Shortlisted ${res.data.shortlist.length} creators.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Discovery failed.");
    } finally {
      setIsFindingCreators(false);
    }
  }

  async function handleRefreshCreators() {
    if (!campaign) return;
    try {
      const res = await api.getCampaignCreators(campaign.id);
      setCreators(res.data);
    } catch (err) {
      console.error("Refresh creators failed:", err);
    }
  }

  async function handleStatusChange(id: string, status: string) {
    setCreators((prev) => prev.map((c) => c.creator_id === id ? { ...c, status } : c));
    if (!campaign) return;
    try {
      const updated = await api.updateCampaignCreator(campaign.id, id, { status });
      setCreators((prev) => prev.map((c) => c.creator_id === id ? updated.data : c));
      setMessage("Pipeline saved.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not save pipeline status.");
    }
  }

  function handlePitchChange(id: string, pitch: string) {
    setCreators((prev) => prev.map((c) => c.creator_id === id ? { ...c, recommended_pitch: pitch } : c));
  }

  async function handlePitchSave(id: string, pitch: string) {
    if (!campaign || !creators.length) return;
    try {
      const updated = await api.updateCampaignCreator(campaign.id, id, { recommended_pitch: pitch });
      setCreators((prev) => prev.map((c) => c.creator_id === id ? updated.data : c));
      setMessage("Pitch saved.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not save pitch.");
    }
  }

  function handleNotesChange(id: string, notes: string) {
    setCreators((prev) => prev.map((c) => c.creator_id === id ? { ...c, notes } : c));
  }

  async function handleNotesSave(id: string, notes: string) {
    if (!campaign || !creators.length) return;
    try {
      const updated = await api.updateCampaignCreator(campaign.id, id, { notes });
      setCreators((prev) => prev.map((c) => c.creator_id === id ? updated.data : c));
      setMessage("Notes saved.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not save notes.");
    }
  }

  async function handleExport() {
    if (!campaign || !creators.length) return;
    setIsExporting(true);
    setMessage("");
    try {
      const exported = await api.exportCampaign(campaign.id);
      setMessage(`CSV export saved: ${exported.data.storage_key}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Export failed.");
    } finally {
      setIsExporting(false);
    }
  }

  async function handleSendOutreach(id: string, subject: string, body: string) {
    if (!campaign) return;
    setIsSendingOutreach(true);
    setMessage("");
    try {
      const res = await api.sendOutreach(campaign.id, id, { subject, body });
      const sentMessage = res.data.outreach_message;
      const updatedCreator = res.data.campaign_creator;
      setCreators((prev) => prev.map((creator) => {
        if (creator.creator_id !== id) return creator;
        return {
          ...creator,
          ...updatedCreator,
          creator: updatedCreator.creator ?? creator.creator,
          outreach_messages: [
            sentMessage,
            ...(updatedCreator.outreach_messages ?? creator.outreach_messages ?? []),
          ],
        };
      }));
      setMessage(`AutoSend accepted ${sentMessage.recipient_email || "the recipient"}.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "AutoSend send failed.");
    } finally {
      setIsSendingOutreach(false);
    }
  }

  if (isAnalyzing) {
    return (
      <div className="min-h-screen bg-[#faf9f6] grid place-items-center px-6">
        <motion.div
          className="w-full max-w-sm notebook-page p-8"
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4 }}
        >
          <div className="flex items-center gap-3 mb-5 border-b border-[#e8e4df] pb-4">
            <span className="w-3 h-3 rounded-full bg-accent animate-pulse-ring" />
            <span className="text-sm font-semibold text-ink">Analyzing your brand</span>
          </div>
          <div className="font-mono text-xs space-y-2.5">
            {CRAWLER_LOGS.map((log, i) => {
              const done = i < crawlerLogIdx;
              const active = i === crawlerLogIdx;
              return (
                <motion.div
                  key={i}
                  className={`flex items-center gap-2 ${done ? "text-[#b5afa6]" : active ? "text-ink" : "text-[#d4cfc8]"}`}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.15 }}
                >
                  <span>{done ? "✓" : active ? "▸" : "○"}</span>
                  <span>{log}</span>
                  {active && <span className="w-1.5 h-3 bg-accent inline-block animate-pulse rounded-sm" />}
                </motion.div>
              );
            })}
          </div>
        </motion.div>
      </div>
    );
  }

  if (campaign) {
    return (
      <Workspace
        campaign={campaign}
        creators={creators}
        onReset={() => { setCampaign(null); setCreators([]); setMessage(""); }}
        onFindCreators={handleFindCreators}
        onRefreshCreators={handleRefreshCreators}
        onStatusChange={handleStatusChange}
        onPitchChange={handlePitchChange}
        onPitchSave={handlePitchSave}
        onNotesChange={handleNotesChange}
        onNotesSave={handleNotesSave}
        onExport={handleExport}
        onSendOutreach={handleSendOutreach}
        isFindingCreators={isFindingCreators}
        isExporting={isExporting}
        isSendingOutreach={isSendingOutreach}
        outreachConfig={outreachConfig}
        message={message}
        onDismissMessage={() => setMessage("")}
      />
    );
  }

  return (
    <>
      <Navbar
        onGetStarted={() => document.getElementById("try-form")?.scrollIntoView({ behavior: "smooth" })}
        user={user}
        onSignOut={handleSignOut}
      />
      <LandingPage onLaunch={handleLaunch} apiHealth={apiHealth} />
    </>
  );
}
