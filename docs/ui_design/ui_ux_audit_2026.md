# FSD-XAI UI/UX audit and improvement record

## Scope and standard

This review covers the login, Home, Analyze, History, XAI Comparison,
Methodology, and User Management screens supplied on 17 September 2026. The
implementation targets the practical parts of **WCAG 2.2 Level AA** that are
within a Streamlit interface: perceivable contrast, visible keyboard focus,
labelled controls, status that is not colour-only, predictable navigation, and
clear error prevention. It is not a formal accessibility conformance claim.

- [WCAG 2 overview](https://www.w3.org/WAI/standards-guidelines/wcag/)
- [WCAG 2.2 contrast minimum (SC 1.4.3)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
- [WCAG 2.2 focus visible (SC 2.4.7)](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html)

## Issues identified and corrections

| Area | Observed issue | Correction delivered |
| --- | --- | --- |
| Navigation | Narrow fractional columns caused `Compare` to wrap; the active state and product identity were weak. | Replaced with a named, responsive pill navigation group, product mark, signed-in identity, and a separate sign-out action. |
| Page layout | Large blank regions and a fixed bottom status bar made pages look unfinished and could cover actions. | Reduced top padding, constrained readable content width, added a structured home hero, and moved operational status into normal page flow. |
| Visual hierarchy | Links and primary actions looked similar; page titles and supporting text had low visual contrast. | Added a clear primary-action treatment, higher-contrast secondary text, a consistent type/spacing scale, and 44px minimum control targets. |
| Keyboard access | Only some buttons exposed a focus ring. | Added high-visibility focus treatment to buttons, inputs, selects, text areas, tabs, and file-upload controls. |
| Login | The square mark did not communicate identity; recovery guidance was easy to miss. | Added a recognisable product mark, task-focused title, field help, and a concise lost-access route. |
| Analyze | The source-to-result workflow was unclear, field labels were visually hidden, and generic uploader text claimed a different limit from the app. | Added three explicit steps, visible labels, readiness guidance, accurate 10 MB/50 MB instructions, and server-side 50 MB hard cap for archives. |
| History | “Clear All” only cleared browser-session entries but appeared to delete persistent case records. Filters had no visible labels. | Removed the misleading destructive action, added labelled filters and reset, a result count, a no-match state, and a single explicit “Open analysis” action. |
| Empty states | Blank Comparison/History pages offered only an icon and terse text. | Added an explanatory state heading, context, and a direct next action where navigation is appropriate. |
| User management | Account disablement had no confirmation. | Added two-step disable confirmation and cancel path; the current administrator and last active administrator remain protected. |
| Model governance | Any examiner could switch the model from the methodology page. | Moved model configuration to the super-administrator Settings page; Methodology is now explanatory and includes a research-use warning. |
| Result interpretation | The gauge showed an evaluation-only EER threshold as a second case decision; XAI wording overstated certainty. | The result gauge now presents one deployed threshold and an uncertainty band. XAI guidance now describes supporting evidence and requires examiner review. |

## Manual acceptance checks before submission or deployment

1. Use `Tab`, `Shift+Tab`, `Enter`, and `Space` on every login, navigation,
   form, filter, download, and account-management control. The focused control
   must be visible and usable without a mouse.
2. Test at 320px, 768px, 1366px, and 1920px widths. Navigation must not wrap
   individual page labels; key actions must remain visible without a fixed
   footer covering them.
3. Check the single-image uploader rejects a file over 10 MB and the batch
   uploader rejects an archive over 50 MB; the instruction and error must
   agree.
4. Filter History to zero matches, reset filters, and reopen both a single and
   a batch case. Confirm no saved database record is removed by a UI action.
5. As a super administrator, try disabling an examiner and cancel once; then
   confirm. Verify that a user cannot disable themself or the final active
   super administrator.
6. Run an analysis near the configured threshold and verify the interface
   shows the result as decision support, not as an automatic forensic
   conclusion.
