# Phase 7 — Integration + End-to-End QA

## Goal
Prove the whole workflow is correct, then fix what's broken before packaging.

## Correctness checks (verify against the raw cached data)
- [ ] For three random intervals (one in early January with December publications), recompute by hand from the raw data: eligible versions, selected publish time, forecast value, and actual value. They must match the UI.
- [ ] No selected publish time is later than its cutoff. Add an assertion test that scans the whole month.
- [ ] The UI's MAE, RMSE, MBE, and WAPE equal a pandas recomputation in a script.
- [ ] Coverage numerator and denominator are correct for a single day (48 intervals; 46 or 50 on DST days, documented even though they fall outside January).
- [ ] Timestamps display in Europe/London with labels. The UTC tooltip is correct.

## UX checks
- [ ] Loading, empty, and error states for every widget (stop the backend; choose a range with no data)
- [ ] Filters reset correctly. The URL state restores on reload.
- [ ] Responsive at 1440, 1280, 1024, and 768 px
- [ ] Keyboard navigation works for filters and the table. Focus is visible.
- [ ] No console errors or warnings. No unhandled promise rejections.

## Performance
- [ ] A full-month query responds in under 2 s on a warm cache. Report the timings.
- [ ] The chart stays responsive with about 1,488 points.

## Deliverable
`docs/qa-report.md` listing each check, its result, evidence, and any fixes made.

Stop and report.
