# WebbGPT Beta Rollout Plan

> Logistics-first plan for validating the product with real users before deciding whether to pursue school support.

---

## Why Private Beta First

- A 16-question survey sent cold to Webb students will get single-digit responses
- We don't yet have school endorsement, and may not get it
- We need **usage data and word-of-mouth**, not survey statistics
- A private beta builds a user base that becomes leverage for whatever comes next (school pitch, public launch, or just a better product)

---

## Stage 1: Private Beta — Dev Group (Week 1–2)

### Who
- Coding/AI Club members (natural first users who will actually engage)
- Target: 5–10 active testers

### How to distribute
- Share the link directly in group chat — no formal announcement, no survey
- Frame: "I built this, try to break it, tell me what's wrong"

### What to collect
No survey form. Instead:
1. **In-chat feedback** — ask people to drop screenshots of bad answers or share what they tried
2. **Server logs** — track query volume, which questions are being asked, error rates
3. **One question at the end of Week 2** (in the group chat, not a form):
   > "On a scale of 1–5, would you send this link to a non-dev friend? Why or why not?"

### Success criteria to move to Stage 2
- At least 5 people actually used it (not just opened it)
- You've identified and fixed 3+ knowledge gaps or bad answers
- At least one person says they'd share it

### What NOT to do
- Don't send a Google Form
- Don't ask people to "test and fill out a survey"
- Don't over-explain the project — let the product speak

---

## Stage 2: Opt-In Public Beta (Week 3–5)

### Who
- Anyone at Webb who wants to try it
- Spread by word of mouth from Stage 1 testers + your own social channels

### How to distribute
- Instagram story / Snapchat / whatever channel actually reaches Webb students
- Keep the pitch to one sentence: **"I made an AI that knows Webb's handbook, course catalog, and website — ask it anything"**
- Link directly to the tool, not to a survey

### In-app micro-feedback (build this into the product)
After a user has asked 2–3 questions, show a small non-blocking prompt:

```
┌─────────────────────────────────────────────┐
│  Quick feedback (30 sec)                    │
│                                             │
│  Did you get a useful answer?   👍  👎     │
│                                             │
│  Would you use this again?                  │
│  [Yes]  [Maybe]  [No]                       │
│                                             │
│  What should it know that it doesn't?       │
│  [___________________________________]      │
│  (optional)                                 │
│                                             │
│                          [Submit]  [Skip]   │
└─────────────────────────────────────────────┘
```

Three questions. No demographics, no AI adoption baseline, no multi-section form. If they skip, that's fine — you still have their usage data from the server logs.

### What to track
| Metric | Source | Why it matters |
|--------|--------|----------------|
| Unique users / day | Server logs | Is anyone coming back? |
| Queries per session | Server logs | Engagement depth |
| 👍 / 👎 ratio | In-app feedback | Product quality signal |
| "Would you use this again?" | In-app feedback | Retention signal |
| Open-text responses | In-app feedback | What's missing from the knowledge base |
| Organic referrals | Ask Stage 1 testers if they shared it | Word-of-mouth traction |

### Success criteria to move to Stage 3
- 20+ unique users over 2 weeks
- 👍 rate > 70%
- "Would use again" (Yes + Maybe) > 60%
- At least a few users you don't personally know

---

## Stage 3: Decision Point (Week 6)

By now you have real data. Choose a path:

### Path A: Pitch to School
**Use if:** you got decent traction and want official support.

Bring this to the administration or AI group:
- "X students used this over Y weeks"
- "Z% found it helpful"
- "Here are the top 5 things students asked about" (from logs)
- "Here's what I'd build next with support: [1B/1C from roadmap]"

This is 10x more compelling than a survey proposal. You're showing a working product with real users, not asking permission to start.

### Path B: Keep Growing Independently
**Use if:** school says no, or you'd rather stay independent.

- Keep iterating on the knowledge base
- Add Phase 1.5 features (Socratic tutor etc.) based on what users are actually asking for
- The product grows on its own merit

### Path C: Merge with School AI Group
**Use if:** the group is building something similar and collaboration makes sense.

- Your product + usage data = strong contribution to bring to the table
- You have leverage because you already built something that works

---

## What Happens to the Existing Survey Docs

| Document | Status |
|----------|--------|
| `survey-design.md` | **On hold.** The full survey methodology is good work but wrong timing. Revisit if the school asks for formal data, or if Stage 2 reaches 60+ users and you want deeper insights. |
| `survey-google-forms.md` | **Replaced** by the in-app micro-feedback widget for now. Keep the file — the parent survey may be useful later if you pursue Phase 2. |
| `roadmap.md` | **Still valid.** Beta data will tell you which Phase 1 sub-feature to build next. |
| `knowledge-base-guide.md` | **Still valid.** Core technical reference. |

---

## Implementation Checklist

### Before Stage 1
- [ ] Confirm the Render deployment is stable and fast enough for testers (cold start issue?)
- [ ] Check server logs are capturing queries (or add basic logging if not)
- [ ] Share link with dev group, keep it casual

### Before Stage 2
- [ ] Build the 3-question in-app feedback widget
- [ ] Fix the top issues found in Stage 1
- [ ] Prepare the one-sentence pitch + link for social sharing
- [ ] Make sure the tool handles load (even modest — 20 concurrent users on free Render?)

### Before Stage 3
- [ ] Compile usage stats into a simple one-page summary
- [ ] Pull 3–5 real example Q&As that show the tool working well
- [ ] Decide which path (A/B/C) based on data and your gut

---

## Timeline

```
Week 1–2    Private beta (dev group, 5–10 testers)
Week 2      Fix issues, decide go/no-go for public
Week 3–5    Public beta (opt-in, in-app feedback)
Week 6      Review data, choose path A/B/C
```

Total: ~6 weeks from link-share to decision point. No surveys, no forms, no waiting for permission.
