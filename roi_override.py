# -*- coding: utf-8 -*-
"""
ROI Override Tool (concise)
- Select folder with CT series + 1 RTSTRUCT
- Choose ROIs and HU override (contour or fill)
- Writes new CT series (fresh UIDs) with overrides burned in
"""

import os
import glob
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from CTkListbox import CTkListbox

import pydicom
from pydicom.uid import generate_uid
import numpy as np
from PIL import Image, ImageDraw, ImageChops
from datetime import datetime

# ------------------------------
# Geometry helpers
# ------------------------------
def densify_contour(pts: np.ndarray, max_mm: float) -> np.ndarray:
    """Insert points so edges are ≤ max_mm apart (keeps order/closure)."""
    out = []
    for i in range(len(pts)):
        p0 = pts[i]; p1 = pts[(i+1) % len(pts)]
        seg_len = np.linalg.norm(p1 - p0)
        steps = max(int(np.ceil(seg_len / max_mm)), 1)
        for k in range(steps):
            out.append(p0 + (p1 - p0) * (k / steps))
    return np.vstack(out)

def polygon_area(poly: list[tuple[int,int]]) -> float:
    """Signed area magnitude (unused by burn-in; kept for reference)."""
    area = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i+1) % n]
        area += x0*y1 - x1*y0
    return 0.5 * area

# ------------------------------
# Core burn-in (kept orientation-agnostic as in your working version)
# ------------------------------
def run_roi_override(input_dir: str,
                     output_dir: str,
                     settings_list: list[dict]):
    # Keep original pixel scaling + dtype per slice
    orig_slopes, orig_intercepts, orig_dtypes = {}, {}, {}

    # Pick SeriesDescription from settings (Single mode: user entry)
    series_desc = settings_list[0].get("image_set_name",
                                       settings_list[0]["roi_name"])

    # ROI config map: {roi_name_lower: {contour/fill/uniform}}
    cfg_map = {
        s["roi_name"].lower(): {
            "contour": s["contour"],
            "fill":    s["fill"],
            "uniform": int(s["uniform"])
        }
        for s in settings_list
    }

    # Find CT + RS
    files = glob.glob(os.path.join(input_dir, "*.dcm"))
    ct_fs = [f for f in files if "CT" in os.path.basename(f).upper()]
    rs_fs = [f for f in files if "RS" in os.path.basename(f).upper()]
    if not ct_fs or not rs_fs:
        raise RuntimeError(f"Missing CT or RTSTRUCT in {input_dir}")

    # Load CTs → HU maps; assign new UIDs; index by z (string tag)
    ct_arrays, ct_ds = {}, {}
    study_uid  = generate_uid()
    series_uid = generate_uid()
    frame_uid  = generate_uid()

    for f in ct_fs:
        ds = pydicom.dcmread(f)
        raw = ds.pixel_array.copy()
        slope = float(getattr(ds, "RescaleSlope", 1.0))
        intercept = float(getattr(ds, "RescaleIntercept", 0.0))
        orig_slopes[f], orig_intercepts[f], orig_dtypes[f] = slope, intercept, raw.dtype

        hu = raw.astype(np.float32) * slope + intercept
        z = f"{float(ds.ImagePositionPatient[2]):.2f}".replace("-0.00","0.00")
        ct_arrays[z] = hu

        # New identity for the output series
        ds.StudyInstanceUID    = study_uid
        ds.SeriesInstanceUID   = series_uid
        ds.FrameOfReferenceUID = frame_uid
        ds.SOPInstanceUID      = generate_uid()
        ds.SeriesDescription   = series_desc
        ct_ds[z] = ds

    # Load RS + ROI numbers
    rs = pydicom.dcmread(max(rs_fs, key=os.path.getmtime))
    roi_nums = {r.ROIName.lower(): r.ROINumber for r in rs.StructureSetROISequence}
    to_do = [roi_nums[n] for n in cfg_map if n in roi_nums]

    # Point RS references at new CT series (not writing RS out, but consistent)
    first_for = next(iter(ct_ds.values())).FrameOfReferenceUID
    for ref in rs.ReferencedFrameOfReferenceSequence:
        ref.FrameOfReferenceUID = first_for
        for st in ref.RTReferencedStudySequence:
            st.ReferencedSOPInstanceUID = study_uid
            for se in st.RTReferencedSeriesSequence:
                se.SeriesInstanceUID = series_uid

    # Burn-in (per ROI → per slice); XOR fill keeps holes hollow
    for seq in rs.ROIContourSequence:
        if seq.ReferencedROINumber not in to_do or not hasattr(seq, "ContourSequence"):
            continue

        key = next(k for k,v in roi_nums.items() if v == seq.ReferencedROINumber)
        cfg = cfg_map[key]

        # Collect polygons by slice z
        polys_by_z: dict[str, list[list[tuple[int,int]]]] = {}
        for ctr in seq.ContourSequence:
            pts = np.array(ctr.ContourData).reshape(-1,3)
            pts = densify_contour(pts, max_mm=1.0)
            z = f"{pts[0,2]:.2f}".replace("-0.00","0.00")

            ds = ct_ds.get(z); hu = ct_arrays.get(z)
            if ds is None or hu is None:
                continue

            # Simple patient→pixel mapping (no orientation handling by design)
            poly = [(
                int((x - ds.ImagePositionPatient[0]) / ds.PixelSpacing[0]),
                int((y - ds.ImagePositionPatient[1]) / ds.PixelSpacing[1])
            ) for x,y,_ in pts]
            polys_by_z.setdefault(z, []).append(poly)

        # Apply for each slice
        for z, polys in polys_by_z.items():
            hu = ct_arrays[z]
            H, W = hu.shape

            # Contour-only = set outline points
            if cfg["contour"]:
                for poly in polys:
                    for x, y in poly:
                        if 0 <= x < W and 0 <= y < H:
                            hu[y, x] = cfg["uniform"]

            # Fill with even-odd (XOR) so inner holes remain air
            if cfg["fill"]:
                mask = Image.new("1", (W, H), 0)
                for poly in polys:
                    tmp = Image.new("1", (W, H), 0)
                    ImageDraw.Draw(tmp).polygon(poly, outline=1, fill=1)
                    mask = ImageChops.logical_xor(mask, tmp)
                hu[np.array(mask, dtype=bool)] = cfg["uniform"]

    # Save CTs (HU → raw), keep original scaling/dtype
    os.makedirs(output_dir, exist_ok=True)
    for f in ct_fs:
        ds_src = pydicom.dcmread(f)
        z = f"{float(ds_src.ImagePositionPatient[2]):.2f}".replace("-0.00","0.00")

        ds = ct_ds[z]
        hu = ct_arrays[z]
        slope = orig_slopes[f]; intercept = orig_intercepts[f]; dtype = orig_dtypes[f]

        raw_new = np.round((hu - intercept) / slope).astype(dtype)
        raw_new = np.clip(raw_new, np.iinfo(dtype).min, np.iinfo(dtype).max)
        ds.PixelData = raw_new.tobytes()

        ds.RescaleSlope     = slope
        ds.RescaleIntercept = intercept
        ds.WindowCenter     = int((hu.max() + hu.min()) / 2)
        ds.WindowWidth      = int(max(hu.max() - hu.min(), 1))

        ds.save_as(os.path.join(output_dir, f"CT.{z}.dcm"))

# ------------------------------
# GUI
# ------------------------------
class ROIApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("EzROIOverride")
        self.geometry("1200x800")
        try: self.state("zoomed")
        except: pass
        self.resizable(True, True)

        self._initial_set_name = None  # remember first suggested name
        self.rows = []

        # Layout
        self.grid_columnconfigure((0,1), weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left panel: folder + ROI list
        left = ctk.CTkFrame(self, border_width=1, corner_radius=8)
        left.grid(row=0, column=0, padx=10, pady=10, sticky="nswe")
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(2, weight=1)

        ctk.CTkButton(left, text="Select DICOM Folder", height=35,
                      command=self.pick_folder).grid(row=0, column=0, pady=(20,5))
        ctk.CTkLabel(left, text="Available ROIs").grid(row=1, column=0, pady=(5,5))

        self.listbox = CTkListbox(left, multiple_selection=True)
        self.listbox.grid(row=2, column=0, padx=10, pady=(0,5), sticky="nswe")

        ctk.CTkButton(left, text="+ Add Selected", height=35,
                      command=self.add_rows).grid(row=3, column=0, pady=(5,20))

        # Right panel: info + controls + table
        right = ctk.CTkFrame(self, border_width=1, corner_radius=8)
        right.grid(row=0, column=1, padx=10, pady=10, sticky="nswe")
        for c in range(7):
            right.grid_columnconfigure(c, weight=1, uniform="col", minsize=120)
        right.grid_rowconfigure(5, weight=1)

        self.status = ctk.CTkLabel(right, text="No folder selected", anchor="center")
        self.status.grid(row=0, column=0, columnspan=7, sticky="ew", pady=(20,5))
        self.summary = ctk.CTkLabel(right, text="", anchor="center")
        self.summary.grid(row=1, column=0, columnspan=7, sticky="ew", pady=(0,5))
        self.info_combined = ctk.CTkLabel(right, text="MRN: —    Patient: —    Study Date: —", anchor="center")
        self.info_combined.grid(row=2, column=0, columnspan=7, sticky="ew", pady=(0,10))

        # Series name (used in Single mode)
        name_row = ctk.CTkFrame(right, fg_color="transparent")
        name_row.grid(row=3, column=0, columnspan=7, sticky="ew", pady=(0,15))
        name_row.grid_columnconfigure((0,1), weight=1)
        ctk.CTkLabel(name_row, text="Image Set Name:").grid(row=0, column=0, sticky="e", padx=(0,5))
        self.set_name = ctk.CTkEntry(name_row, width=200, height=25, justify="center", font=("Arial", 10))
        self.set_name.grid(row=0, column=1, sticky="w", padx=(5,0))

        # Table headers
        for i, txt in enumerate(["ROI","Contour","Fill","Preset HU","Manual HU","Remove","ImageSet Name"]):
            ctk.CTkLabel(right, text=txt, anchor="center").grid(row=4, column=i, sticky="nsew", padx=5, pady=(0,5))

        # Rows (scrollable)
        self.rows_frame = ctk.CTkScrollableFrame(right)
        self.rows_frame.grid(row=5, column=0, columnspan=7, sticky="nswe", padx=5, pady=(0,10))
        for c in range(7):
            self.rows_frame.grid_columnconfigure(c, weight=1, uniform="col", minsize=120)

        # Mode + action
        rb = ctk.CTkFrame(right)
        rb.grid(row=6, column=0, columnspan=7, sticky="ew", padx=5, pady=(5,5))
        rb.grid_columnconfigure((0,1), weight=1)
        self.mode = tk.StringVar(value="combine")  # "combine"=single series, "separate"=per-ROI series
        ctk.CTkRadioButton(rb, text="Single ImageSet",   variable=self.mode, value="combine").grid(row=0, column=0, sticky="e", padx=(0,20))
        ctk.CTkRadioButton(rb, text="Separate ImageSets",variable=self.mode, value="separate").grid(row=0, column=1, sticky="w", padx=(20,0))
        self.mode.trace_add("write", lambda *a: self._on_mode_change())

        ctk.CTkButton(right, text="Burn In ROIs", height=35, command=self.burn_in)\
            .grid(row=7, column=0, columnspan=7, pady=(5,5))

        self.progress = ctk.CTkProgressBar(right)
        self.progress.grid(row=8, column=0, columnspan=7, sticky="ew", padx=5, pady=(0,20))

        # HU validator
        self._vc = (self.register(self._validate_hu), '%P')

    # ------------------------------
    # GUI helpers
    # ------------------------------
    def _validate_hu(self, P: str) -> bool:
        """Allow blank/'-'/integer (for manual HU)."""
        return (P == "" or P == "-" or P.isdigit() or (P.startswith("-") and P[1:].isdigit()))

    def pick_folder(self):
        """Choose folder, verify RS↔CT linkage, list ROIs."""
        fd = filedialog.askdirectory()
        if not fd: return
        self.folder = fd

        files = glob.glob(os.path.join(fd, "*.dcm"))
        ct_fs = [f for f in files if "CT" in os.path.basename(f).upper()]
        rs_fs = [f for f in files if "RS" in os.path.basename(f).upper()]
        if not ct_fs:
            return messagebox.showerror("Error", "Folder must contain at least one CT (.dcm) file.")
        if len(rs_fs) != 1:
            return messagebox.showerror("Error", "Folder must contain exactly one RTSTRUCT (.dcm) file.")

        rsd = pydicom.dcmread(rs_fs[0])
        first_ct = pydicom.dcmread(ct_fs[0])

        # RS must reference the same Study as CT
        ct_study_uid = getattr(first_ct, "StudyInstanceUID", None)
        ref_uids = []
        for ref in getattr(rsd, "ReferencedFrameOfReferenceSequence", []):
            for st in getattr(ref, "RTReferencedStudySequence", []):
                uid = getattr(st, "ReferencedSOPInstanceUID", None)
                if uid: ref_uids.append(uid)
        if ct_study_uid not in ref_uids:
            return messagebox.showerror("Error", "RTSTRUCT does not reference the same Study as your CT images.")

        # Header info
        self.status.configure(text=self.folder)
        pid = getattr(first_ct, "PatientID", "—")
        pname = getattr(first_ct, "PatientName", "—")
        date = getattr(first_ct, "StudyDate", "")
        if len(date)==8: date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
        self.info_combined.configure(text=f"MRN: {pid}    Patient: {pname}    Study Date: {date}")
        self.summary.configure(text=f"Loaded {len(ct_fs)} CT images, 1 RTSTRUCT")

        # Populate ROI list
        self.listbox.delete(0, tk.END)
        for seq in rsd.StructureSetROISequence:
            self.listbox.insert(tk.END, seq.ROIName)

    def _on_mode_change(self, *args):
        """Enable the correct name fields per mode."""
        mode = self.mode.get()
        if mode == "combine":
            self.set_name.configure(state="normal")
            if not self.set_name.get().strip() and self._initial_set_name:
                self.set_name.insert(0, self._initial_set_name)
        else:
            cur = self.set_name.get().strip()
            if cur and not self._initial_set_name:
                self._initial_set_name = cur
            self.set_name.delete(0, tk.END)
            self.set_name.configure(state="disabled")

        for row in self.rows:
            ent = row["ent_name"]
            if mode == "separate":
                ent.configure(state="normal")
                if not row["isetname"].get():
                    row["isetname"].set(row["name"])  # default to ROI name
            else:
                ent.delete(0, tk.END)
                ent.configure(state="disabled")

    def add_rows(self):
        """Add selected ROIs (no duplicates)."""
        for idx in self.listbox.curselection():
            name = self.listbox.get(idx)
            if any(r["name"] == name for r in self.rows):
                continue
            self._add_row(name)
        self._lock_minsize()
        self._on_mode_change()

    def _add_row(self, name):
        """Create one table row."""
        r = len(self.rows)
        if r == 0 and not self.set_name.get().strip():
            self._initial_set_name = name
            self.set_name.insert(0, name)

        ctk.CTkLabel(self.rows_frame, text=name).grid(row=r, column=0, pady=10, padx=(0,5))

        cv = tk.BooleanVar()
        ctk.CTkCheckBox(self.rows_frame, text="", variable=cv,
                        command=lambda: fv.set(False)).grid(row=r, column=1, pady=10, padx=(44,0))

        fv = tk.BooleanVar()
        ctk.CTkCheckBox(self.rows_frame, text="", variable=fv,
                        command=lambda: cv.set(False)).grid(row=r, column=2, pady=10, padx=(50,0))

        uv = tk.StringVar()
        combo = ctk.CTkComboBox(
            self.rows_frame, width=160, height=30,
            values=["Air (-1000 HU)", "Water (0 HU)", "Bolus (50 HU)",
                    "Titanium (7000 HU)", "Co-Cr-Mo (10000 HU)",
                    "Stainless Steel (11000 HU)", "Manual Entry"],
            command=lambda ch: self._on_preset(ch, uv, ent_manual)
        )
        combo.set("Water (0 HU)")
        combo.grid(row=r, column=3, pady=10, padx=(8,0))

        ent_manual = ctk.CTkEntry(self.rows_frame, textvariable=uv,
                                  validate="key", validatecommand=self._vc,
                                  state="disabled")
        ent_manual.grid(row=r, column=4, pady=10, padx=(18,0))

        ctk.CTkButton(self.rows_frame, text="Remove", fg_color="red",
                      command=lambda i=r: self._remove(i)).grid(row=r, column=5, pady=10, padx=(28))

        # Per-row ImageSet Name (used in Separate mode)
        nv = tk.StringVar()
        ent_name = ctk.CTkEntry(self.rows_frame, textvariable=nv,
                                placeholder_text="ImageSet Name", state="disabled")
        ent_name.grid(row=r, column=6, pady=10, padx=(31,0))

        self.rows.append({
            "name":     name,
            "contour":  cv,
            "fill":     fv,
            "uniform":  uv,        # manual HU when "Manual Entry"
            "preset":   combo,     # preset label for non-manual
            "ent_name": ent_name,  # per-row ImageSet Name entry
            "isetname": nv         # per-row ImageSet Name value
        })

    def _on_preset(self, choice: str, uv: tk.StringVar, ent_manual: ctk.CTkEntry):
        """Toggle manual HU entry; leave it blank when disabled."""
        if choice == "Manual Entry":
            ent_manual.configure(state="normal")
            if not uv.get().strip():
                uv.set("0")
        else:
            uv.set("")  # keep empty when using a preset
            ent_manual.delete(0, tk.END)
            ent_manual.configure(state="disabled")

    def _remove(self, idx: int):
        """Delete the row and shift the grid up."""
        for w in self.rows_frame.grid_slaves(row=idx):
            w.destroy()
        self.rows.pop(idx)
        for r in range(idx, len(self.rows)):
            for w in self.rows_frame.grid_slaves(row=r+1):
                w.grid_configure(row=r)
        self._lock_minsize()
        self._on_mode_change()

    def _lock_minsize(self):
        """Freeze minimum window size to current layout."""
        self.update_idletasks()
        self.minsize(self.winfo_reqwidth(), self.winfo_reqheight())

    def burn_in(self):
        """Build settings, fix naming, run burn-in."""
        messagebox.showinfo("Burn-in Started",
                            "The burn-in process has started.\nYou will be notified when it completes.")

        if not hasattr(self, "folder") or not self.rows:
            return messagebox.showwarning("Warn", "Select a DICOM folder and at least one ROI.")
        for r in self.rows:
            if not (r["contour"].get() or r["fill"].get()):
                return messagebox.showerror("Error", f"ROI '{r['name']}' needs Contour or Fill.")

        base_out = filedialog.askdirectory(title="Select base output folder", initialdir=self.folder)
        if not base_out: return

        # Naming for Single mode
        mode = self.mode.get()
        single_series_name = None
        if mode == "combine":
            single_series_name = self.set_name.get().strip()
            if not single_series_name:
                return messagebox.showerror("Error", "Please enter an Image Set Name for Single ImageSet mode.")

        # Build settings
        settings, roi_names = [], []
        for r in self.rows:
            roi_names.append(r["name"])
            choice = r["preset"].get()
            if choice == "Manual Entry":
                raw = r["uniform"].get().strip()
                try: uniform = int(raw)
                except ValueError:
                    return messagebox.showerror("Error", f"Manual HU for {r['name']} must be integer")
            else:
                uniform = int(choice.split("(")[1].split()[0])

            # Use top box for Single; per-row (fallback to ROI name) for Separate
            image_set_name = (single_series_name if mode == "combine"
                              else (r["isetname"].get().strip() or r["name"]))

            settings.append({
                "roi_name":       r["name"],
                "contour":        r["contour"].get(),
                "fill":           r["fill"].get(),
                "uniform":        uniform,
                "image_set_name": image_set_name
            })

        # Output parent
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        parent = os.path.join(base_out, f"ROIOverrideOutput_{ts}")
        os.makedirs(parent, exist_ok=True)
        self.summary.configure(text=f"Output → {parent}")

        # Tasks
        tasks = []
        if mode == "combine":
            safe = "_".join(n.replace(" ", "_") for n in roi_names)
            tasks.append((settings, os.path.join(parent, f"Combined_{safe}")))
        else:
            for s in settings:
                tasks.append(([s], os.path.join(parent, s["image_set_name"])))

        # Run
        total = len(tasks)
        for i, (cfg, out) in enumerate(tasks):
            os.makedirs(out, exist_ok=True)
            run_roi_override(self.folder, out, cfg)
            self.progress.set((i+1)/total)
            self.update_idletasks()

        messagebox.showinfo("Done", f"Burn-in complete!\nAll output saved under:\n{parent}")
        self.destroy()

# ------------------------------
# Main
# ------------------------------
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    ROIApp().mainloop()
