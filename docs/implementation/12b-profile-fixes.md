# 12B profile contrast correction

Scoped follow-up to the browser worker's `c20b3ed` findings, implemented from
child-worktree baseline `360c5dc`. This closes the two identified source-level
contrast defects, not full package 12B acceptance.

## Changes

Changed the editable construct legend counter and readonly construct eyebrow
from `text-slate-400` to existing `text-slate-600`. Each appears six times in a
complete profile. Typography, layout, semantics, role contracts, permissions and
version behavior are unchanged. No dependencies or migrations changed.

Reviewed the other small text in the owned component: identity role, version
timestamps, version-history guidance, rating scale endpoints and evidence-entry
help use `text-slate-500` against white, slate-50 or teal-50. Their current
token pairs exceed 4.5:1, so they were retained.

## Targeted evidence

- `npm exec --workspace @iopsych/web -- vitest run 'app/roles/[roleId]/role-profile-workspace.test.tsx'`:
  **3 passed**, covering draft revision, recruiter extraction and manager
  approval into a frozen readonly version.
- `npm exec --workspace @iopsych/web -- eslint 'app/roles/[roleId]/role-profile-workspace.tsx' --max-warnings=0`:
  passed.
- `git diff --check`: passed before handoff.
- Read the installed Next.js `use-client.md` guide under
  `node_modules/next/dist/docs/01-app/03-api-reference/01-directives/` before
  editing.

Computed WCAG relative-luminance contrast from the installed Tailwind
`node_modules/tailwindcss/theme.css` OKLCH tokens, converting OKLCH to linear
sRGB and using `(lighter + 0.05) / (darker + 0.05)`:

| Foreground                       |  White | Slate-50 | Teal-50 |
| -------------------------------- | -----: | -------: | ------: |
| Slate-400, previous              | 2.63:1 |   2.51:1 |  2.52:1 |
| Slate-500, retained related text | 4.77:1 |   4.55:1 |  4.58:1 |
| Slate-600, corrected labels      | 7.56:1 |   7.23:1 |  7.26:1 |

These are token calculations, not browser-computed style or axe results. No new
class-name assertion tests were added for this two-token style-only change;
existing interaction tests were rerun. Browser test dependencies are not
installed in this child worktree, and no duplicate full browser suite was
started.

## Remaining integration check

Requested the owner of browser dispatch `ctx_6f6fb5f60c61` to rerun editable and
readonly profile axe scans after coordinator integration. That rerun is the next
eligible verification step; manual accessibility and broader package acceptance
remain open. Only synthetic test fixtures were used, no services were launched,
and reserved or existing service ports were untouched.
