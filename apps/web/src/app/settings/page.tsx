"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { getInsForgeClient } from "@/lib/insforge";
import { api } from "@/lib/api";
import type { DeveloperKey, CreditStatus } from "@/lib/api";

type SettingsTab = "profile" | "security" | "keys";

// Accent sticker rotations for styling
const STICKER_ROTATIONS = [-1.5, 2, -1, 1.5];

export default function SettingsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<SettingsTab>("profile");
  const [user, setUser] = useState<any>(null);
  const [loadingUser, setLoadingUser] = useState(true);

  // Profile Form States
  const [nameInput, setNameInput] = useState("");
  const [emailInput, setEmailInput] = useState("");
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [profileMessage, setProfileMessage] = useState("");

  // Security Form States
  const [isSendingCode, setIsSendingCode] = useState(false);
  const [codeSent, setCodeSent] = useState(false);
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordMessage, setPasswordMessage] = useState("");
  const [isUpdatingPassword, setIsUpdatingPassword] = useState(false);

  // Developer Keys States
  const [keys, setKeys] = useState<DeveloperKey[]>([]);
  const [credits, setCredits] = useState<CreditStatus | null>(null);
  const [loadingKeys, setLoadingKeys] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [generatedPlainKey, setGeneratedPlainKey] = useState<string | null>(null);
  const [isCreatingKey, setIsCreatingKey] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);

  // Load User and Keys
  useEffect(() => {
    async function loadUser() {
      try {
        const insforge = getInsForgeClient();
        const { data } = await insforge.auth.getCurrentUser();
        if (data?.user) {
          setUser(data.user);
          setNameInput(data.user.profile?.name || "");
          setEmailInput(data.user.email || "");
          loadKeys(data.user.id);
        } else {
          router.push("/sign-in");
        }
      } catch (err) {
        console.error("Failed to load user settings:", err);
        router.push("/sign-in");
      } finally {
        setLoadingUser(false);
      }
    }
    loadUser();
  }, [router]);

  async function loadKeys(userId: string) {
    setLoadingKeys(true);
    try {
      const res = await api.getDeveloperKeys(userId);
      if (res?.data) {
        setKeys(res.data.keys || []);
        setCredits(res.data.credits || null);
      }
    } catch (err) {
      console.error("Failed to load keys:", err);
    } finally {
      setLoadingKeys(false);
    }
  }

  // Profile Save handler
  async function handleProfileSave(e: FormEvent) {
    e.preventDefault();
    if (!user) return;
    setIsSavingProfile(true);
    setProfileMessage("");
    try {
      const res = await api.updateProfile(user.id, nameInput, emailInput);
      if (res?.success) {
        const insforge = getInsForgeClient();
        const { error } = await insforge.auth.setProfile({ name: nameInput });
        if (error) throw error;
        await insforge.auth.refreshSession();
        
        const { data } = await insforge.auth.getCurrentUser();
        if (data?.user) {
          setUser(data.user);
        }
        setProfileMessage("Profile updated successfully!");
      }
    } catch (err: any) {
      setProfileMessage(err?.message || "Failed to update profile.");
    } finally {
      setIsSavingProfile(false);
    }
  }

  // Send Reset Password Code
  async function handleSendResetCode() {
    if (!user?.email) return;
    setIsSendingCode(true);
    setPasswordMessage("");
    try {
      const insforge = getInsForgeClient();
      const { error } = await insforge.auth.sendResetPasswordEmail({ email: user.email });
      if (error) throw error;
      setCodeSent(true);
      setPasswordMessage("Verification code sent to your email!");
    } catch (err: any) {
      setPasswordMessage(err?.message || "Failed to send verification code.");
    } finally {
      setIsSendingCode(false);
    }
  }

  // Reset/Update Password
  async function handleUpdatePassword(e: FormEvent) {
    e.preventDefault();
    if (!otp || !newPassword) return;
    setIsUpdatingPassword(true);
    setPasswordMessage("");
    try {
      const insforge = getInsForgeClient();
      const { error } = await insforge.auth.resetPassword({ newPassword, otp });
      if (error) throw error;
      setPasswordMessage("Password updated successfully!");
      setCodeSent(false);
      setOtp("");
      setNewPassword("");
    } catch (err: any) {
      setPasswordMessage(err?.message || "Failed to update password. Make sure the code is correct.");
    } finally {
      setIsUpdatingPassword(false);
    }
  }

  // Create Developer Key
  async function handleCreateKey(e: FormEvent) {
    e.preventDefault();
    if (!user || !newKeyName.trim()) return;
    setIsCreatingKey(true);
    setGeneratedPlainKey(null);
    try {
      const res = await api.createDeveloperKey(user.id, newKeyName.trim());
      if (res?.data?.plain_key) {
        setGeneratedPlainKey(res.data.plain_key);
        setNewKeyName("");
        loadKeys(user.id);
      }
    } catch (err) {
      console.error("Failed to create key:", err);
    } finally {
      setIsCreatingKey(false);
    }
  }

  // Revoke Developer Key
  async function handleRevokeKey(keyId: string) {
    if (!user) return;
    if (!confirm("Are you sure you want to revoke this API key? This cannot be undone.")) return;
    try {
      await api.revokeDeveloperKey(user.id, keyId);
      loadKeys(user.id);
    } catch (err) {
      console.error("Failed to revoke key:", err);
    }
  }

  function handleCopyKey() {
    if (!generatedPlainKey) return;
    navigator.clipboard.writeText(generatedPlainKey);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  }

  if (loadingUser) {
    return (
      <main className="min-h-screen bg-[#faf9f6] flex items-center justify-center p-6 text-ink">
        <div className="text-center font-semibold text-sm">
          <span className="w-1.5 h-1.5 rounded-full bg-accent inline-block animate-ping mr-2" />
          Loading user settings...
        </div>
      </main>
    );
  }

  return (
    <main className="relative min-h-screen bg-[#faf9f6] text-ink py-16 px-4 md:px-6">
      <div className="absolute inset-0 grid-overlay pointer-events-none" />

      <div className="relative z-10 max-w-4xl mx-auto">
        {/* Navigation & Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded bg-[#1a1a1a] flex items-center justify-center text-[#faf9f6] font-bold text-[10px] shadow-sm">
              CS
            </div>
            <span className="text-sm font-semibold tracking-tight text-ink">Creator Scout</span>
          </div>

          <Link
            href="/"
            className="px-3.5 py-2 rounded-lg border border-[#e8e4df] bg-white text-xs font-semibold text-ink hover:bg-[#f3f0eb] transition cursor-pointer flex items-center gap-1.5"
          >
            ← Back to Scout
          </Link>
        </div>

        {/* Title */}
        <div className="mb-8 relative">
          <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight">
            Settings &amp;{" "}
            <span
              style={{ fontFamily: "var(--font-caveat)" }}
              className="text-accent text-3xl sm:text-4xl"
            >
              Developer Profile
            </span>
          </h1>
          <p className="text-xs text-[#7a7a7a] mt-1.5">
            Configure your workspace access, developer API credentials, and credit limits.
          </p>

          <motion.div
            className="absolute -top-6 right-0 badge-sticker badge-teal text-[9px] select-none pointer-events-none hidden md:inline-flex"
            animate={{ y: [0, -4, 0] }}
            transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
          >
            Settings Workspace
          </motion.div>
        </div>

        {/* Settings Notebook Grid */}
        <div className="grid md:grid-cols-4 gap-6">
          {/* Tabs Sidebar */}
          <div className="md:col-span-1 flex flex-row md:flex-col gap-2 overflow-x-auto pb-2 md:pb-0">
            {(
              [
                { id: "profile", label: "Profile details", color: "badge-coral" },
                { id: "security", label: "Security & auth", color: "badge-lavender" },
                { id: "keys", label: "API Credentials", color: "badge-teal" },
              ] as const
            ).map((t) => {
              const active = activeTab === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => {
                    setActiveTab(t.id);
                    setProfileMessage("");
                    setPasswordMessage("");
                    setGeneratedPlainKey(null);
                  }}
                  className={`px-4 py-2.5 rounded-lg text-left text-xs font-semibold whitespace-nowrap transition-all cursor-pointer w-full flex items-center gap-2 border ${
                    active
                      ? `badge-sticker ${t.color} border-transparent shadow-sm translate-x-0 md:translate-x-1`
                      : "border-transparent text-[#7a7a7a] hover:text-ink hover:bg-[#f3f0eb]"
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${active ? "bg-ink" : "bg-[#b5afa6]"}`} />
                  {t.label}
                </button>
              );
            })}
          </div>

          {/* Form Content Notebook Sheet */}
          <div className="md:col-span-3">
            <div className="notebook-page p-6 md:p-8 min-h-[380px]">
              <AnimatePresence mode="wait">
                {activeTab === "profile" && (
                  <motion.div
                    key="profile"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -12 }}
                    transition={{ duration: 0.3 }}
                  >
                    <h2 className="text-base font-semibold text-ink mb-4">Profile Details</h2>
                    <form onSubmit={handleProfileSave} className="grid gap-5">
                      <label className="grid gap-2 text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a]">
                        Full Name
                        <input
                          type="text"
                          required
                          value={nameInput}
                          onChange={(e) => setNameInput(e.target.value)}
                          placeholder="Jane Doe"
                          className="glass-input focus-ring w-full px-4 py-3 text-sm font-mono"
                        />
                      </label>

                      <label className="grid gap-2 text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a]">
                        Email Address
                        <input
                          type="email"
                          required
                          value={emailInput}
                          onChange={(e) => setEmailInput(e.target.value)}
                          placeholder="jane@example.com"
                          className="glass-input focus-ring w-full px-4 py-3 text-sm font-mono"
                        />
                      </label>

                      <div className="flex items-center gap-4 mt-2">
                        <button
                          type="submit"
                          disabled={isSavingProfile}
                          className="glow-btn-accent px-5 py-3 text-xs font-semibold cursor-pointer rounded-xl disabled:opacity-50"
                        >
                          {isSavingProfile ? "Saving..." : "Save changes"}
                        </button>

                        {profileMessage && (
                          <span className={`text-xs font-medium ${profileMessage.includes("successful") ? "text-success" : "text-danger"}`}>
                            {profileMessage}
                          </span>
                        )}
                      </div>
                    </form>
                  </motion.div>
                )}

                {activeTab === "security" && (
                  <motion.div
                    key="security"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -12 }}
                    transition={{ duration: 0.3 }}
                  >
                    <h2 className="text-base font-semibold text-ink mb-2">Security &amp; Password</h2>
                    <p className="text-xs text-[#7a7a7a] mb-5">
                      Change your password via verification code verification. A code will be sent to <strong>{user?.email}</strong>.
                    </p>

                    {!codeSent ? (
                      <div className="grid gap-4 max-w-sm">
                        <button
                          type="button"
                          onClick={handleSendResetCode}
                          disabled={isSendingCode}
                          className="glow-btn px-5 py-3 text-xs font-semibold cursor-pointer rounded-xl disabled:opacity-50 text-center"
                        >
                          {isSendingCode ? "Sending code..." : "Send Verification Code"}
                        </button>
                        {passwordMessage && (
                          <span className={`text-xs font-medium ${passwordMessage.includes("sent") ? "text-[#1e7a72]" : "text-danger"}`}>
                            {passwordMessage}
                          </span>
                        )}
                      </div>
                    ) : (
                      <form onSubmit={handleUpdatePassword} className="grid gap-5">
                        <label className="grid gap-2 text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a]">
                          Verification Code
                          <input
                            type="text"
                            required
                            maxLength={6}
                            value={otp}
                            onChange={(e) => setOtp(e.target.value)}
                            placeholder="123456"
                            className="glass-input focus-ring w-full px-4 py-3 text-sm font-mono tracking-widest text-center"
                          />
                        </label>

                        <label className="grid gap-2 text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a]">
                          New Password
                          <input
                            type="password"
                            required
                            minLength={8}
                            value={newPassword}
                            onChange={(e) => setNewPassword(e.target.value)}
                            placeholder="Min. 8 characters"
                            className="glass-input focus-ring w-full px-4 py-3 text-sm font-mono"
                          />
                        </label>

                        <div className="flex items-center gap-4 mt-2">
                          <button
                            type="submit"
                            disabled={isUpdatingPassword}
                            className="glow-btn-accent px-5 py-3 text-xs font-semibold cursor-pointer rounded-xl disabled:opacity-50"
                          >
                            {isUpdatingPassword ? "Updating..." : "Update Password"}
                          </button>

                          <button
                            type="button"
                            onClick={() => {
                              setCodeSent(false);
                              setPasswordMessage("");
                            }}
                            className="text-xs text-[#7a7a7a] hover:text-ink transition underline cursor-pointer"
                          >
                            Cancel
                          </button>
                        </div>

                        {passwordMessage && (
                          <div className={`mt-2 text-xs font-medium ${passwordMessage.includes("updated") ? "text-success" : "text-danger"}`}>
                            {passwordMessage}
                          </div>
                        )}
                      </form>
                    )}
                  </motion.div>
                )}

                {activeTab === "keys" && (
                  <motion.div
                    key="keys"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -12 }}
                    transition={{ duration: 0.3 }}
                    className="grid gap-6"
                  >
                    {/* Monthly Credits Usage panel */}
                    {credits && (
                      <div className="rounded-xl border border-[#e8e4df] bg-[#f8f6f2] p-5">
                        <div className="flex justify-between items-center mb-3">
                          <p className="text-[10px] font-bold uppercase tracking-widest text-[#7a7a7a]">
                            Monthly Credits Usage
                          </p>
                          <span className="badge-sticker badge-amber text-[9px]">
                            {credits.remaining.toFixed(1)} remaining
                          </span>
                        </div>

                        <div className="w-full bg-[#e8e4df] h-2.5 rounded-full overflow-hidden">
                          <div
                            className="bg-accent h-full transition-all duration-500"
                            style={{
                              width: `${Math.min(100, (credits.used / credits.limit) * 100)}%`,
                            }}
                          />
                        </div>

                        <div className="flex justify-between items-center mt-2.5 text-[10px] font-mono text-[#7a7a7a]">
                          <span>{credits.used.toFixed(1)} used</span>
                          <span>Limit: {credits.limit.toFixed(1)} credits</span>
                        </div>
                      </div>
                    )}

                    {/* Developer Key Generator */}
                    <div>
                      <h2 className="text-sm font-semibold text-ink mb-3.5">
                        Generate New API Key
                      </h2>

                      {generatedPlainKey ? (
                        <div className="p-4 rounded-xl border border-[#f5c4ba] bg-[#fde8e4] text-[#c4402d] mb-4">
                          <p className="text-[10px] font-bold uppercase tracking-widest mb-1.5">
                            New Key Generated (Save This Now!)
                          </p>
                          <p className="text-xs font-mono leading-relaxed mb-3 break-all select-all p-2 bg-white rounded border border-[#f5c4ba]/50 text-ink">
                            {generatedPlainKey}
                          </p>
                          <div className="flex items-center gap-3">
                            <button
                              onClick={handleCopyKey}
                              type="button"
                              className="px-3.5 py-1.5 rounded-lg bg-white border border-[#f5c4ba] text-[11px] font-semibold text-ink hover:bg-[#faf9f6] transition cursor-pointer flex items-center gap-1.5"
                            >
                              {copiedKey ? "Copied! ✓" : "Copy to Clipboard"}
                            </button>
                            <button
                              onClick={() => setGeneratedPlainKey(null)}
                              type="button"
                              className="text-[10px] text-[#c4402d] hover:underline font-semibold cursor-pointer"
                            >
                              I have saved it, dismiss
                            </button>
                          </div>
                        </div>
                      ) : (
                        <form onSubmit={handleCreateKey} className="flex gap-3 max-w-md">
                          <input
                            type="text"
                            required
                            placeholder="e.g. Production Key, Staging"
                            value={newKeyName}
                            onChange={(e) => setNewKeyName(e.target.value)}
                            className="glass-input focus-ring flex-1 px-4 py-2 text-xs font-mono"
                          />
                          <button
                            type="submit"
                            disabled={isCreatingKey}
                            className="glow-btn px-4 py-2 text-xs font-semibold cursor-pointer rounded-xl shrink-0 disabled:opacity-50"
                          >
                            {isCreatingKey ? "Generating..." : "Generate Key"}
                          </button>
                        </form>
                      )}
                    </div>

                    {/* Keys list */}
                    <div>
                      <h2 className="text-sm font-semibold text-ink mb-3.5">
                        Active API Keys
                      </h2>

                      {loadingKeys ? (
                        <div className="text-xs text-[#7a7a7a] font-mono">Loading active keys...</div>
                      ) : keys.length === 0 ? (
                        <div className="text-xs text-[#7a7a7a] font-mono p-4 border border-dashed border-[#e8e4df] rounded-xl text-center bg-[#faf9f6]">
                          No active developer API keys found.
                        </div>
                      ) : (
                        <div className="grid gap-3.5">
                          {keys.map((k) => (
                            <div
                              key={k.id}
                              className="flex items-center justify-between p-4 rounded-xl border border-[#e8e4df] bg-white hover:border-[#d4cfc8] transition"
                            >
                              <div className="grid gap-1 truncate mr-4">
                                <p className="text-xs font-semibold text-ink truncate">{k.name}</p>
                                <div className="flex flex-wrap gap-1.5 items-center mt-1">
                                  <span className="badge-sticker badge-teal text-[8px] font-mono select-none">
                                    {k.scopes.join(", ")}
                                  </span>
                                  <span className="text-[9px] font-mono text-[#b5afa6]">
                                    ID: {k.id.slice(0, 8)}...
                                  </span>
                                  <span className="text-[9px] font-mono text-[#b5afa6]">
                                    Created: {new Date(k.created_at).toLocaleDateString()}
                                  </span>
                                </div>
                              </div>

                              <button
                                onClick={() => handleRevokeKey(k.id)}
                                type="button"
                                className="px-2.5 py-1.5 text-[10px] font-semibold text-danger bg-danger/5 border border-danger/20 hover:bg-danger hover:text-white transition rounded-lg cursor-pointer shrink-0"
                              >
                                Revoke
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
