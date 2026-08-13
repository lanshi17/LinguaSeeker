# Cover Letter — Genetics in Medicine

> Draft prepared 2026-08-13. Replace bracketed placeholders before submission.

---

[Date]

Editor-in-Chief
Genetics in Medicine

Dear Editor,

We are pleased to submit our manuscript, "**Marginal Contribution of Cross-Lingual Evidence Extraction to ACMG/AMP Variant Classification: An Ablation Study of a Multi-Agent Literature Curation System**," for consideration as an Original Research Article in *Genetics in Medicine*.

**Why this study matters to GIM readers.** ACMG/AMP variant classification depends on manual literature curation that is overwhelmingly English-centric. Clinical laboratories increasingly evaluate variants whose evidence base includes non-English publications, yet no study has quantified what is actually lost when curation pipelines process English text only. We believe this question — at the intersection of variant curation practice, health equity, and the rapidly evolving role of large language models in clinical genetics — falls squarely within the scope of the journal.

**What we did.** We developed Lingua Seeker, an open-source multi-agent system implementing a four-phase pipeline (multi-source literature acquisition, cross-lingual dual-track evidence extraction, entity standardization, and expert-in-the-loop review), and ran a controlled ablation: 30 ClinGen/ClinVar-curated variant entries, each pairing an English article with a system-generated Chinese translation, were processed twice — English-only versus dual-track (English + Chinese) — with all other parameters held identical.

**Principal findings and implications.**

- The Chinese track contributed a mean of 3.62 evidence items per entry that the English track missed (+22.8%; p = 5.9 × 10⁻⁶), with 86.2% of entries gaining evidence.
- Gains concentrated in clinically salient fields — phenotypes, age of onset, assay context — and the Chinese track rescued gold-standard fields (variant type, mode of inheritance, gene symbol) in 10% of entries, including one complete extraction failure.
- Mean match against an eight-field English-centric gold standard was unchanged (3.57/8 in both modes; p = 1.0), demonstrating that multilingual processing adds evidence without degrading average accuracy, and that evidence-level yield is the more sensitive measure of multilingual value.

These results provide the first quantitative estimate of the marginal value of cross-lingual evidence extraction for variant classification and argue for multilingual processing in curation workflows, particularly for variants studied in non-English-speaking populations.

**Transparency and reproducibility.** All source code, ablation reports, and analysis scripts are openly available (https://github.com/lanshi17/LinguaSeeker, branch `feature/gim-submission`); all statistics and figures are reproducible from committed report files.

This manuscript is original, is not under consideration elsewhere, and has not been previously published. All authors have approved the submission. [The authors declare no conflicts of interest. / Conflicts: …]

Reporting follows no clinical-trial or systematic-review framework (computational ablation study); no human participants were involved (public ClinGen/ClinVar data and PMC open-access articles only), so IRB review was not required.

Thank you for considering our manuscript. We look forward to your response.

Sincerely,

[Corresponding author name, degrees]
[Affiliation]
[Address / telephone / e-mail]
On behalf of all authors: [author list]
