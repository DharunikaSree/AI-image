const BLOCKED_HOSTNAMES = new Set([
  "demo-store.example.com",
  "example.com",
  "localhost",
  "127.0.0.1",
  "0.0.0.0",
  "test.com",
]);

/**
 * Validates whether a given URL is a genuine, safe external ecommerce/store URL.
 * Rejects placeholder URLs (example.com, demo-store.example.com, localhost),
 * non-HTTP(S) schemes (javascript:, data:, file:), and malformed strings.
 */
export function isGenuineExternalUrl(url?: string | null): boolean {
  if (!url || typeof url !== "string") return false;
  const trimmed = url.trim();
  if (!trimmed) return false;

  // Strict protocol whitelist
  if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
    return false;
  }

  try {
    const parsed = new URL(trimmed);
    const host = parsed.hostname.toLowerCase();

    if (
      BLOCKED_HOSTNAMES.has(host) ||
      host.endsWith(".example.com") ||
      host.endsWith(".local") ||
      !host.includes(".")
    ) {
      return false;
    }

    return true;
  } catch {
    return false;
  }
}
