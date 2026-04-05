# Bioinformatics Domain Example

This example shows how to use skill-facets for bioinformatics project delivery.

## Included Skills

| Skill | Type | Description |
|-------|------|-------------|
| ppt | command | SCI presentation with V4 nested signals |
| sci-fig | command | Publication-quality figures (300DPI, white bg, no gridlines) |
| audit-fix | command | Plan-based audit-fix loop (P0-P3 priority) |
| bio-report | command | Chinese bioinformatics Word report (SimSun/SimHei fonts) |
| deliver-v4 | skill | One-click delivery packaging (dual facet + runner) |

## Install

```bash
# From project root
bash /path/to/skill-facets/install.sh --example bioinformatics
```

## Workflow

```
/sci-fig          → Generate SCI figures
/validate sci-fig → Check DPI, background, format
/bio-report       → Generate Word report
/validate bio-report → Check fonts, numbering, Markdown residue
/deliver-v4       → Package: audit → collect → scan → ZIP
```

## Blind Test Data

`blind_test/` contains PPT outputs from 5 rounds of V0/V2/V3/V4 signal architecture comparison.

## Real Project

`real_project/` contains a mock gastric cancer RNA-seq analysis with PCA, volcano, GO enrichment, and KEGG figures.
