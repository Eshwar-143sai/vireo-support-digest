# 3-minute screen recording: talk track (about 430 words; rehearse once, it runs ~2:50)

**0:00 - 0:20  What and why.** Show README top + `out/leaderboard.md` raw table. "Priya asked for a digest and a tickets-closed leaderboard. I read the pack first: the policy and Neha's email say the leaderboard would be misleading, and Arjun wants money, not a reading tool."

**0:20 - 0:55  Prompts.** Show the chat. "My first prompt was: profile these five files and find the traps. That found 653 duplicate IDs, legacy times five and a half hours early, and CSAT zero meaning no response. Second: find where the desk loses money, priced at the policy's costs. Third: build a classifier and audit it by hand."

**0:55 - 1:40  What changed between versions.** Show `out/eval_report.md` table. "Version 1 scored 82%. Failures clustered: boxes 'crushed' filed as hardware, product names acting as keywords. Version 2, 89% on tickets it had never seen. Version 3, 90%. Each time I drew a fresh sample so the number stays honest."

**1:40 - 2:30  What I threw away.** Show `git log` or the form's discard list. "Three things. My first lot-defect finding: highly significant, then it vanished when I stopped reading 'I want my money back' as a refund complaint. My first payout number, Rs 5.6 lakh, counted legitimate duplicate-charge refunds; corrected to Rs 3.1 lakh. And my typo repair, which turned 'crackling' into 'tracking'."

**2:30 - 2:55  Result.** Show `out/business_case.json` payout block + digest. "Second payouts: 7.1% of paid orders, Rs 52,000 a quarter, target 2% saves about Rs 37,000. Ninety-two percent raised by a different agent than the first. It's a lower bound and the 70% is my assumption."

**2:55 - 3:00** "Run cost is zero. README has the rest."
