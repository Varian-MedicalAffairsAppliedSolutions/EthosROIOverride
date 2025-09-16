[CHANGELOG.md](https://github.com/user-attachments/files/22365655/CHANGELOG.md)
# Changelog
# Changelog

All notable changes to this project will be documented in this file.

## 1.0.3 — 2025-09-16

- Replaced gate with PlanDeliverySimulator-style flow; added offline QR and JotForm iframe embed.
- Changed access code and enforced registration guard on `roi_override.html`.
- Added sticky top banner: **NOT VALIDATED FOR CLINICAL USE**.
- Help/About: added bold orange disclaimer; renamed “Open Source Licenses” to “Dependencies and Licenses”; made links clickable and orange; inlined Varian LUSLA text as a collapsible section.
- Added footer license link and About section updates; removed unused F1 hint.
- README updates: UI Overview image, System Requirements (Browser), Support and Development, license switched to Varian LUSLA, important disclaimer.
- Gate pages updated and standardized (`gate/index.html`, `gate/register.html`, `gate/check-registration.html`, `gate/VarianLUSLA.html`).
- ROI list now sorted alphabetically by name in the sidebar.

## 1.0.2 — 2025-09-12

- Added JotForm registration support in the licensing gate (optional online flow in `gate/register.html`).
- Default Export Mode set to “Each ROI on a Separate CT”.
- Default line style set to Dotted; preview/slider defaults updated accordingly.
- Single ZIP export for separate mode with per‑ROI subfolders and correct SeriesDescription.
- Version/build badge added to main UI; Help menu shows version and links to README/Changelog.

## 1.0.1 — 2025-09-10

- Added live preview on ROI toggle with white outline.
- Preview thickness matches image pixels across views; respects Solid/Dotted style and Line Width.
- Removed Preview button; preview now updates automatically with control changes.
- Added Export Mode radios (Single ImageSet vs Separate ImageSets).
- ZIP filename now includes burned ROI name(s).
- Added comprehensive README with setup, usage, and technical notes.
- Version bump to 1.0.1.

## 1.0.0 — 2025-09-08

- Initial Electron packaging and basic burn & export workflow.
- RTSTRUCT parsing and overlay rendering.
- Python alternative (`roi_override.py`) with contour/fill and per‑ROI series support.
