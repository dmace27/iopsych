export default function CandidateInviteLoading() {
  return (
    <main
      aria-busy="true"
      aria-label="Loading candidate assessment"
      className="mx-auto max-w-4xl px-5 py-12 sm:px-8"
      id="main-content"
    >
      <div className="skeleton-shimmer h-5 w-36 rounded" />
      <div className="skeleton-shimmer mt-5 h-12 max-w-xl rounded" />
      <div className="skeleton-shimmer mt-8 h-72 rounded-3xl" />
      <span className="sr-only">Loading candidate assessment…</span>
    </main>
  );
}
