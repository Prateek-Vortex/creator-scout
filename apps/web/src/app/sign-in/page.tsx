"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { getInsForgeClient, hasInsForgeConfig } from "@/lib/insforge";

export default function SignInPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setMessage("");

    try {
      const insforge = getInsForgeClient();
      const { error } = await insforge.auth.signInWithPassword({ email, password });
      if (error) throw error;
      setMessage("Signed in. Redirecting to home...");
      setTimeout(() => {
        router.push("/");
      }, 1000);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Sign in failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleOAuth(provider: "google" | "github") {
    setMessage("");
    try {
      const insforge = getInsForgeClient();
      const { error } = await insforge.auth.signInWithOAuth({
        provider,
        redirectTo: `${window.location.origin}/`,
      });
      if (error) throw error;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "OAuth sign in failed.");
    }
  }

  return (
    <main className="relative min-h-screen grid place-items-center px-4 py-16 bg-background text-foreground overflow-hidden">
      <div className="absolute inset-0 grid-overlay pointer-events-none" />

      <div className="relative z-10 w-full max-w-sm animate-fade-in-up">
        {/* Logo / Brand Header */}
        <div className="mb-8 text-center">
          <div className="inline-flex items-center justify-center w-10 h-10 rounded bg-white mb-4">
            <span className="text-black font-medium text-sm">CS</span>
          </div>
          <h1 className="mt-2 text-2xl font-medium tracking-tight text-white">Log in</h1>
          <p className="mt-1 text-sm text-muted font-normal">
            Welcome back to Creator Scout
          </p>
        </div>

        {/* Main Card */}
        <div className="glass-card p-6">
          {!hasInsForgeConfig && (
            <div className="mb-6 rounded border border-warning/50 bg-warning/10 px-4 py-3 text-xs font-mono text-warning">
              [!] Missing InsForge env vars
            </div>
          )}

          <form className="grid gap-4" onSubmit={handleSubmit}>
            <AuthField label="Email address">
              <input
                className="glass-input focus-ring w-full px-3 py-2 text-sm font-mono"
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@company.com"
                required
                type="email"
                value={email}
              />
            </AuthField>

            <AuthField label="Password">
              <input
                className="glass-input focus-ring w-full px-3 py-2 text-sm font-mono"
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••"
                required
                type="password"
                value={password}
              />
            </AuthField>

            <button
              className="glow-btn focus-ring w-full rounded py-2.5 text-sm font-medium text-black mt-2 cursor-pointer disabled:opacity-50"
              disabled={!hasInsForgeConfig || isSubmitting}
              type="submit"
            >
              {isSubmitting ? "Authenticating..." : "Continue"}
            </button>
          </form>

          {/* Divider */}
          <div className="flex items-center gap-3 my-6">
            <div className="flex-1 h-px bg-[#333]" />
            <span className="text-[10px] font-mono text-muted uppercase">or</span>
            <div className="flex-1 h-px bg-[#333]" />
          </div>

          {/* OAuth Buttons */}
          <div className="grid grid-cols-2 gap-3">
            <button
              className="flex items-center justify-center gap-2 rounded border border-[#333] bg-[#000] px-4 py-2.5 text-xs font-medium text-white hover:bg-[#111] transition-all cursor-pointer disabled:opacity-50"
              disabled={!hasInsForgeConfig}
              onClick={() => handleOAuth("google")}
              type="button"
            >
              Google
            </button>
            <button
              className="flex items-center justify-center gap-2 rounded border border-[#333] bg-[#000] px-4 py-2.5 text-xs font-medium text-white hover:bg-[#111] transition-all cursor-pointer disabled:opacity-50"
              disabled={!hasInsForgeConfig}
              onClick={() => handleOAuth("github")}
              type="button"
            >
              GitHub
            </button>
          </div>

          {/* Feedback message */}
          {message && (
            <div className="mt-5 rounded border border-[#333] bg-[#111] px-4 py-3 text-xs font-mono text-white animate-fade-in-up">
              {message}
            </div>
          )}
        </div>

        {/* Footer link */}
        <p className="mt-6 text-center text-xs text-muted">
            Don&apos;t have an account?{" "}
          <Link className="font-medium text-white hover:underline transition-colors" href="/sign-up">
            Sign up
          </Link>
        </p>
      </div>
    </main>
  );
}

function AuthField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="grid gap-1.5 text-[11px] font-medium text-muted">
      {label}
      {children}
    </label>
  );
}
