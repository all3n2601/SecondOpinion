# Demo video (about 3 minutes, screen recording only)

The video is a silent screen recording: no voice-over. The screen has to tell the story on its own,
so move the mouse slowly and pause on each key screen for a few seconds so it can be read.

Record at 1280×800 or larger, with the practice report and release A (or the unsealed practice
envelope). Before you start, run `npm run dev`, open http://localhost:3000, check it says
**API connected**, and set **Viewing as** to *Data-use reviewer*. Close other tabs and hide
notifications.

| Time | Do this | Pause on |
| --- | --- | --- |
| 0:00 | Landing page → **Start an audit** | The report text and the research-only banner |
| 0:20 | **Run the practice audit** → **Open the audit board** | The three verdicts: one supported, one wrong, one the data can't answer |
| 0:50 | Open C2 (≈62% Luminal A) → evidence panel | 62% in the report vs 49.9% (421 of 844) in the data, the code and the sample IDs |
| 1:40 | Open C3 (hormone therapy) | *Insufficient evidence* and the data that would be needed |
| 2:00 | **Review** → accept all three | That a person confirms each verdict |
| 2:10 | **Decision** → switch **Viewing as** to *Program leader* | The simpler view and the suggested decision |
| 2:40 | Choose a decision, type a reason, **Export**, download both files | The downloaded `audit.json` and Decision Record |

After recording, upload the video (unlisted is fine), and replace `_link to be added_` at the top of
the README with the link.

Checks before recording:

- [ ] Click through once first: the landing page and Review page changed on Nov 14, so make sure
      every step above still matches the screen.
- [ ] `.venv/bin/python docs/challenge/format/validate.py audit.json` prints `valid` on the downloaded file.
- [ ] The research-only banner is visible on every screen in the video.
- [ ] Nothing typed on screen (for example the decision reason) reads like medical advice.

---

# Finals runbook (Nov 14, live judging)

A judge must finish the scenario without help, then hands over an unseen input. Rehearse these in
order. On Nov 13 the API path was run end to end (report, audit, decision, export, the organizers'
validator) on release A, the no-RNA release and the practice envelope. The **add a role** form was
not clicked through in the browser: do that once before the judges arrive.

## Before the judges arrive

- [ ] `npm run dev`; the Start page says **API connected**.
- [ ] **Unsealing works on this laptop.** `envelopes/unseal.py` needs `cryptography` and `pandas`,
      and `.venv` does not have them (it also has no `pip`). From the challenge repo, either
      `uv pip install --python ../SecondOpinion/.venv/bin/python -r requirements.txt`, or make a
      throwaway venv (`uv venv v && uv pip install --python v/bin/python -r requirements.txt`) and run
      `v/bin/python envelopes/unseal.py ...`. Then rehearse with the public code:
      `python envelopes/unseal.py practice orange meadow pilot lantern` (about 10 to 20 seconds) and
      point **Release folder** at `envelopes/opened/practice/release/`. Do this before Saturday, not
      during the Q&A; `git pull` first so `envelopes/sealed/` is current.
- [ ] **AI helper chip.** Either it says *off*, or one test sentence it handles comes back with a
      plan. If a claim's reason reads "The AI service did not accept the request (HTTP 308)", the
      `SO_AI_BASE_URL` in `.env` is `http://` and the host redirects to `https://`. Use the `https://`
      URL, or set `SO_AI=off`. The audit still finishes either way: the sentence just comes back
      *insufficient evidence* with that reason.
- [ ] **Release folder** box holds a path that exists on this laptop (it can be pre-filled with a
      stale one). Press **Check the files**: it lists the files and checksums.
- [ ] The release matches what you expect: release A (with `rna_hiseq.tsv.gz`) or an envelope release
      (no RNA file, no manifest). The tool names the missing RNA file in a note; it never fails.
- [ ] Tests on the real data: `SO_RELEASE_DIR=<release folder without the RNA file> .venv/bin/python -m pytest -q`.
      Expected: all pass except `test_status_without_a_key_says_why` when `.env` turns AI on.

## The scenario a judge runs alone (about 3 minutes)

1. **Start** → *Run the practice audit* → *Open the audit board*.
2. Board: three verdicts with a plain reason each. Open **C2** for the evidence: the calculation, the
   report-vs-data gauge, the files and checksums, the pandas snippet, the sample IDs, the eight ways of
   counting.
3. **Review**: accept or override each (an override needs a reason and a role). **Decision**: read the
   suggestion and who signs off, choose one, give a reason, **Export**.
4. The downloaded `audit.json` validates with `docs/challenge/format/validate.py`.

## Unseen inputs, and what the tool does

| Judge hands over | Do this | What they should see |
| --- | --- | --- |
| A **new role** ("Biostatistician", "Hospital CIO") | **Add a role** form: name, detail level, sections | The role appears in **Viewing as**; the same audit re-renders with that role's sections and detail |
| A **sealed envelope** (number + four words) | Unseal from the challenge repo, point **Release folder** at `envelopes/opened/E<n>/release/` | A note that the release has no RNA file; counts on the four layers present; every other check unchanged |
| A report with **conflicting findings** (two sentences disagreeing, or a number that is right under one way of counting and wrong under another) | Paste it on Start | One finding per sentence; each verdict is separate; *fragile* verdicts name the counting choice that flips them |
| The **same sentence twice** | Paste it | Listed once, so the export never has two findings with the same `claim_text` |
| A claim about **treatment, response, survival benefit or cause** | Include it in the paste | *Insufficient evidence*, with the data that would be needed. Never a guess |
| A sentence with **Markdown** (bold, backticks, links) | Include it | `claim_text` in `audit.json` is the sentence exactly as written, Markdown included |
| An **age or duration** ("median age 58 years") | Include it | Not treated as a count of tumors; it comes back as a number with no check yet |
| A sentence naming **both sexes** ("1,085 female and 12 male patients") | Include it | Not forced into one count; it comes back as a number with no check yet |

If the browser state looks wrong, **Start over** clears it (it lives only in this tab's
`sessionStorage`).

## Say, and do not say

- Say: "every number is recomputed by ordinary code; the AI helper only proposes a check, and our code
  runs it and sets the verdict."
- Say: "a person confirms every verdict; `needs_human_review` is always true in the export."
- Do not say the tool recommends treatment, predicts outcomes, or replaces a reviewer.
