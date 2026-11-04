# UI inspiration for IOPsych

Research notes · November 4, 2026

## Direction

Make the internal product feel like a focused professional workspace: compact, legible, and quiet, with decisions and evidence at the center. Make the candidate experience feel more like a clear, considerate form than a recruiting dashboard. The product handles sensitive assessments, so visual restraint and clear explanations matter more than decoration or a fashionable dark theme.

The strongest starting combination is **Attio's record organization + Ashby's recruiting context + Formbricks' respondent flow**. Use Linear for interaction polish, not as a visual skin.

### What prompted this direction

A source review of the current UI—not a full visual or usability audit—shows a warm canvas with a radial teal glow, large bold page titles, uppercase tracked labels, rounded panels, and prominent teal buttons. For example, see `apps/web/app/globals.css` and `apps/web/app/roles/roles-workspace.tsx`. These choices are individually reasonable, but repeated together they can make routine work feel like a sequence of promotional cards. The role list, role profile, reports, and candidate assessment would benefit from more distinct layouts suited to their jobs.

## Product references

| Reference | Inspect | What to take into IOPsych | Watch out for |
| --- | --- | --- | --- |
| **Attio** | [Record pages and views](https://attio.com/help/reference/attio-101/attios-data-model/understanding-records) · [Creating and viewing records](https://attio.com/help/reference/managing-your-data/records/create-and-view-records) | A list-to-record model: scannable rows with status and metadata, followed by a consistent detail page with attributes and activity. Consider it for roles and reports; use a preview only if it preserves context and keyboard access. | CRM flexibility and dense customization are not goals for the pilot. Keep the number of views and controls small. |
| **Ashby** | [Candidate profile guide](https://docs.ashbyhq.com/candidate-profile) | Group a person's identity, relevant actions, and contextual information predictably. For reports, keep the candidate/role identity and review state visible while separating evidence from interpretation. | This is a recruiting reference, not permission to expose extra candidate information or copy an ATS pipeline. Keep existing privacy boundaries. |
| **Linear** | [Product](https://linear.app/) · [Design details](https://linear.app/now) | Study compact navigation, precise typography, row alignment, subtle dividers, and fast interaction feedback. Apply the discipline to internal workspaces and states. | Do not import its dark, developer-tool aesthetic by default. Assessment content needs warmth, readability, and space. |
| **GOV.UK Design System** | [Forms](https://design-system.service.gov.uk/patterns/) · [Error summary](https://design-system.service.gov.uk/components/error-summary/) | Clear labels, useful errors, explicit consequences, and predictable progression are valuable for consent, privacy requests, and assessments. Place guidance next to the decision it explains. | The public-service visual identity is not a ready-made brand; adapt the patterns to this product. |
| **Typeform** | [Question types](https://www.typeform.com/help/a/question-types-360029573471/) · [Form design guidance](https://www.typeform.com/help/a/design-your-typeform-360029573651/) | Look at pacing and the visual focus of a question. Candidate assessment screens should make the current question and available responses immediately obvious. | One-question-at-a-time is a hypothesis, not automatically better: test it against review, navigation, and accessibility needs. |
| **USWDS** | [Form templates](https://designsystem.digital.gov/templates/form-templates/) · [Accessibility guidance](https://designsystem.digital.gov/documentation/accessibility/) | A practical reference for long forms, validation, and inclusive interactions. Useful alongside the candidate flow and administrative privacy actions. | Treat the system as a source of tested patterns, not a replacement for testing this app. |

## Open-source references

These are useful for studying real implementations and interaction patterns. Check each repository's current license and the specific files before reusing code or assets.

| Repository | Inspect | Why it is relevant |
| --- | --- | --- |
| [Twenty](https://github.com/twentyhq/twenty) | Record lists, detail views, navigation, filtering | A full CRM with information-rich records; useful for list density and progressive disclosure in internal workspaces. |
| [Formbricks](https://github.com/formbricks/formbricks) | Survey authoring and respondent experience | Closest open-source reference for assessment questions, response controls, progress, and completion states. |
| [OpenATS](https://github.com/adamperlis/openats) | Candidate records, structured feedback, role workflows | Domain reference for the relationship between roles, candidates, and review. AGPL-3.0 is stated in the repository; review its terms before copying code. |
| [Cal.com / Cal.diy](https://github.com/calcom/cal.diy) | Public booking flow and settings forms | Useful contrast between a focused external flow and a denser authenticated workspace. |
| [shadcn/ui blocks](https://ui.shadcn.com/blocks) | Sidebar, login, dashboard and data-table examples; preview and source are linked together | Useful implementation vocabulary for Next.js/React. Customize hierarchy and copy around actual tasks rather than adopting a generic dashboard unchanged. |
| [Tabler](https://github.com/tabler/tabler) | [Live demo](https://preview.tabler.io/) · tables, forms and empty states | A broad catalog for comparing practical admin patterns and edge states; its Bootstrap implementation is a reference, not a proposed stack change. |

## Apply this to the existing screens

1. **Roles list:** replace repeated large cards with a compact, accessible list or table when there are multiple roles. Give title, department/location, approval status, and last update a stable hierarchy. Keep “Create role” prominent, but reduce introductory copy once the workspace is understood. Start with Attio and Twenty.
2. **Role profile and approval:** use a clear page title and status, then separate editable role requirements, evidence, and the approval action. Keep the reason for approval and the consequences close to the action. Use restrained section dividers before adding another bordered container. Start with Ashby and GOV.UK.
3. **Reports:** establish a reading order: identity and role, review status, summary, supporting evidence, limitations, then next action. Make evidence and interpretation distinguishable in words and structure, not color alone. Do not turn assessment results into a decorative score dashboard.
4. **Candidate assessment:** give the candidate a narrow, readable column, clear progress and time expectations where accurate, obvious selected states, and a way to revisit answers when supported. Explain consent and privacy in plain language at the point of choice. Start with Formbricks and GOV.UK.
5. **Accounts and privacy:** favor plain tables, clear labels, explicit status, and direct confirmation of consequential actions. Design empty, loading, error, permission-denied, and success states as part of the flow.

## Design rules to try

- Use one restrained neutral canvas and one primary accent; reserve semantic colors for meaningful status. Remove ambient gradients if they do not help orientation.
- Use typography and spacing as the main hierarchy. Reduce the repeated uppercase eyebrow labels, oversized headers, heavy weights, large corner radii, and nested cards.
- Make data-dense pages denser through aligned rows and consistent metadata, while keeping form controls comfortably sized and readable.
- Give each page one clear primary action; place secondary actions close to the object they affect.
- Keep status understandable as text, and make focus, errors, progress, and save/approval feedback explicit.
- Test at narrow widths and with keyboard navigation, zoom, reduced motion, and representative long content. Maintain the current privacy, consent, and human-review requirements.

## Suggested first design pass

Redesign the **roles list and one role detail page together**. They exercise navigation, list density, status, forms, and approval without requiring an entirely new product vocabulary. Compare desktop and mobile mockups against real empty, populated, loading, and error states; then carry the resulting tokens and interaction rules to reports. Treat the candidate assessment as a separate, quieter surface that shares the same underlying type and controls.

## Further browsing

- [SaaS UI](https://www.saasui.design/) and [SaaSFrame](https://www.saasframe.io/) collect product screens by pattern. Useful for finding additional list, form, and settings examples; verify each pattern in its original product before relying on it.
- [shadcn/ui blocks](https://ui.shadcn.com/blocks) pairs previews with implementation for quick comparison of layout choices.

These links are starting points for design study, not endorsements of each product's assessment practices. Product screens and repositories change; the recommendations above are design hypotheses to validate with this app's users.
