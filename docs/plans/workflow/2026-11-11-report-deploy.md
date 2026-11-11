# Deploy the report to GitHub Pages (approved 2026-11-11)

- Add `.github/workflows/deploy-report.yml`: the template's deploy workflow, uploading `report/` only,
  run on pushes to `main` that touch `report/**` (and by hand).
- Remove `report/.github/workflows/deploy.yml`: GitHub never runs nested workflows, and it uploaded `.`.
- Pages is already enabled with source "GitHub Actions"; site: https://ruzhylopv.github.io/math-tutor-nlp-sys/
- The developer commits this to `main` directly.
