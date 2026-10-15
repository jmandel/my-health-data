# /// script
# requires-python = ">=3.10"
# dependencies = ["pydicom==3.0.1"]
# ///
"""De-identifies Josh's imaging exports into the sample studies in this
directory ("Josh Example").

    uv run imaging/deid.py --out imaging SOURCE_DIR [SOURCE_DIR ...]

SOURCE_DIRs are the unzipped CD/portal exports. The script holds no
personal data: the identifiers it must remove are read from the inputs at
run time, and the run fails if any of them is still present in an output.

Rules (from DICOM PS3.15 Basic Application Level Confidentiality Profile,
keeping dates, descriptions and device type, as the owner chose):
- PatientName Example^Josh; PatientID JEXAMPLE01; PatientBirthDate reduced
  to 1 January of the birth year; PatientAge, PatientSex, PatientSize and
  PatientWeight kept.
- AccessionNumber and StudyID: a fixed fake value per study (STUDIES).
- Every other person name, at any depth, emptied.
- Removed: institution, department and station names and addresses,
  device serial numbers and plate/gantry IDs, phone numbers, other patient
  IDs and names, issuer of patient ID, patient address, military rank and
  branch, ethnic group, occupation, patient history and comments, order,
  request and procedure-step identifiers, study and image comments, reason
  for study, the Original Attributes Sequence, references to other
  patients, studies and procedure steps, and all private attributes.
- Kept: study, series, acquisition and content dates and times;
  descriptions; protocol names; manufacturer and model; technical
  attributes; pixel data, byte for byte.
- Instance-identifying UIDs are replaced by deterministic 2.25 UIDs.
  Coding-scheme, SOP Class, transfer syntax and implementation UIDs stay.
- Screen captures and scanned documents are dropped (DROP_SERIES): they
  show the patient's name and identifiers in the pixels.

Output: <out>/<study>/<series number>-<series description>.tgz, one
archive per series, each holding <study>/<series>/<instance>.dcm.
"""

import argparse
import hashlib
import io
import os
import re
import sys
import tarfile
import gzip
from collections import defaultdict

import pydicom
from pydicom.config import settings
from pydicom.dataelem import DataElement
from pydicom.tag import Tag

settings.reading_validation_mode = 1  # warn, keep the original values
settings.writing_validation_mode = 1

UID_NAMESPACE = "jmandel/my-health-data/imaging/v1"
PATIENT_NAME = "Example^Josh"
PATIENT_ID = "JEXAMPLE01"

# Studies are recognised by date and description (not identifying).
STUDIES = [
    {"date": "20200729", "description": "BRAIN 7/29/20", "id": "mri-brain-2020", "accession": "EXMRI2020"},
    {"date": "20121009", "description": "CT ABDOMEN/PELVIS W CON", "id": "ct-abdomen-pelvis-2012", "accession": "EXCT2012"},
    {"date": "20121010", "description": "WRIST LEFT AP LAT & OBL", "id": "xr-wrist-left-2012", "accession": "EXCR2012A"},
    {"date": "20121010", "description": "HAND AND WRIST RT", "id": "xr-hand-wrist-right-2012", "accession": "EXCR2012B"},
    {"date": "20121010", "description": "HAND RGHT PA LAT OBL MIN 3 VW", "id": "xr-hand-right-2012", "accession": "EXCR2012C"},
]

# Series dropped because their pixels show identifying text.
DROP_SERIES = {
    ("ct-abdomen-pelvis-2012", "Dose Report"): "screen capture showing patient name, ID and accession number",
    ("ct-abdomen-pelvis-2012", "Clinical Documents"): "scanned paper document",
    ("mri-brain-2020", "ViewportCapture-MR"): "viewer screen captures showing patient name and demographics",
}

REMOVE = {Tag(t) for t in [
    0x00080080, 0x00080081, 0x00080082, 0x00080092, 0x00080094, 0x00080096, 0x00081010, 0x00081040,
    0x00081049, 0x00081052, 0x00081062, 0x00081072, 0x00081080, 0x00081084, 0x00081110, 0x00081111,
    0x00081120, 0x00084000, 0x00100021, 0x00100024, 0x00100032, 0x00100050, 0x00101000, 0x00101001,
    0x00101002, 0x00101005, 0x00101040, 0x00101060, 0x00101080, 0x00101081, 0x00101090, 0x00102000,
    0x00102110, 0x00102150, 0x00102152, 0x00102154, 0x00102160, 0x00102180, 0x001021B0, 0x001021F0,
    0x00102203, 0x00104000, 0x00181000, 0x00181004, 0x00181005, 0x00181007, 0x00181008, 0x0018700A,
    0x00184000, 0x00204000, 0x00321020, 0x00321021, 0x00321030, 0x00321033, 0x00324000, 0x00380010,
    0x00380011, 0x00380300, 0x00380400, 0x00380500, 0x00384000, 0x00400001, 0x00400009, 0x00400010,
    0x00400011, 0x00400241, 0x00400242, 0x00400243, 0x00400253, 0x00400275, 0x00400280, 0x00401001,
    0x00401010, 0x00401400, 0x00402001, 0x00402008, 0x00402009, 0x00402010, 0x00402016, 0x00402017,
    0x00402400, 0x00403001, 0x04000561, 0x00880140,
]}
# Emptied: Hitachi MR writes an opaque number in Position Reference
# Indicator; it is not needed and could be a site counter.
EMPTY = {Tag(0x00201040)}
KEEP_UIDS = {Tag(t) for t in [0x0008010C, 0x00020012]}  # coding scheme, implementation class
REGISTRY = "1.2.840.10008."


def new_uid(uid: str) -> str:
    h = bytearray(hashlib.sha256(f"{UID_NAMESPACE}:{uid}".encode()).digest()[:16])
    h[6] = (h[6] & 0x0F) | 0x50
    h[8] = (h[8] & 0x3F) | 0x80
    return "2.25." + str(int.from_bytes(h, "big"))


def clean(ds, top: bool) -> None:
    ds.remove_private_tags()
    for elem in list(ds):
        tag = elem.tag
        if tag in REMOVE or (tag.group & 0xFF00) in (0x5000, 0x6000):
            del ds[tag]
            continue
        if elem.VR == "SQ":
            for item in elem.value:
                clean(item, False)
            continue
        if (elem.VR == "PN" and not (top and tag == Tag(0x00100010))) or tag in EMPTY:
            elem.value = ""
        elif elem.VR == "UI" and tag not in KEEP_UIDS and elem.value:
            vals = elem.value if elem.VM > 1 else [elem.value]
            mapped = [v if str(v).startswith(REGISTRY) else new_uid(str(v)) for v in vals]
            elem.value = mapped if elem.VM > 1 else mapped[0]


def phi_terms(ds) -> dict:
    """Identifying values read from a source file, by category."""
    terms = defaultdict(set)
    name = str(ds.get("PatientName", ""))
    for part in re.split(r"[\^ =,]+", name):
        if len(part) >= 3:
            terms["name"].add(part.upper())
    for kw in ["PatientID", "OtherPatientIDs", "AccessionNumber", "StudyID", "IssuerOfPatientID",
               "RequestedProcedureID", "PerformedProcedureStepID", "FillerOrderNumberImagingServiceRequest",
               "DeviceSerialNumber", "PlateID", "GantryID"]:
        v = ds.get(kw)
        for x in (v if isinstance(v, (list, pydicom.multival.MultiValue)) else [v]):
            if x and len(str(x).strip()) >= 4:
                terms["id"].add(str(x).strip().upper())
    dob = str(ds.get("PatientBirthDate", "") or "")
    if re.fullmatch(r"\d{8}", dob):
        y, m, d = dob[:4], dob[4:6], dob[6:]
        mon = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"][int(m) - 1]
        if m + d != "0101":
            for f in [dob, f"{y}-{m}-{d}", f"{m}/{d}/{y}", f"{int(m)}/{int(d)}/{y}", f"{m}/{d}/{y[2:]}",
                      f"{int(m)}/{int(d)}/{y[2:]}", f"{d}-{mon}-{y}", f"{mon} {d} {y}", f"{mon} {int(d)}, {y}",
                      f"{d}.{m}.{y}"]:
                terms["dob"].add(f.upper())
    return terms


def tgz(files: list[tuple[str, bytes]]) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        dirs = sorted({os.path.dirname(n) for n, _ in files} | {os.path.dirname(os.path.dirname(n)) for n, _ in files})
        for d in dirs:
            if not d:
                continue
            ti = tarfile.TarInfo(d)
            ti.type, ti.mode, ti.mtime = tarfile.DIRTYPE, 0o755, 0
            tar.addfile(ti)
        for name, data in sorted(files):
            ti = tarfile.TarInfo(name)
            ti.size, ti.mode, ti.mtime = len(data), 0o644, 0
            tar.addfile(ti, io.BytesIO(data))
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", mtime=0, filename="", compresslevel=9) as gz:
        gz.write(raw.getvalue())
    return out.getvalue()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("sources", nargs="+")
    a = ap.parse_args()

    terms = defaultdict(set)
    series = defaultdict(list)
    dropped = defaultdict(int)
    skipped = 0
    seen = {}  # SOP Instance UID -> file hash; the exports repeat some files
    duplicates = 0
    for root in a.sources:
        for dp, _, fn in os.walk(root):
            for f in sorted(fn):
                path = os.path.join(dp, f)
                try:
                    ds = pydicom.dcmread(path)
                    ds.SOPInstanceUID
                except Exception:
                    skipped += 1
                    continue
                digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
                if ds.SOPInstanceUID in seen:
                    if seen[ds.SOPInstanceUID] != digest:
                        sys.exit(f"two different files share a SOP Instance UID: {path}")
                    duplicates += 1
                    continue
                seen[ds.SOPInstanceUID] = digest
                for k, v in phi_terms(ds).items():
                    terms[k] |= v
                study = next((s for s in STUDIES if str(ds.get("StudyDate")) == s["date"] and str(ds.get("StudyDescription")) == s["description"]), None)
                if study is None:
                    sys.exit(f"unrecognised study in {path}: add it to STUDIES")
                desc = str(ds.get("SeriesDescription", ""))
                if (study["id"], desc) in DROP_SERIES:
                    dropped[(study["id"], desc)] += 1
                    continue

                birth = str(ds.get("PatientBirthDate", "") or "")
                pixel_before = ds.PixelData if "PixelData" in ds else None
                clean(ds, True)
                clean(ds.file_meta, True)
                ds.PatientName = PATIENT_NAME
                ds.PatientID = PATIENT_ID
                if re.fullmatch(r"\d{8}", birth):
                    ds.PatientBirthDate = birth[:4] + "0101"
                ds.AccessionNumber = study["accession"]
                ds.StudyID = study["accession"]
                if (ds.PixelData if "PixelData" in ds else None) != pixel_before:
                    sys.exit(f"pixel data changed in {path}")
                buf = io.BytesIO()
                ds.save_as(buf, enforce_file_format=True)
                num = int(ds.get("SeriesNumber") or 0)
                slug = re.sub(r"[^A-Za-z0-9]+", "-", desc).strip("-") or "series"
                inst = int(ds.get("InstanceNumber") or 0)
                series[(study["id"], f"{num:04d}-{slug}")].append((inst, ds.SOPInstanceUID, buf.getvalue()))

    # Guard: no identifying value from any source may appear in any output.
    leaks = defaultdict(set)
    for key, files in series.items():
        for _, _, data in files:
            text = data.decode("latin-1").upper()
            ds_out = pydicom.dcmread(io.BytesIO(data))
            attr_text = "\n".join(str(e.value).upper() for e in ds_out.iterall() if e.VR not in ("UI", "OB", "OW", "UN", "SQ"))
            for cat, vals in terms.items():
                for v in vals:
                    # Short all-digit values also occur by chance inside the new
                    # 2.25 UIDs and in binary pixel data, so those are checked
                    # against the text attributes only; everything else
                    # against every byte of the file.
                    short_number = v.isdigit() and len(v) < 8
                    if v in (attr_text if short_number else text):
                        # Report where (attribute or byte offset), never the value.
                        out = pydicom.dcmread(io.BytesIO(data))
                        attrs = [e.keyword or str(e.tag) for e in out.iterall() if e.tag != Tag(0x7FE00010) and v in str(e.value).upper()]
                        leaks[cat].add(f"{key[0]}/{key[1]}: {attrs or 'pixel data offset ' + str(text.index(v))}")
    if leaks:
        sys.exit("identifying values still present in outputs: " + "; ".join(f"{k}: {sorted(v)[:5]}" for k, v in leaks.items()))

    for (study_id, slug), files in sorted(series.items()):
        files.sort()
        names = [(f"{study_id}/{slug}/{i:04d}-{uid[-8:]}.dcm", data) for i, uid, data in files]
        d = os.path.join(a.out, study_id)
        os.makedirs(d, exist_ok=True)
        blob = tgz(names)
        with open(os.path.join(d, f"{slug}.tgz"), "wb") as fh:
            fh.write(blob)
        print(f"{study_id}/{slug}.tgz  {len(files)} instances  {len(blob) / 1e6:.1f} MB")
    for (sid, desc), n in sorted(dropped.items()):
        print(f"dropped {sid} '{desc}': {n} instance(s): {DROP_SERIES[(sid, desc)]}")
    print(f"non-DICOM files skipped: {skipped}; identical duplicate files skipped: {duplicates}; identifying values checked: "
          + ", ".join(f"{k} {len(v)}" for k, v in sorted(terms.items())) + "; none found in outputs")


if __name__ == "__main__":
    main()
