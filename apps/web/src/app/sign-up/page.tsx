"use client";

import Link from "next/link";
import { useState } from "react";
import type { FormEvent } from "react";
import { getInsForgeClient, hasInsForgeConfig } from "@/lib/insforge";

export default function SignUpPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [isSuccess, setIsSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setMessage("");
    setIsSuccess(false);

    try {
      const insforge = getInsForgeClient();
      const { data, error } = await insforge.auth.signUp({
        email,
        password,
        name,
        redirectTo: `${window.location.origin}/sign-in`,
      });
      if (error) throw error;
      setIsSuccess(true);
      setMessage(
        data?.requireEmailVerification
          ? "Account created! Check your inbox to verify your email before signing in."
          : "Account created. You can now sign in to your workspace."
      );
    } catch (error) {
      setIsSuccess(false);
      setMessage(error instanceof Error ? error.message : "Sign up failed.");
    } finally {
      setIsSubmitting(false);
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
          <h1 className="mt-2 text-2xl font-medium tracking-tight text-white">Sign up</h1>
          <p className="mt-1 text-sm text-muted font-normal">
            Start discovering brand–creator matches
          </p>
        </div>

        {/* Main Card */}
        <div className="glass-card p-6">
          {!hasInsForgeConfig && (
            <div className="mb-6 rounded border border-warning/50 bg-warning/10 px-4 py-3 text-xs font-mono text-warning">
              [!] Missing InsForge env vars
            </div>
          )}

          {isSuccess ? (
            <div className="py-6 text-center animate-fade-in-up">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full border border-[#333] bg-[#111] mb-4">
                <span className="text-white">✓</span>
              </div>
              <h2 className="text-lg font-medium text-white mb-2">Success</h2>
              <p className="text-muted text-xs leading-relaxed font-mono">{message}</p>
              <Link
                className="mt-6 inline-block w-full glow-btn rounded px-4 py-2 text-sm font-medium text-black"
                href="/sign-in"
              >
                Go to Sign In
              </Link>
            </div>
          ) : (
            <form className="grid gap-4" onSubmit={handleSubmit}>
              <AuthField label="Full name">
                <input
                  className="glass-input focus-ring w-full px-3 py-2 text-sm font-mono"
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Jane Doe"
                  required
                  type="text"
                  value={name}
                />
              </AuthField>

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
                  minLength={8}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Min. 8 characters"
                  required
                  type="password"
                  value={password}
                />
                {password.length > 0 && password.length < 8 && (
                  <span className="text-[10px] text-danger font-medium mt-1">
                    Password must be at least 8 characters
                  </span>
                )}
              </AuthField>

              <button
                className="glow-btn focus-ring w-full rounded py-2.5 text-sm font-medium text-black mt-2 cursor-pointer disabled:opacity-50"
                disabled={!hasInsForgeConfig || isSubmitting}
                type="submit"
              >
                {isSubmitting ? "Creating account..." : "Sign up"}
              </button>

              {message && !isSuccess && (
                <div className="mt-2 rounded border border-[#333] bg-[#111] px-4 py-3 text-xs font-mono text-white animate-fade-in-up">
                  {message}
                </div>
              )}
            </form>
          )}
        </div>

        {/* Footer link */}
        <p className="mt-6 text-center text-xs text-muted">
          Already have an account?{" "}
          <Link className="font-medium text-white hover:underline transition-colors" href="/sign-in">
            Log in
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
