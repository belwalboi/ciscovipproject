# NetSage AI — Project Scaffold

## What's built
- `cases.csv` — 30 cases, ~4 per fault type (VLAN, Gateway, DHCP, DNS, Routing, ACL, NAT, Wireless), each with symptom, topology note, show output, expected fault, OSI layer, concept tag, severity.
- `diagnose_prompt.md` — system prompt + JSON schema + 3 worked few-shot examples (including the two from the brief) + a helper prompt for reconciling AI output with the rule checker.
- `rule_checker.py` — deterministic Python checks: duplicate IP, gateway mismatch, wrong mask, interface down, missing VLAN, missing route, DHCP pool sanity. Runs standalone with sample output (5 findings across 5 sample cases — see console output).
- `human_review_log.csv` — template, pre-seeded with case_id for one representative case per category, ready for your Accepted/Edited/Rejected verdicts.
- `dashboard_summary.csv` — one row per case with category/OSI/severity pre-filled; `ai_confidence`, `human_verdict`, `agreement` columns left for you to fill after running diagnoses.

## What you still need to do (can't be faked — needs your actual AI + human review)
1. **Run the AI**: for each of the 30 cases, feed `symptom` + `topology_note` + `show_output` into `diagnose_prompt.md`'s user template, get back the JSON.
2. **Fill `dashboard_summary.csv`**: paste `confidence` into `ai_confidence`. Once reviewed, mark `human_verdict` (Accepted/Edited/Rejected) and `agreement` (Yes/No — did the AI's root cause match `expected_fault` in cases.csv).
3. **Fill `human_review_log.csv`**: pick at least 5 cases where the AI got it wrong or partially wrong (edited/rejected). For each, write 1–2 sentences on *why* it was wrong — this is your Responsible AI log requirement.
4. **Cross-check with the rule checker**: for cases involving interface/DHCP/IP-level facts (C01, C05, C08, C09, C10 are already stubbed in `rule_checker.py`'s `sample_cases`), extend the list with the rest of your 30 cases' facts and compare its findings against the AI's diagnosis using the helper prompt in `diagnose_prompt.md`.
5. **Dashboard chart**: open `dashboard_summary.csv` in Sheets/Excel, pivot on `category` (count) and on `agreement` (% agreement rate = AI-vs-human agreement rate the brief asks for).
6. **Demo video (5–10 min)**: pick one case (C20's inter-VLAN ACL case or C28's guest isolation case are good because they match the brief's own examples) and record: broken lab → AI diagnosis JSON → human review decision → fix applied in Packet Tracer → verification ping/traceroute.

## Notes for your team
- Keep `cases.csv` as the single source of truth for `expected_fault` — that's what you grade AI agreement against.
- The rule checker is intentionally *not* AI — it's meant to catch the same mistake a human junior engineer would catch mechanically (e.g. C01's VLAN port misassignment), so you can show, in your report, where deterministic checks and AI diagnosis agree vs. where the AI adds value the rule checker can't (e.g. C20's ACL evaluation order, which needs semantic reasoning, not just a lookup).
