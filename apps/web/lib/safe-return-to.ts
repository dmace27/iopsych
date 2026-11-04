/** Exact internal page shapes; never carry query strings, fragments or bearer URLs. */
const uuid =
  "[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}";
const internalPath = new RegExp(
  `^(?:/roles(?:/${uuid}(?:/(?:reports|invites))?)?|/reports/${uuid}|/privacy)$`,
  "i",
);

export function isInternalAccountPath(value: string): boolean {
  return internalPath.exec(value)?.[0] === value;
}

export function safeReturnTo(value: unknown): string {
  return typeof value === "string" && isInternalAccountPath(value)
    ? value
    : "/roles";
}

export function signInHref(pathname: string): string {
  return `/sign-in?returnTo=${encodeURIComponent(safeReturnTo(pathname))}`;
}
