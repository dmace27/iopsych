import type { RoleProfileStatus, RoleStatus } from "../../lib/contracts";

const LABELS: Record<RoleStatus | RoleProfileStatus, string> = {
  active: "Active",
  approved: "Approved",
  archived: "Archived",
  draft: "Draft",
  superseded: "Superseded",
};

const STYLES: Record<RoleStatus | RoleProfileStatus, string> = {
  active: "bg-emerald-50 text-emerald-800",
  approved: "bg-emerald-50 text-emerald-800",
  archived: "border-slate-200 bg-slate-100 text-slate-600",
  draft: "border-amber-200 bg-amber-50 text-amber-800",
  superseded: "border-slate-200 bg-slate-100 text-slate-600",
};

/** Render status with text and shape, never color alone. */
export function StatusBadge({
  status,
}: {
  status: RoleStatus | RoleProfileStatus;
}) {
  return (
    <span className={`status-badge ${STYLES[status]}`}>
      <span className="status-dot" aria-hidden="true" />
      {LABELS[status]}
    </span>
  );
}

/** Return the user-facing label for tests and non-visual announcements. */
export function statusLabel(status: RoleStatus | RoleProfileStatus): string {
  return LABELS[status];
}
