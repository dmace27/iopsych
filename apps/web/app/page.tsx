/** Minimal shell used to verify the web application is running. */
export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl items-center px-6 py-16">
      <section aria-labelledby="page-title" className="space-y-4">
        <p className="text-sm font-semibold uppercase tracking-wide text-slate-600">
          IOPsych MVP
        </p>
        <h1 id="page-title" className="text-4xl font-semibold tracking-tight">
          Technical foundation is running.
        </h1>
        <p className="max-w-2xl text-lg leading-8 text-slate-700">
          Product workflows will be added in later implementation packages. This
          build contains only the monorepo and developer tooling foundation.
        </p>
      </section>
    </main>
  );
}
