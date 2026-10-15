"""Synthetic stand-ins for the series deid.py drops because their pixels
show identifying text. Each is rebuilt from scratch with the same layout
and information, showing "Josh Example" and the sample identifiers.

Called by deid.py. Nothing here holds personal data: identifying values
are never needed, because every rendered string comes from the sample
identity below, from the de-identified headers, or from the non-identifying
constants in this file (dose values, clinical facts on the order form).

To add a reconstruction (or a new synthetic object), write a function
taking a Context and returning a list of (dataset, comment) pairs, and add
it to BUILDERS. deid.py cleans each returned dataset with the same rules as
every other file, sets ImageComments to the comment, and writes it.
"""

import math
import os
from dataclasses import dataclass, field

import numpy as np
import pydicom
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.uid import generate_uid
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")

# Sample identity, as written into the de-identified headers.
NAME_DISPLAY = "EXAMPLE,JOSH"
NAME_SPACED = "EXAMPLE JOSH"
PATIENT_ID = "JEXAMPLE01"

# Fictional people and places used on the reconstructed objects.
FACILITY = ("Example Medical Center", "Sample City,California")
MRI_SITE = "Example Open MRI"
CLINICIAN = "Example, Casey M"
CLINICIAN_SHORT = "example"
CLINICIAN_PHONE = "4155550100"
ORDER_CLERK = "EXAMPLE,JORDA"  # the form truncates names to 13 characters
STAFF_INITIALS = "RTX"
ACCOUNT_NUMBER = "90000001"
FINANCIAL_CLASS = "EXAMPLE HMO"  # insurance plan line on the order form
ORDER_NUMBER = "I0000001"
CAMPUS_CODES = (("NOR", "CEN", "SOU"), ("RP", "NRP", "PRP"))

# Values from the CT dose screen that are not in any header (not
# identifying). CTDIvol is read from the header at run time.
DOSE_SCAN_RANGE = "I65.000-I529.375"
DOSE_DLP = "562.59"
DOSE_PHANTOM = "Body 32"


@dataclass
class Context:
    """What builders get: dropped originals and the kept source files, by
    (study id, SeriesDescription). Datasets are the originals (not yet
    de-identified); builders must not copy identifying text from them."""
    dropped: dict = field(default_factory=dict)  # (study, desc) -> [Dataset]
    kept: dict = field(default_factory=dict)  # (study, desc) -> [Dataset]
    accession: dict = field(default_factory=dict)  # study id -> fake accession
    birth_year: str = ""


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def to_mono(img: Image.Image, maxval: int, dtype) -> bytes:
    a = np.asarray(img.convert("L"), dtype=np.float64) / 255.0 * maxval
    return np.round(a).astype(dtype).tobytes()


# ---------------------------------------------------------------- CT dose screen


def dose_report(ctx: Context):
    out = []
    for ds in ctx.dropped.get(("ct-abdomen-pelvis-2012", "Dose Report"), []):
        w, h = int(ds.Columns), int(ds.Rows)
        img = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(img)
        f = font("DejaVuSans-Bold.ttf", 12)
        ctdi = next((f"{float(it.CTDIvol):.2f}" for it in ds.get("ExposureDoseSequence", []) if "CTDIvol" in it), "")
        date = pydicom.valuerep.DA(str(ds.StudyDate))
        left = [f"Patient Name: {NAME_SPACED}", f"Accession Number: {ctx.accession['ct-abdomen-pelvis-2012']}",
                f"Patient ID: {PATIENT_ID}", f"Exam Description: {ds.get('PerformedProcedureStepDescription', 'CT ABD/PELVIS W')}"]
        right = [f"Exam no: {ctx.accession['ct-abdomen-pelvis-2012']}", date.strftime("%b %d %Y"), str(ds.get("ManufacturerModelName", "") or "LightSpeed VCT")]
        for i, t in enumerate(left):
            d.text((4, 6 + 20 * i), t, font=f, fill=255)
        for i, t in enumerate(right):
            d.text((w - 4, 6 + 20 * i), t, font=f, fill=255, anchor="ra")
        d.text((w // 2, 114), "Dose Report", font=f, fill=255, anchor="ma")
        cols = [(28, "Series"), (90, "Type"), (190, "Scan Range\n(mm)"), (298, "CTDIvol\n(mGy)"), (365, "DLP\n(mGy-cm)"), (464, "Phantom\ncm")]
        for x, t in cols:
            lines = t.split("\n")
            y0 = 144 if len(lines) == 1 else 136
            for j, line in enumerate(lines):
                d.text((x, y0 + 15 * j), line, font=f, fill=255, anchor="ma")
        rows = [["1", "Scout", "-", "-", "-", "-"], ["2", "Helical", DOSE_SCAN_RANGE, ctdi, DOSE_DLP, DOSE_PHANTOM]]
        for r, row in enumerate(rows):
            for (x, _), t in zip(cols, row):
                d.text((x, 174 + 22 * r), t, font=f, fill=255, anchor="ma")
        d.text((340, 218), "Total Exam DLP:", font=f, fill=255, anchor="ra")
        d.text((365, 218), DOSE_DLP, font=f, fill=255, anchor="ma")
        d.text((w // 2, 260), "1/1", font=f, fill=255, anchor="ma")
        img = img.point(lambda v: 255 if v >= 128 else 0)  # the original is two-level
        ds.PixelData = to_mono(img, 1023, np.int16)
        ds.SeriesDescription = "Dose Report (reconstructed)"
        out.append((ds, "Reconstructed: dose screen redrawn with the sample patient's identifiers; dose values as on the original screen."))
    return out


def dose_sr(ctx: Context):
    """A CT Radiation Dose SR (TID 10011) built from the dose screen and the
    image headers. The CD has no dose SR; this one is synthetic."""
    screens = ctx.dropped.get(("ct-abdomen-pelvis-2012", "Dose Report"), [])
    if not screens:
        return []
    scr = screens[0]
    axial = ctx.kept.get(("ct-abdomen-pelvis-2012", "ABD/PEL"), [])
    scout = ctx.kept.get(("ct-abdomen-pelvis-2012", "SCOUT"), [])
    ref = axial[0] if axial else scr

    def code(value, scheme, meaning):
        c = Dataset()
        c.CodeValue, c.CodingSchemeDesignator, c.CodeMeaning = value, scheme, meaning
        return c

    def item(rel, vtype, concept, **kw):
        it = Dataset()
        it.RelationshipType = rel
        it.ValueType = vtype
        it.ConceptNameCodeSequence = Sequence([code(*concept)])
        if vtype == "CONTAINER":
            it.ContinuityOfContent = "SEPARATE"
            it.ContentSequence = Sequence(kw.get("children", []))
        elif vtype == "CODE":
            it.ConceptCodeSequence = Sequence([code(*kw["value"])])
        elif vtype == "NUM":
            mv = Dataset()
            mv.NumericValue = kw["value"]
            mv.MeasurementUnitsCodeSequence = Sequence([code(kw["unit"], "UCUM", kw["unit"])])
            it.MeasuredValueSequence = Sequence([mv])
        elif vtype == "TEXT":
            it.TextValue = kw["value"]
        elif vtype == "UIDREF":
            it.UID = kw["value"]
        elif vtype == "DATETIME":
            it.DateTime = kw["value"]
        return it

    def uid(tag: str) -> str:
        # Placeholders: deid.py remaps every UID deterministically.
        return generate_uid(entropy_srcs=[str(scr.SOPInstanceUID), tag])

    events = []
    for i, ev in enumerate(scr.get("ExposureDoseSequence", [])):
        spiral = str(ev.get("AcquisitionType", "")) == "SPIRAL"
        params = [
            item("CONTAINS", "NUM", ("113824", "DCM", "Exposure Time"), value=f"{float(ev.ExposureTime) / 1000:.3f}", unit="s"),
            item("CONTAINS", "NUM", ("113826", "DCM", "Nominal Single Collimation Width"), value=f"{float(ref.get('SingleCollimationWidth', ev.SingleCollimationWidth)):.3f}", unit="mm"),
            item("CONTAINS", "NUM", ("113827", "DCM", "Nominal Total Collimation Width"), value=f"{float(ref.get('TotalCollimationWidth', ev.TotalCollimationWidth)) if spiral else float(scout[0].TotalCollimationWidth) if scout else 5.0:.3f}", unit="mm"),
            item("CONTAINS", "NUM", ("113823", "DCM", "Number of X-Ray Sources"), value="1", unit="{X-Ray sources}"),
            item("CONTAINS", "CONTAINER", ("113831", "DCM", "CT X-Ray Source Parameters"), children=[
                item("CONTAINS", "TEXT", ("113832", "DCM", "Identification of the X-Ray Source"), value="A"),
                item("CONTAINS", "NUM", ("113733", "DCM", "KVP"), value=str(ev.KVP), unit="kV"),
                item("CONTAINS", "NUM", ("113833", "DCM", "Maximum X-Ray Tube Current"), value=f"{float(ev.XRayTubeCurrentInuA) / 1000:.1f}", unit="mA"),
                item("CONTAINS", "NUM", ("113734", "DCM", "X-Ray Tube Current"), value=f"{float(ev.XRayTubeCurrentInuA) / 1000:.1f}", unit="mA"),
            ]),
        ]
        if spiral:
            params.insert(3, item("CONTAINS", "NUM", ("113828", "DCM", "Pitch Factor"), value=f"{float(ev.SpiralPitchFactor):.3f}", unit="{ratio}"))
            lo, hi = [float(x.lstrip("IS")) for x in DOSE_SCAN_RANGE.split("-")]
            params.insert(1, item("CONTAINS", "NUM", ("113825", "DCM", "Scanning Length"), value=f"{abs(hi - lo):.3f}", unit="mm"))
        children = [
            item("CONTAINS", "TEXT", ("125203", "DCM", "Acquisition Protocol"), value=str(scr.get("ProtocolName", ""))),
            item("CONTAINS", "CODE", ("123014", "DCM", "Target Region"), value=("818981001", "SCT", "Abdomen")),
            item("CONTAINS", "CODE", ("113820", "DCM", "CT Acquisition Type"),
                 value=("116152004", "SCT", "Spiral Acquisition") if spiral else ("113805", "DCM", "Constant Angle Acquisition")),
            item("CONTAINS", "UIDREF", ("113769", "DCM", "Irradiation Event UID"), value=uid(f"event{i}")),
            item("CONTAINS", "CONTAINER", ("113822", "DCM", "CT Acquisition Parameters"), children=params),
        ]
        if spiral:
            children.append(item("CONTAINS", "CONTAINER", ("113829", "DCM", "CT Dose"), children=[
                item("CONTAINS", "NUM", ("113830", "DCM", "Mean CTDIvol"), value=f"{float(ev.CTDIvol):.2f}", unit="mGy"),
                item("CONTAINS", "CODE", ("113835", "DCM", "CTDIw Phantom Type"), value=("113691", "DCM", "IEC Body Dosimetry Phantom")),
                item("CONTAINS", "NUM", ("113838", "DCM", "DLP"), value=DOSE_DLP, unit="mGy.cm"),
            ]))
        events.append(item("CONTAINS", "CONTAINER", ("113819", "DCM", "CT Acquisition"), children=children))

    start = f"{scr.StudyDate}{str(scout[0].AcquisitionTime).split('.')[0] if scout else scr.StudyTime}"
    root = [
        item("HAS CONCEPT MOD", "CODE", ("121058", "DCM", "Procedure reported"), value=("77477000", "SCT", "Computed Tomography X-Ray")),
        item("HAS OBS CONTEXT", "CODE", ("121005", "DCM", "Observer Type"), value=("121007", "DCM", "Device")),
        item("HAS OBS CONTEXT", "UIDREF", ("121012", "DCM", "Device Observer UID"), value=uid("device")),
        item("HAS OBS CONTEXT", "DATETIME", ("113809", "DCM", "Start of X-Ray Irradiation"), value=start),
        item("CONTAINS", "CODE", ("113705", "DCM", "Scope of Accumulation"), value=("113014", "DCM", "Study")),
        item("CONTAINS", "CONTAINER", ("113811", "DCM", "CT Accumulated Dose Data"), children=[
            item("CONTAINS", "NUM", ("113812", "DCM", "Total Number of Irradiation Events"), value=str(len(events)), unit="{events}"),
            item("CONTAINS", "NUM", ("113813", "DCM", "CT Dose Length Product Total"), value=DOSE_DLP, unit="mGy.cm"),
        ]),
        *events,
    ]
    root[4].ContentSequence = Sequence([item("HAS PROPERTIES", "UIDREF", ("110180", "DCM", "Study Instance UID"), value=str(scr.StudyInstanceUID))])

    ds = Dataset()
    ds.file_meta = pydicom.dataset.FileMetaDataset()
    ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.88.67"
    ds.file_meta.MediaStorageSOPInstanceUID = uid("sop")
    ds.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
    ds.preamble = b"\0" * 128
    for kw in ["SpecificCharacterSet", "StudyDate", "StudyTime", "StudyInstanceUID", "StudyDescription", "PatientName", "PatientID",
               "PatientBirthDate", "PatientSex", "PatientAge", "AccessionNumber", "StudyID", "ReferringPhysicianName", "Manufacturer"]:
        if kw in scr:
            setattr(ds, kw, scr.data_element(kw).value)
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.88.67"
    ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
    ds.Modality = "SR"
    ds.SeriesInstanceUID = uid("series")
    ds.SeriesNumber = 997
    ds.SeriesDescription = "Dose Record (synthetic)"
    ds.InstanceNumber = 1
    ds.ContentDate, ds.ContentTime = scr.StudyDate, str(scr.get("ContentTime", scr.StudyTime))
    ds.ReferencedPerformedProcedureStepSequence = Sequence([])
    ds.PerformedProcedureCodeSequence = Sequence([])
    ds.CompletionFlag, ds.VerificationFlag = "COMPLETE", "UNVERIFIED"
    ds.ValueType = "CONTAINER"
    ds.ConceptNameCodeSequence = Sequence([code("113701", "DCM", "X-Ray Radiation Dose Report")])
    ds.ContinuityOfContent = "SEPARATE"
    tmpl = Dataset()
    tmpl.MappingResource, tmpl.TemplateIdentifier = "DCMR", "10011"
    ds.ContentTemplateSequence = Sequence([tmpl])
    ds.ContentSequence = Sequence(root)
    return [(ds, None)]


# ------------------------------------------------------------- scanned CT order


def code39(text: str) -> list[int]:
    """Bar widths (narrow 1, wide 3), bars and spaces alternating, for Code 39."""
    table = {
        "0": "000110100", "1": "100100001", "2": "001100001", "3": "101100000", "4": "000110001", "5": "100110000",
        "6": "001110000", "7": "000100101", "8": "100100100", "9": "001100100", "A": "100001001", "B": "001001001",
        "C": "101001000", "D": "000011001", "E": "100011000", "F": "001011000", "G": "000001101", "H": "100001100",
        "I": "001001100", "J": "000011100", "K": "100000011", "L": "001000011", "M": "101000010", "N": "000010011",
        "O": "100010010", "P": "001010010", "Q": "000000111", "R": "100000110", "S": "001000110", "T": "000010110",
        "U": "110000001", "V": "011000001", "W": "111000000", "X": "010010001", "Y": "110010000", "Z": "011010000",
        "-": "010000101", "*": "010010100",
    }
    widths = []
    for ch in f"*{text}*":
        widths += [3 if b == "1" else 1 for b in table[ch]] + [1]
    return widths


def draw_barcode(d: ImageDraw.ImageDraw, x0: int, y0: int, width: int, height: int, text: str) -> None:
    widths = code39(text)
    unit = width / sum(widths)
    x = float(x0)
    for i, w in enumerate(widths):
        if i % 2 == 0:
            d.rectangle([round(x), y0, round(x + w * unit) - 1, y0 + height], fill=255)
        x += w * unit


def handwriting(d, xy, text, size, angle_img=None, rng=None):
    d.text(xy, text, font=font("DejaVuSans-Oblique.ttf", size), fill=235)


def clinical_document(ctx: Context):
    out = []
    for ds in ctx.dropped.get(("ct-abdomen-pelvis-2012", "Clinical Documents"), []):
        w, h = int(ds.Columns), int(ds.Rows)
        img = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(img)
        S = 1.1  # layout measured on a 1545-pixel-wide view of the original
        mono, monob = font("DejaVuSansMono.ttf", 33), font("DejaVuSansMono-Bold.ttf", 33)

        def t(x, y, s, bold=False, anchor="la", f=None, fill=255):
            d.text((round(x * S), round(y * S)), s, font=f or (monob if bold else mono), fill=fill, anchor=anchor)

        date = str(ds.StudyDate)
        mmddyy = f"{date[4:6]}/{date[6:8]}/{date[2:4]}"
        age = str(ds.get("PatientAge", "")).lstrip("0").rstrip("Y")
        sex = str(ds.get("PatientSex", ""))
        acc = ctx.accession["ct-abdomen-pelvis-2012"]
        t(711, 70, FACILITY[0], True, "ma")
        t(711, 102, FACILITY[1], True, "ma")
        t(711, 133, "RADIOLOGY", True, "ma")
        t(52, 165, mmddyy, True)
        t(270, 165, "19:58:00")
        t(52, 197, "Name:")
        t(195, 197, NAME_DISPLAY, True)
        t(720, 197, f"MRN: {PATIENT_ID}")
        t(1028, 197, f"DOB: 01/01/{ctx.birth_year} {age}Y {sex}")
        t(52, 229, "Patient Loc:  Emergency Dept")
        t(1043, 229, f"FC: {FINANCIAL_CLASS}")
        t(52, 260, f"Account Number:  {ACCOUNT_NUMBER}")
        t(52, 320, "---------------------------PHYSICIAN INFORMATION---------------------------")
        t(52, 385, "Primary Care:")
        t(920, 385, "Phone:")
        for i, label in enumerate(["Attending:", "Ordering:", "Copy To:"]):
            t(52, 416 + 32 * i, label)
            t(322, 416 + 32 * i, CLINICIAN)
            if i < 2:
                t(920, 414 + 32 * i, f"Phone: {CLINICIAN_PHONE}")
        t(52, 540, "-----------------------------ORDER INFORMATION-----------------------------")
        t(52, 604, f"PCIS Entered By:  {ORDER_CLERK}")
        t(740, 602, "RIS Entered By: PCIS Order")
        t(52, 667, "Exam Date:")
        t(270, 667, mmddyy, True)
        t(487, 667, "Priority:")
        t(685, 667, "STAT", True)
        t(920, 665, "Pregnant: Y / N / Unknown")
        t(52, 729, "Alerts/Allergies:")
        t(108, 760, "*NO PCIS ENTRIES")
        t(52, 791, "Precautions/Add'l Info:")
        t(525, 791, ";, NO PREP,", True)
        t(838, 730, f"per DR {CLINICIAN_SHORT} no wait for Creatine", f=font("DejaVuSans-Oblique.ttf", 38), fill=235)
        for x, y in [(282, 100), (880, 140), (1210, 120), (455, 992)]:
            t(x, y, STAFF_INITIALS, f=font("DejaVuSans-Oblique.ttf", 44), fill=235)
        # The contrast checklist stamp, with handwritten answers.
        st = font("DejaVuSerif-Bold.ttf", 23)
        rows = [(866, "Creat________Date_________eGFR________"), (895, "Iodine Allergy ______________"),
                (930, "Diabetic  Y / N    Glucophage__________"), (960, "Kidney Problems _______________"),
                (1005, "_______mL Isovue 300 / 370 Rate______"), (1040, "IV_____Site_______Attempts_____Tech/RN____"),
                (1073, "Notes:____________________________________")]
        for y, s in rows:
            t(780, y, s, f=st)
        for cx, cy, r in [(955, 905, 14), (938, 942, 16), (975, 970, 15)]:
            d.ellipse([round((cx - r) * S), round((cy - r) * S), round((cx + r) * S), round((cy + r) * S)], outline=235, width=3)
        d.ellipse([round(985 * S), round(985 * S), round(1058 * S), round(1030 * S)], outline=235, width=3)
        t(800, 985, "85", f=font("DejaVuSans-Oblique.ttf", 40), fill=235)
        t(1158, 978, "2.5", f=font("DejaVuSans-Oblique.ttf", 40), fill=235)
        t(125, 1073, "C64119", True)
        t(341, 1073, "CT ABD/PELVIS W", True)
        t(52, 1137, "Reason for Exam:")
        t(88, 1168, "CENTRAL ABDOMINAL PAIN")
        d.line([round(655 * S), round(1230 * S), round(760 * S), round(1130 * S)], fill=235, width=4)
        d.line([round(660 * S), round(1180 * S), round(725 * S), round(1262 * S)], fill=235, width=4)
        draw_barcode(d, round(910 * S), round(1220 * S), round(430 * S), round(92 * S), acc)
        t(1100, 1354, acc, anchor="ma")
        t(52, 1385, "CODE STATUS:  SEE PATIENT CHART FOR CODE STATUS")
        t(52, 1449, "-FILM INFO------------------------------------AUDIT INFO-----------------", True)
        t(52, 1512, "LED:  07/24/2011")
        t(830, 1512, f"PCIS Ordr.No: {ORDER_NUMBER}:   11.")
        t(52, 1574, "Date of Last Pertinent Exam:_______________")
        for row, names in enumerate(CAMPUS_CODES):
            for i, n in enumerate(names):
                t(900 + 146 * i, 1572 + 62 * row, n)
        draw_barcode(d, round(440 * S), round(1655 * S), round(360 * S), round(95 * S), PATIENT_ID)
        t(397, 1790, NAME_DISPLAY)
        t(397, 1822, PATIENT_ID)
        t(1192, 1790, "19:58")
        # The CTDI log stamp in the lower left, on a separate slip.
        slip = Image.new("L", (round(365 * S), round(340 * S)), 0)
        sd = ImageDraw.Draw(slip)
        sf = font("DejaVuSans.ttf", 30)
        sd.rectangle([2, 2, slip.width - 3, slip.height - 3], outline=170, width=3)
        sd.text((18, 70), "Series", font=sf, fill=170)
        sd.text((220, 70), "est. CTDI", font=sf, fill=170)
        for i in range(6):
            y = 115 + 41 * i
            sd.line([10, y, slip.width - 10, y], fill=170, width=2)
            sd.text((30, y + 4), str(i + 1), font=sf, fill=170)
        sd.line([150, 110, 150, slip.height - 10], fill=170, width=2)
        sd.text((160, 112), "11.32", font=font("DejaVuSans-Oblique.ttf", 40), fill=235)
        slip = slip.rotate(-2, resample=Image.BICUBIC, expand=False)
        img.paste(Image.composite(slip, img.crop((round(75 * S), round(1665 * S), round(75 * S) + slip.width, round(1665 * S) + slip.height)),
                                  slip.point(lambda v: 255 if v > 20 else 0)), (round(75 * S), round(1665 * S)))
        # Scan look: slight skew, softening, faint scanner bands and noise.
        img = img.rotate(0.15, resample=Image.BICUBIC, fillcolor=0).filter(ImageFilter.GaussianBlur(0.6))
        a = np.asarray(img, dtype=np.float64)
        rng = np.random.default_rng(20121009)
        xs = np.arange(w)
        bands = 6 * np.exp(-((xs - 605) / 18) ** 2) + 5 * np.exp(-((xs - 1375) / 14) ** 2)
        a = a + bands[None, :] + rng.normal(0, 1.2, a.shape)
        a = np.clip(a, 0, 255)
        ds.PixelData = np.round(a).astype(np.uint8).tobytes()
        ds.SeriesDescription = "Clinical Documents (reconstructed)"
        out.append((ds, "Reconstructed: CT order form redrawn with fictional patient, staff, facility and order identifiers; clinical content as on the original."))
    return out


# --------------------------------------------------------- MRI viewer captures

# For each capture (by series number): the de-identified series and slice
# shown, and the series whose slice positions are drawn as reference lines.
# Captures 21 and 22 showed localizer images that are not on the CD; their
# reconstructions use the closest series that is.
# Series are given by (SeriesDescription, SeriesNumber); several series
# share a description.
CAPTURES = {
    21: {"base": ("T1 SE SAG", 15), "slice": 9, "lines": ("4 SHOT PG DWI", 3), "note": "localizer not on the CD; drawn on T1 SE SAG slice 9"},
    22: {"base": ("FLAIR COR", 20), "slice": 11, "lines": ("T1 SE SAG", 15), "note": "localizer not on the CD; drawn on FLAIR COR slice 11"},
    23: {"base": ("T1 SE SAG", 15), "slice": 9, "lines": ("T2 FSE AX", 16), "note": "same slice as the original"},
    24: {"base": ("T2 FSE AX", 16), "slice": 6, "lines": ("FLAIR COR", 20), "note": "same slice as the original"},
}


def _series(ctx, desc_num):
    desc, num = desc_num
    return sorted((s for s in ctx.kept[("mri-brain-2020", desc)] if int(s.SeriesNumber) == num), key=lambda s: int(s.InstanceNumber))


def _geometry(ds):
    iop = np.array([float(v) for v in ds.ImageOrientationPatient])
    ipp = np.array([float(v) for v in ds.ImagePositionPatient])
    ps = [float(v) for v in ds.PixelSpacing]  # row spacing, column spacing
    return ipp, iop[:3], iop[3:], ps


def _plane(rowdir, coldir):
    n = np.cross(rowdir, coldir)
    a = np.argmax(np.abs(n))
    return ["SAG", "COR", "TRS"][a]


def _ref_line(base, target, size):
    """Intersection of target's slice plane with base's image, in viewport pixels."""
    ipp, r, c, ps = _geometry(base)
    tipp, tr, tc, _ = _geometry(target)
    n = np.cross(tr, tc)
    # Signed distance at pixel (x, y): n . (ipp + x*r*ps_col + y*c*ps_row - tipp)
    a = float(n @ r) * ps[1]
    b = float(n @ c) * ps[0]
    k = float(n @ (ipp - tipp))
    cols, rows = int(base.Columns), int(base.Rows)
    pts = []
    for x in (0, cols - 1):
        if abs(b) > 1e-9:
            y = -(a * x + k) / b
            if 0 <= y <= rows - 1:
                pts.append((x, y))
    for y in (0, rows - 1):
        if abs(a) > 1e-9:
            x = -(b * y + k) / a
            if 0 <= x <= cols - 1:
                pts.append((x, y))
    if len(pts) < 2:
        return None
    scale = size / max(cols, rows)
    (x0, y0), (x1, y1) = sorted(pts)[:1] + sorted(pts)[-1:]
    return (x0 * scale, y0 * scale, x1 * scale, y1 * scale)


def mri_captures(ctx: Context):
    out = []
    for cap in ctx.dropped.get(("mri-brain-2020", "ViewportCapture-MR"), []):
        spec = CAPTURES.get(int(cap.SeriesNumber))
        if not spec:
            continue
        base_series = _series(ctx, spec["base"])
        base = next(s for s in base_series if int(s.InstanceNumber) == spec["slice"])
        line_series = _series(ctx, spec["lines"])
        size = int(cap.Columns)
        # The image, windowed as the viewer would, scaled into the viewport.
        px = base.pixel_array.astype(np.float64)
        wc, ww = float(np.ravel([base.WindowCenter])[0]), float(np.ravel([base.WindowWidth])[0])
        g = np.clip((px - (wc - ww / 2)) / ww, 0, 1) * 255
        im = Image.fromarray(g.astype(np.uint8)).resize((size, size), Image.BILINEAR)
        d = ImageDraw.Draw(im)
        small, name_f = font("DejaVuSans.ttf", max(9, size // 36)), font("DejaVuSans.ttf", max(11, size // 29))
        # Reference lines with slice numbers at both ends.
        for i, t in enumerate(line_series):
            seg = _ref_line(base, t, size)
            if not seg:
                continue
            x0, y0, x1, y1 = seg
            d.line([x0, y0, x1, y1], fill=225, width=1)
            d.text((x0 + 2, y0 - 6), str(i + 1), font=small, fill=255)
            d.text((x1 - 2, y1 - 6), str(i + 1), font=small, fill=255, anchor="ra")
        plane = _plane(*_geometry(base)[1:3])
        lh = small.size + 2
        age = str(cap.get("PatientAge", "")).lstrip("0")
        lbs = f"{float(cap.PatientWeight) * 2.20462:.1f}lbs" if cap.get("PatientWeight") else ""
        seq = {"SE": "2D SE", "IR": "2D IR"}.get(str(base.get("ScanningSequence", "")), "2D " + str(base.get("ScanningSequence", "")))
        if str(base.get("SequenceName", "")):
            seq = "2D " + str(base.SequenceName)
        tr, te = float(base.get("RepetitionTime", 0) or 0), float(base.get("EchoTime", 0) or 0)
        fov = round(float(base.PixelSpacing[1]) * int(base.Columns))
        acq = [int(v) for v in base.get("AcquisitionMatrix", [0, 0, 0, 0])]
        matrix = f"{max(acq[0], acq[1])}x{max(acq[2], acq[3])}"
        lines = [f"({cap.get('PatientSex', '')}) {age} {lbs}".strip(), f"{PATIENT_ID} BRAIN", f"{seq} {tr:g}/{te:.1f}",
                 f"{plane} {fov} {float(base.SliceThickness):.1f} {base.get('PatientPosition', '')}", matrix,
                 f"S# {spec['slice']}/{len(base_series)}", f"NSA {int(float(base.get('NumberOfAverages', 1) or 1))}"]
        d.text((4, 2), NAME_DISPLAY, font=name_f, fill=255, stroke_width=1, stroke_fill=0)
        y = 2 + name_f.size + 2
        for s in lines:
            d.text((4, y), s, font=small, fill=255, stroke_width=1, stroke_fill=0)
            y += lh
        acq_date, acq_time = str(base.get("AcquisitionDate", base.StudyDate)), str(base.get("AcquisitionTime", base.StudyTime))
        d.text((size - 4, 2), f"{acq_date[4:6]}/{acq_date[6:8]}/{acq_date[:4]} {acq_time[:2]}:{acq_time[2:4]}:{acq_time[4:6]}", font=small, fill=255, anchor="ra")
        top, left, right, bottom = {"SAG": ("H", "A", "P", "F"), "COR": ("H", "R", "L", "F"), "TRS": ("A", "R", "L", "P")}[plane]
        d.text((size // 2, 2), top, font=name_f, fill=255, anchor="ma")
        d.text((size // 2, size - 4), bottom, font=name_f, fill=255, anchor="md")
        d.text((4, size // 2), left, font=name_f, fill=255, anchor="lm")
        d.text((size - 4, size // 2), right, font=name_f, fill=255, anchor="rm")
        # A 10 cm scale bar along the left edge.
        mm_px = size / (max(int(base.Columns), int(base.Rows)) * float(base.PixelSpacing[0]))
        x0, y0 = 16, size * 0.3
        d.line([x0, y0, x0, y0 + 100 * mm_px], fill=255)
        for k in range(11):
            d.line([x0, y0 + 10 * k * mm_px, x0 + 4, y0 + 10 * k * mm_px], fill=255)
        d.text((x0 + 6, y0 + 100 * mm_px - lh), "10 cm", font=small, fill=255)
        loc = float(base.get("SliceLocation", 0) or 0)
        bl = ["Stack ID: 1", f"Dist from center(mm): {loc:.1f}", f"Orient: {plane}", f"{int(base.Columns)}x{int(base.Rows)}"]
        for i, s in enumerate(reversed(bl)):
            d.text((4, size - 4 - (i + 1) * lh), s, font=small, fill=255)
        br = [MRI_SITE, f"W: {ww:g} L: {wc:g}", str(base.get("ManufacturerModelName", "")), "1.00X"]
        for i, s in enumerate(br):
            d.text((size - 4, size - 4 - (i + 1) * lh), s, font=small, fill=255, anchor="ra")
        a = np.asarray(im, dtype=np.uint16)
        cap.PixelData = a.tobytes()
        for kw in ["ImagePositionPatient", "ImageOrientationPatient", "SliceLocation"]:
            if kw in cap:
                del cap[kw]
        cap.SeriesDescription = "ViewportCapture-MR (reconstructed)"
        out.append((cap, f"Reconstructed viewer capture ({spec['note']}); overlay shows the sample patient and a fictional site."))
    return out


BUILDERS = [dose_report, dose_sr, clinical_document, mri_captures]


def build(ctx: Context):
    out = []
    for b in BUILDERS:
        out += b(ctx)
    return out
