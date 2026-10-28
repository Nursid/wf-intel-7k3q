# Phase 0 — Prerequisites (done by you, not Claude)

Finish this checklist before Phase 1. Items marked 🔑 need your own login, card, or decision.

## Local tools
- [ ] Git installed (`git --version`)
- [ ] Python 3.11+ (`python --version`)
- [ ] Node.js 20 LTS + npm (`node -v`)
- [ ] Docker Desktop running (`docker compose version`)
- [ ] GitHub CLI logged in 🔑 (`gh auth login`, then `gh auth status`)
- [ ] Vercel CLI logged in 🔑 (`npm i -g vercel`, then `vercel login`)
- [ ] Backend host CLI logged in 🔑. For Heroku: `heroku login`

## Accounts and decisions
- [ ] 🔑 **GitHub account.** Choose a random, anonymous repo name (e.g. `wf-intel-7k3q`). Don't use your name or company.
- [ ] 🔑 **Vercel account.** The free Hobby plan is enough.
- [ ] 🔑 **Backend hosting.** Heroku has had no free tier since Nov 2022 and needs a verified card plus a paid Eco/Basic dyno (about $5–7/month). Pick one:
  - Heroku (paid, as the brief specifies), or
  - Render, Railway, or Fly.io (free or cheap tiers; cold starts possible). Using one is a documented deviation from the brief.
- [ ] 🔑 **Default decision cutoff.** The brief deliberately leaves this open. Pick a pilot default such as *D-1 at 09:00 Europe/London*. It stays user-configurable and is documented as an assumption.
- [ ] 🔑 **YouTube account** for the unlisted demo video. You record it yourself (screen recorder, e.g. OBS or Loom).
- [ ] 🔑 **Submission form link.** Keep it handy for Phase 10.

## Notes
- The Elexon BMRS Insights API is public and needs no API key. Phase 1 verifies this.
- Fill in the **Decisions** section of `CLAUDE.md` before starting Phase 1.
