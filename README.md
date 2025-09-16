[README.md](https://github.com/user-attachments/files/22365002/README.md)
# ROI Override Tool

Burn DICOM RTSTRUCT contours into CT image pixels to generate derived “annotation baked‑in” DICOM series for review or system ingestion. This repository provides a browser/Electron implementation (`roi_override.html` + `roi_override.js`) and a Python desktop alternative (`roi_override.py`).

Important: ## Not validated for clinical use.

## UI Overview

![ROI Override Tool UI](https://github.com/Varian-MedicalAffairsAppliedSolutions/EthosROIOverride/blob/main/docs/UI-Overview.png?raw=1)

## Features

- Load a folder of CT DICOMs and associated RTSTRUCT(s).
- ROI browser with show/hide and include/exclude for burn‑in.
  - Single‑click an ROI name to show/hide its overlay.
  - Double‑click an ROI name to navigate the views to its center.
- Live preview when toggling “Include in burn‑in”:
  - White outline, accurate image‑pixel thickness.
  - Honors Solid/Dotted line style and Line Width.
  - Reverts to original ROI colors when not selected.
- Burn & Export:
  - Combined (single ImageSet) or Separate (one ImageSet per ROI).
  - DICOM SeriesDescription includes burned ROI names.
  - ZIP filename contains the burned ROI name(s): `<SeriesName>__<ROI1>_<ROI2>.zip`.
- Python app supports Contour and Fill with HU override, combined or per‑ROI series.

## Access & Licensing

- On first launch, the app opens an access gate requiring registration and acceptance of the Varian Limited Use Software License Agreement (LUSLA), modeled after PlanDeliverySimulator.
- Enter the registration code provided to you to complete access. Your registration status is stored locally.
- Files:
  - `gate/index.html` — entry screen with LUSLA link
  - `gate/register.html` — registration code entry
  - `gate/VarianLUSLA.html` — license agreement (abridged)

## Data Requirements

- CT images: classic single‑frame DICOM CT series (one slice per file).
- RT Structure Set (RTSTRUCT): references the same Study as the CT series.
- Consistent orientation and spacing across CT series.

## Quick Start (Electron/Desktop)

Prerequisites:
- Node.js 18+ and npm

Install and run:
- `npm install`
- `npm run dev`

Build Windows portable binary:
- `npm run build` (outputs `dist/ROI-Override-<version>.exe`)

## System Requirements (Browser)

- **Recommended Browsers:** For the best performance and compatibility, please use the latest version of:
  - **Google Chrome** ([Download](https://www.google.com/chrome/))
  - **Mozilla Firefox** ([Download](https://www.mozilla.org/firefox/new/))

- **Other Supported Browsers:** The tool is also compatible with:
  - Microsoft Edge (latest version)
  - Safari (version 14 or newer)

- **Unsupported:** Internet Explorer is not supported.

For users in environments with software installation restrictions, please contact your IT department to request that a supported browser be installed.

## Quick Start (Browser)

- Open `roi_override.html` in a modern browser (Chromium‑based recommended).
  - If using the Electron app, it will open the access gate first.
- Click “Import DICOM Files” and select your CT/RTSTRUCT folder contents.
- If multiple CT series are detected, choose the target series when prompted.
- Use the RT Structure panel to show/hide ROIs and toggle “Include in burn‑in”.
  - Single‑click ROI name = show/hide; double‑click = navigate to ROI.
- Configure Burn‑In Controls:
  - Series Name
  - Line Width and Style (Solid/Dotted)
  - Default HU (used if ROI has no per‑ROI HU set)
- Export Mode:
  - Single ImageSet (combines selected ROIs) or Separate ImageSets (one per ROI)
- Click “Burn & Export”. A ZIP will be downloaded with the modified DICOMs.

## Live Preview Behavior

- Toggling “Include in burn‑in” on an ROI immediately previews its outline in white.
- Preview thickness matches image pixels (axial in image space; sagittal/coronal scaled to maintain pixel‑accurate visual thickness).
- Changing Line Width or Style updates the preview live.
- Toggling an ROI off returns its overlay to the original color.

## Export Details

- Combined export writes one derived series with all selected ROIs.
- Separate export writes one derived series per selected ROI.
- SeriesDescription: `<SeriesName> | ROI1 | ROI2 | ...` (also appended to DerivationDescription when present).
- ZIP filename: `<SeriesName>__<ROI1>_<ROI2>.zip`.
  - Separate mode creates one ZIP per ROI with its name in the filename.
- Inside the ZIP: a folder named after the base Series Name containing the modified DICOM files.

## Python Desktop Alternative

`roi_override.py` provides a native desktop workflow with contour and fill support.

Prerequisites (Python 3.9+):
- `pip install pydicom numpy pillow customtkinter CTkListbox`

Run:
- `python roi_override.py`

Workflow:
- Select a DICOM folder containing CT files and exactly one RTSTRUCT.
- Select ROIs and choose Contour and/or Fill.
- Choose HU preset or Manual Entry per ROI.
- Mode:
  - Single ImageSet: one combined series; enter Series Name at top.
  - Separate ImageSets: one series per ROI; each row can specify its ImageSet Name.
- Choose output directory and run. Each series is saved into its own folder of DICOM files.

Algorithmic notes (Python):
- Contour is stamped with an N×N brush in image pixels (Line Width).
- Fill uses XOR of polygon masks to preserve interior holes.
- Contours are densified to ~1 mm spacing before rasterization.
- UIDs are regenerated (Study/Series/Frame/SOP) for the output series.

## Technical Notes (Browser/Electron)

- RTSTRUCT parsing: reads StructureSetROISequence and ROIContourSequence; associates contours to CT slices using ReferencedSOPInstanceUID.
- Rendering:
  - Axial overlay drawn in image pixel space; preview uses white outline.
  - Sagittal/Coronal use 3D mask + marching squares; line width/dashes scaled so on‑screen thickness reflects image pixels.
- Burn‑in (JS path):
  - Contour stamping only (per ROI), respecting Solid/Dotted style with sampled points.
  - HU conversion via RescaleSlope/Intercept; reverted to native pixel type after burn.
- DICOM writing (JS path):
  - In‑place byte updates: Pixel Data, UIDs (Study/Series/SOP), SeriesDescription, optional BurnedInAnnotation and DerivationDescription if elements exist.
  - New UIDs sized to fit existing element lengths.

## Limitations

- Enhanced multi‑frame CT not supported.
- Assumes consistent pixel spacing/orientation across series.
- RTSTRUCT edge cases (e.g., missing references, non‑axial contours) may render incompletely.
- Browser path writes in‑place within byte arrays; if tags are absent or too short they may not be created/expanded.

## Privacy and Safety

- This tool writes derived DICOM images with annotations burned into pixel data. Do not use for primary diagnosis.
- Ensure patient data handling follows your organization’s privacy and security policies.

## Development

Project layout:
- `roi_override.html` / `roi_override.js` / `viewer.js` / `viewer.css`: main app UI and logic.
- `roi_override.py`: Python desktop alternative with contour/fill.
- `js/dcmjs.js`: DICOM utility used for reading/writing in the browser path.
- `main.js` / `preload.js` / `package.json`: Electron wrapper.

Scripts:
- `npm run dev` — start Electron app.
- `npm run build` — build Windows portable binary.

Coding notes:
- Preview outlines are white and reflect the selected style and width.
- Separate ImageSets mode exports one series per ROI as in the Python app.
- ZIP filenames include burned ROI names.

## Support and Development

### Technical Support
For technical issues or questions:
- Check browser compatibility (Chrome/Firefox recommended)
- Verify DICOM file format (uncompressed required)
- Ensure adequate system memory for large datasets

### Feature Requests
This tool is actively developed for research and educational applications. Feature requests and feedback are welcome for future development consideration.

## License

This project is licensed under the Varian Limited Use Software License Agreement (LUSLA).

---

**IMPORTANT DISCLAIMER**

**This software is provided for educational and research purposes only. It has not been validated for clinical use and should not be used for patient treatment planning or clinical decision-making. All results should be independently verified using clinically validated software before any clinical application.**
