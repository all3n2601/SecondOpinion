# Demo video script (3 minutes)

Record the screen at 1280×800 or larger, with the practice report and release A (or the unsealed
practice envelope). Before you start, run `npm run dev`, open http://localhost:3000, check it says
**API connected**, and set **Viewing as** to *Data-use reviewer*.

| Time | Screen | Say |
| --- | --- | --- |
| 0:00 | Start | "Reviewers get reports like this and must decide: can we publish it?" |
| 0:20 | Start → **Use the practice report** → **Check the files** → **Find claims** → Claims → Audit board | "Three claims: one supported, one wrong, one the data can't answer." |
| 0:50 | Open C2 (≈62% Luminal A) → evidence panel | "The report says 62%. The data says 49.9%, 421 of 844, and never 62% however you count it. Here are the code and the sample IDs." |
| 1:40 | Open C3 (hormone therapy) | "This release has no treatment data, so we don't guess. Here's the data that would be needed." |
| 2:00 | **Review** → accept all three | "A person confirms or overrides every verdict before anything is exported." |
| 2:10 | **Decision** → switch **Viewing as** to *Program leader* | "Same facts, simpler view. The tool suggests Fix a problem." |
| 2:40 | Choose a decision, write a reason, **Export**, download both files | "audit.json passes the organizers' validator, and the Decision Record says who must sign off. Research prototype, never a clinical decision." |

After recording, upload the video (unlisted is fine), and replace `_link to be added_` at the top of
the README with the link.

Checks before recording:

- [ ] `.venv/bin/python docs/challenge/format/validate.py audit.json` prints `valid` on the downloaded file.
- [ ] The research-only banner is visible on every screen in the video.
- [ ] No sentence in the voice-over sounds like medical advice.
