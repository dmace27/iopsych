/** Accept only implemented internal workspace paths, preserving a local query. */
export function safeReturnTo(value: unknown): string {
  if (typeof value !== "string" || value.length > 2048) return "/roles";
  return /^\/(roles|reports|privacy|accounts)(\/[a-zA-Z0-9_-]+)*(\?[^#\\\x00-\x20]*)?$/.test(
    value,
  )
    ? value
    : "/roles";
}
