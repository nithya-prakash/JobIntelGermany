# Phase 10: Responsible AI and EU AI Act risk assessment

**Reviewed:** 4 October 2026  
**Scope:** repository behavior observed at this review; this is an engineering risk assessment, not legal advice, an AI Act classification decision, or a conformity assessment.

## Current intended use and boundary

The implemented matcher is a local command-line aid for a person searching postings. It reads either canonical skill IDs or a local CV, extracts terms from the CV in process memory, and ranks postings by overlap with a finite skills taxonomy. Its score is explicitly described as taxonomy overlap, not a hiring probability or overall suitability. It is not an employer-facing applicant-ranking product, and the repository has no recruitment workflow or deployed service.

That boundary matters. Using this tool to filter, evaluate, or rank applicants on behalf of an employer would change its intended purpose and affected people. Annex III point 4(a) of the AI Act covers certain recruitment and selection systems, including systems that filter applications or evaluate candidates. Classification depends on the actual intended purpose and context; this document does not decide whether a future version is high-risk or whether an exception applies. Obtain a use-specific legal assessment before such a change.

## Observed controls and evidence

| Area | Observed behavior | Evidence and limit |
| --- | --- | --- |
| Scope and score | Candidate-side CLI; interpretable precision, coverage, and harmonic overlap components; output says it is not hiring probability or suitability. | `src/german_job_market/matching.py:167-191,218-245`; no human-judged relevance benchmark (`data/evaluation/matching/phase log.md`). |
| Candidate input | Structured skill IDs avoid candidate text. A local UTF-8 CV is read, parsed in memory, then the local result is printed; no persistence is implemented by this command. | `src/german_job_market/matching_cli.py:37-45,58-84`. This is not a whole-system retention or endpoint security guarantee. |
| Posting text | Email and German phone-pattern redaction is applied by source normalization. | `src/german_job_market/normalization.py:15-16,47-55`. Pattern redaction can miss other identifiers and is not anonymization. |
| Data schema | Posting schema has job and organization fields, but no explicit demographic attributes. | `src/german_job_market/schema.py:14-37`. Lack of explicit sensitive fields does not remove proxy-bias risk. |
| Model deployment | No fine-tuned model or inference backend was produced or benchmarked. | `reports/phase8/llm_readiness.json`, `reports/phase9/serving_readiness.json`. |
| Salary prediction | No salary target labels were present in the audited corpus; no salary predictor was trained. | `reports/phase6/salary_readiness.json`. |

No group fairness metrics, causal analysis, representativeness analysis, or user-impact study has been run. The risk ratings below are qualitative engineering priorities, not measured probabilities or impact estimates.

## Risk register

The machine-readable register at [`reports/phase10/responsible_ai_risk_register.json`](../reports/phase10/responsible_ai_risk_register.json) records each item with the fields **Requirement**, **System behavior**, **Evidence**, **Gap**, **Risk**, and **Mitigation**. It separates controls present in code from organizational actions and conditional legal duties.

Key findings:

1. **Purpose creep into employer screening — High.** If adopted to filter or evaluate applicants for employers, the intended use may enter the AI Act's Annex III employment use case. Require a documented use-case review, legal classification, provider/deployer role allocation, and pre-deployment controls before enabling it.
2. **Unequal access and proxy bias — High.** No group-level test or representative candidate benchmark exists. Skills, language, career breaks, education, and CV-writing style can act as proxies or interact with missing taxonomy coverage. Do not use rankings to make or recommend employment decisions until a lawful and appropriate evaluation plan, representative data, and human review exist.
3. **Misleading gap explanations — High.** A skill absent from a posting's extracted terms is labeled missing even when the posting does not establish it as a requirement. The taxonomy is finite, and the source combines requirements with responsibilities. Present this as “not found in this text,” retain evidence spans in a future version, and provide a correction path.
4. **CV privacy and security — High.** The current CLI processes a local file in memory, but has no account controls, retention workflow, access logging policy, or deployed upload boundary. Keep CVs local; before any hosted or stored use, document controller/processor roles, lawful basis, purpose, minimization, deletion/retention, access control, encryption, incident handling, and any DPIA need with privacy counsel.
5. **Data quality and market representation — High.** The underlying posting corpus is historical, single-source, AI-skill-focused, and lacks many decision-relevant fields. It cannot support claims about current vacancies or broad candidate suitability. Limit claims to observed source text and collect a licensed, temporally and occupationally broader evaluation corpus before expanding use.
6. **Human oversight and recourse — High for consequential use.** The CLI emits a ranking but has no review workflow, override, complaint, or appeal mechanism. For any employment-related deployment, define who reviews outputs, what authority they have, how errors are corrected, and how affected people can challenge consequential outcomes.
7. **Monitoring and accountability — Medium now; High in deployment.** No deployed model or operational monitoring exists. If deployed, log model/rule version and decision context without unnecessary CV text, monitor quality and disparate outcomes under an approved governance plan, assign owners, and define rollback and incident response.
8. **Generated explanations and transparency — Medium, future-dependent.** No LLM is currently served. If a later interface uses AI to interact with people or generate content covered by AI Act Article 50, assess the applicable disclosure/marking duties for that exact interaction and make limitations clear. Article 50 has applied since 2 August 2026.
9. **Automated-decision boundary — High if consequential.** The current tool supports search and does not make an employer decision. A future system that solely makes decisions with legal or similarly significant effects on people requires a separate GDPR Article 22 and data-protection assessment; a nominal human click does not by itself establish meaningful human involvement.
10. **Conditional AI Act obligations — High before changed use.** Annex III high-risk rules are scheduled to apply from 2 December 2027 following the 2026 amendment. Article 27 fundamental-rights impact assessment (FRIA) is not a universal requirement for every private recruiter; its scope depends on the deployer and use categories in the Regulation. Reassess the consolidated law and final guidance at each release/use change.

## Legal and organizational interpretation

As of the review date, the European Commission states that the AI Act generally applies from 2 August 2026, with Annex III high-risk rules delayed to 2 December 2027. Article 50 transparency obligations apply from 2 August 2026. These dates do not mean that every provision has started or that this prototype is compliant. The Act's employment and recruitment examples, classification rules, human oversight, accuracy, deployer duties, and FRIA scope must be applied to the concrete intended purpose, actors, and deployment context.

The GDPR remains a separate assessment for CV and other personal data. Article 22 addresses certain decisions based solely on automated processing that produce legal or similarly significant effects, with conditions and safeguards in its text. This repository does not establish a lawful basis, controller/processor roles, retention schedule, data-subject process, or a DPIA conclusion.

| Layer | Current conclusion |
| --- | --- |
| Technical controls | Some data minimization and direct-contact-pattern redaction exist; matching is local and skills-only. These are limited controls, not a security or fairness certification. |
| Organizational controls | No production owner, oversight procedure, appeal route, incident process, monitoring plan, or approved retention schedule is implemented. |
| Legal interpretation | No compliance or risk classification conclusion is made. Seek qualified legal/privacy review before processing real candidate CVs in a service or using outputs in recruitment decisions. |

## Release gates before expanding use

- Keep the current candidate-side, local-search scope explicit in CLI and documentation.
- Do not use the current match score to reject, shortlist, or prioritize people for employment.
- Before a hosted CV feature, complete privacy/security design and data-protection review, including retention and deletion behavior.
- Before employer-side screening, make a documented intended-purpose and AI Act classification assessment; evaluate whether Annex III, GDPR Article 22, and other employment/data-protection duties apply.
- Build an independently reviewed and appropriately representative benchmark; measure ranking quality and group-level harms only where collection and processing are lawful and ethically justified.
- Add source evidence and a correction/appeal route for any candidate-facing gap claims.
- Assign human reviewers and operational owners, with authority to override and pause use, before consequential decisions.

## Official references

- [AI Act consolidated text as of 27 July 2026](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02024R1689-20260727) — Annex III point 4, Articles 6, 14, 15, 26, 27, and 50.
- European Commission: [AI Act regulatory framework and application timeline](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai), [Article 50 transparency FAQ](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act), and [enforcement timeline](https://digital-strategy.ec.europa.eu/en/policies/enforcement-ai-act).
- [GDPR consolidated text, Article 22](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng).

Legal sources were checked on 4 October 2026. This review is a portfolio engineering artifact, not legal advice or evidence of conformity with the AI Act, GDPR, or employment law.
