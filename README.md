# FAMCO PHM Dashboard MVP

This is a static HTML/CSS/JavaScript prototype for a Population Health Management dashboard.

## Important security rule
Do **not** upload real patient-level data to GitHub Pages.
Use only synthetic, aggregated, or properly de-identified data in this repository.

## Files

- `index.html` — main app page
- `style.css` — dashboard design
- `app.js` — navigation, table rendering, search, and card rendering
- `data/sample_dashboard.json` — synthetic demo data
- `.nojekyll` — disables Jekyll processing on GitHub Pages

## Run locally

Open the folder in VS Code and use Live Server, or run:

```bash
python -m http.server 8000
```

Then open:

```text
http://localhost:8000
```

## Publish on GitHub Pages

1. Create a new GitHub repository, for example `phm-dashboard`.
2. Upload these files to the root of the repository.
3. Go to repository **Settings**.
4. Open **Pages**.
5. Under **Build and deployment**, choose **Deploy from a branch**.
6. Choose branch `main` and folder `/root`.
7. Click **Save**.
8. Wait until GitHub shows the published URL.

## Next development step

Replace `data/sample_dashboard.json` with an automatically generated de-identified JSON file from the PHM ETL pipeline.
