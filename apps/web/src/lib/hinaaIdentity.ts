export const HINAA_DEV_USER = "local-dev-user";

/** Identity headers every browser request must carry. */
export function hinaaIdentityHeaders(): Record<string, string> {
  return { "X-HINAA-Dev-User": HINAA_DEV_USER };
}
