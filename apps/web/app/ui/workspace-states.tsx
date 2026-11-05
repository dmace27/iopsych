import type { ReactNode } from "react";

/** Consistent screen-reader-announced loading panel. */
export function LoadingState({ label }: { label: string }) {
  return (
    <div
      aria-live="polite"
      aria-busy="true"
      className="space-y-3"
      role="status"
    >
      <span className="sr-only">{label}</span>
      <div className="skeleton-shimmer h-16 rounded-lg" />
      <div className="skeleton-shimmer h-16 rounded-lg" />
      <div className="skeleton-shimmer h-16 rounded-lg" />
    </div>
  );
}

/** Recoverable error state with an explicit retry action. */
export function ErrorState({
  title,
  message,
  onRetry,
}: {
  title: string;
  message: string;
  onRetry: () => void;
}) {
  return (
    <section
      aria-labelledby="error-state-title"
      className="rounded-lg border border-rose-200 bg-rose-50 p-5"
      role="alert"
    >
      <h2
        className="text-base font-semibold text-rose-950"
        id="error-state-title"
      >
        {title}
      </h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-rose-900">
        {message}
      </p>
      <button
        className="mt-4 min-h-11 rounded-md bg-rose-900 px-4 py-2 text-sm font-medium text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-800 focus-visible:ring-offset-2"
        onClick={onRetry}
        type="button"
      >
        Try again
      </button>
    </section>
  );
}

/** Visually distinct empty state that can contain the next available action. */
export function EmptyState({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center">
      <div
        aria-hidden="true"
        className="mx-auto grid size-12 place-items-center rounded-full bg-teal-50 text-xl text-teal-800"
      >
        ◇
      </div>
      <h2 className="mt-4 text-lg font-medium tracking-tight text-slate-950">
        {title}
      </h2>
      <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-600">
        {description}
      </p>
      {children ? <div className="mt-6">{children}</div> : null}
    </section>
  );
}
