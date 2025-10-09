[CHANGELOG.md](https://github.com/user-attachments/files/22365655/CHANGELOG.md)
# Changelog
# Changelog

All notable changes to this project will be documented in this file.

## 1.1.1 — 2025-10-08

- Default hard-burned warning text at the top-left of every slice: "NOT VALIDATED FOR CLINICAL USE".
- Applies to both preview and exported series (burned into pixels at ~1000 HU).

## 1.1.0 — 2025-10-06

- Per-ROI burn controls: outline style, line width, and fill ΔHU overrides with +/- 50 HU steppers.
- Fill ΔHU global control relabeled and per-ROI values inherit the global setting until overridden.
- Burn notes textarea expanded to five lines with live character counting.
- Preview/burn pipeline honors per-ROI line widths and fill deltas; footer text now reflects the rounded ΔHU.

## 1.0.4 — 2025-10-05

- Integrated external core burn pipeline into the browser app:
  - Unified `burnSlices` with exact pixel stamping (even/odd‑aware 1×1 and 2×2 kernels).
  - Fixed dotted contour sampling to a consistent step of 6.
- Preview fidelity improvements:
  - Preview now generates an in‑memory burned series that exactly matches export (no overlay text/lines added).
  - Suppressed ROI overlays in sagittal/coronal during real preview so only burned pixels are shown.
  - Slice slider/labels now reflect the active series (preview > processed > original).
- Burned footer enhancements:
  - Two lines are always burned: “<ROI>, <Solid|Dotted>[, ±HU overlay]” and “NOT FOR DOSE CALCULATION”.
  - Optional 3‑line user note burned above the ROI line; adaptive wrapping to full image width; automatic ellipsis.
  - Footer font reduced ~2 points for readability (15 px), stamped at 1000 HU.
- Defaults & UI polish:
  - Default line width: Solid = 1 px; Dotted = 2 px.
  - Text inputs/textarea focus styling improved for dark theme readability.
- Robustness & fixes:
  - Resolved “Cannot access 'ctx' before initialization” during preview footer generation.
  - Removed preview overlay footer (previously caused duplicate footers).
  - dcmjs include adjusted to reduce file:// CORS issues; recommend serving via a local HTTP server if needed.


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
