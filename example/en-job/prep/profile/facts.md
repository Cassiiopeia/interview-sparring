# Facts

The ledger every answer is checked against; one row per fact, and Status is one of: confirmed (checked against its source), unconfirmed (not verified yet), do-not-say (never say it in an interview), confidential (true, but not for the interviewer).

> Example: a fictional applicant. Nothing here describes a real person.

| Fact | Status | Source |
|---|---|---|
| Backend engineer at a logistics startup since 2026 (4 years by the interview) | confirmed | CV |
| Main duty: the order-tracking API (Python, PostgreSQL) | confirmed | CV, user 2030-03-02 |
| Rebuilt the tracking status cache; I designed it, a teammate reviewed and deployed it | confirmed | user 2030-03-05 |
| Cache rebuild cut p95 response time from about 800 ms to about 200 ms | confirmed | user 2030-03-05 (team dashboard) |
| Led the on-call handbook rewrite | unconfirmed | user 2030-03-05 — "I think I led it"; check who owned it |
| Customer names of the current employer | do-not-say | user 2030-03-02 |
| Monthly order volume of the current employer | confidential | user 2030-03-02 |
| Studied mechanical engineering, moved to software through side projects | confirmed | CV |
