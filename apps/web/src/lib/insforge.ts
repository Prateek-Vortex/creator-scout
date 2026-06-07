import { createClient } from "@insforge/sdk";

const insforgeUrl = process.env.NEXT_PUBLIC_INSFORGE_URL;
const insforgeAnonKey = process.env.NEXT_PUBLIC_INSFORGE_ANON_KEY;

export const hasInsForgeConfig = Boolean(insforgeUrl && insforgeAnonKey);

let browserClient: ReturnType<typeof createClient> | null = null;

export function getInsForgeClient() {
  if (!hasInsForgeConfig) {
    throw new Error(
      "Missing NEXT_PUBLIC_INSFORGE_URL or NEXT_PUBLIC_INSFORGE_ANON_KEY"
    );
  }

  if (!browserClient) {
    browserClient = createClient({
      baseUrl: insforgeUrl!,
      anonKey: insforgeAnonKey!,
    });
  }

  return browserClient;
}
