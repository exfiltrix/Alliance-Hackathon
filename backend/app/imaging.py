"""Reading uploads (DICOM / PNG) into pixels plus the image ID.

DICOM patient identifiers are removed recursively before storage. The raw native pixel
array is kept separate from the display view: tile hashes always use the native array,
while previews and AI use a modality/VOI-aware display view.
"""
import hashlib
import hmac
import io
import json
import struct
import uuid
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pydicom
from PIL import Image, PngImagePlugin
from pydicom.pixels import apply_modality_lut, apply_voi_lut
from pydicom.uid import generate_uid

from app.config import settings

PNG_UID_KEY = "medseal_uid"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# Display-affecting DICOM tags included in the v1 metadata hash. This tuple is frozen
# because existing seals use it; v2 adds the broader tuple below.
META_TAGS = (
    "Modality", "BodyPartExamined", "Laterality", "ImageLaterality", "ViewPosition",
    "PhotometricInterpretation", "BitsStored", "PixelRepresentation",
    "RescaleSlope", "RescaleIntercept", "RescaleType", "WindowCenter", "WindowWidth",
    "PixelSpacing", "StudyInstanceUID", "SeriesInstanceUID",
)
META_TAGS_V2 = META_TAGS + (
    "VOILUTSequence", "ModalityLUTSequence", "PresentationLUTShape", "ImageOrientationPatient",
    "PatientOrientation", "ImagerPixelSpacing", "NumberOfFrames", "BurnedInAnnotation",
    "StudyDate", "AcquisitionDate",
)

# Tags that identify a patient or a person responsible for care. UIDs are deliberately
# not included: SOPInstanceUID and related UIDs are required for seal verification.
PATIENT_TAGS = (
    "PatientName", "PatientID", "PatientBirthDate", "PatientBirthTime", "PatientSex", "PatientAge",
    "PatientAddress", "PatientTelephoneNumbers", "PatientMotherBirthName", "OtherPatientIDs",
    "OtherPatientIDsSequence", "OtherPatientNames", "PatientBirthName", "PatientComments",
    "EthnicGroup", "MilitaryRank", "BranchOfService", "MedicalRecordLocator", "PatientInsurancePlanCodeSequence",
    "IssuerOfPatientID", "PatientReligiousPreference", "PatientWeight", "PatientSize",
    "AccessionNumber", "InstitutionName", "InstitutionAddress", "InstitutionalDepartmentName",
    "ReferringPhysicianName", "PerformingPhysicianName", "OperatorsName", "PhysiciansOfRecord",
    "RequestingPhysician", "StudyID", "DeviceSerialNumber", "StationName",
)


class ImageError(ValueError):
    """Upload is not a supported image. Message is safe to show to the user."""


class ImageTooLarge(ImageError):
    """Decodes to more pixels than settings.max_pixels (decompression bomb, T10)."""


@dataclass
class LoadedImage:
    kind: Literal["dicom", "png"]
    # DICOM: always 2-D grayscale (multi-channel DICOM is rejected below). PNG: native channel
    # layout — 2-D grayscale or 3-D (h, w, channels) for RGB/RGBA/LA — original dtype.
    px: np.ndarray
    uid: str | None  # None = image carries no ID (never sealed)
    dataset: pydicom.Dataset | None = None
    pil: Image.Image | None = None
    patient_id: str | None = None
    burned_in_annotation: bool = False


def _pixel_budget() -> int:
    return max(1, int(settings.max_pixels))


def _check_pixel_count(count: int) -> None:
    if count > _pixel_budget():
        raise ImageTooLarge(f"Image is too large: {count} pixels exceed the {_pixel_budget()} pixel limit")


def _check_png_header(data: bytes) -> None:
    if len(data) < 29 or data[12:16] != b"IHDR":
        raise ImageError("Invalid PNG header")
    width, height = struct.unpack(">II", data[16:24])
    bit_depth, color_type = data[24], data[25]
    if color_type in (2, 4, 6) and bit_depth == 16:
        raise ImageError("16-bit colour PNG is not supported")
    _check_pixel_count(width * height)
    # Keep Pillow's secondary decompression-bomb guard aligned with the explicit header check.
    Image.MAX_IMAGE_PIXELS = _pixel_budget()


def _dicom_pixel_count(ds: pydicom.Dataset) -> int:
    rows = int(getattr(ds, "Rows", 0) or 0)
    columns = int(getattr(ds, "Columns", 0) or 0)
    frames = int(getattr(ds, "NumberOfFrames", 1) or 1)
    samples = int(getattr(ds, "SamplesPerPixel", 1) or 1)
    if rows <= 0 or columns <= 0 or frames <= 0 or samples <= 0:
        raise ImageError("DICOM image dimensions are missing or invalid")
    return rows * columns * frames * samples


def load_image(data: bytes) -> LoadedImage:
    Image.MAX_IMAGE_PIXELS = _pixel_budget()
    if data[:8] == PNG_MAGIC:
        return _load_png(data)
    if data[128:132] == b"DICM":
        return _load_dicom(data)
    raise ImageError("Only DICOM (.dcm) and PNG files are supported")


def _strip_dataset(ds: pydicom.Dataset) -> None:
    for element in list(ds):
        keyword = element.keyword
        if element.VR == "PN" or keyword in PATIENT_TAGS or element.tag.is_private:
            del ds[element.tag]
            continue
        if element.VR == "SQ":
            for item in element.value:
                _strip_dataset(item)
    ds.remove_private_tags()


def strip_patient_tags(ds: pydicom.Dataset) -> None:
    """Remove person/identity tags recursively while retaining UIDs by design."""
    _strip_dataset(ds)


def _load_dicom(data: bytes) -> LoadedImage:
    try:
        ds = pydicom.dcmread(io.BytesIO(data))
    except Exception as e:  # pydicom raises many different types on bad input
        raise ImageError(f"Cannot read DICOM file: {e}") from e
    try:
        _check_pixel_count(_dicom_pixel_count(ds))
        patient_id = str(ds.PatientID) if "PatientID" in ds else None
        burned = str(getattr(ds, "BurnedInAnnotation", "")).upper() == "YES"
        strip_patient_tags(ds)
        px = ds.pixel_array
    except ImageError:
        raise
    except Exception as e:
        raise ImageError(f"Cannot decode DICOM pixel data: {e}") from e
    if px.ndim != 2:
        raise ImageError(f"Only single-frame grayscale DICOM is supported (got shape {px.shape})")
    uid = str(ds.SOPInstanceUID) if "SOPInstanceUID" in ds else None
    return LoadedImage("dicom", px, uid, dataset=ds, patient_id=patient_id, burned_in_annotation=burned)


def _load_png(data: bytes) -> LoadedImage:
    _check_png_header(data)
    try:
        img = Image.open(io.BytesIO(data))
        _check_pixel_count(img.width * img.height)
        img.load()
    except ImageError:
        raise
    except Exception as e:
        raise ImageError(f"Cannot read PNG file: {e}") from e
    return LoadedImage("png", native_pixels(img), img.text.get(PNG_UID_KEY), pil=img)


_NATIVE_MODES = ("L", "I", "I;16", "I;16B", "I;16L", "F", "LA", "RGB", "RGBA")


def native_pixels(img: Image.Image) -> np.ndarray:
    """Pixels in their native channel layout and original bit depth. Every channel is sealed."""
    if img.mode == "P":
        img = img.convert("RGBA" if "transparency" in img.info else "RGB")
    elif img.mode not in _NATIVE_MODES:
        img = img.convert("RGB")
    return np.array(img)


def _canonical_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, pydicom.dataset.Dataset):
        return {
            f"{element.tag.group:04X}{element.tag.element:04X}": _canonical_value(element.value)
            for element in value
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def meta_fields(image: "LoadedImage", version: int = 1) -> dict:
    """Return the metadata set bound by the row's stored version."""
    if image.kind == "dicom":
        out = {}
        tags = META_TAGS if version < 2 else META_TAGS_V2
        for tag in tags:
            if tag in image.dataset:
                out[tag] = _canonical_value(image.dataset[tag].value)
        if version >= 2:
            # Overlay planes are even group 60xx. Include them even when no keyword exists.
            for element in image.dataset:
                group = element.tag.group
                if 0x6000 <= group <= 0x60FF and group % 2 == 0:
                    out[f"{group:04X}{element.tag.element:04X}"] = _canonical_value(element.value)
        return out
    return {"mode": image.pil.mode if image.pil is not None else "unknown"}


def patient_reference(patient_id: str | None) -> str:
    """Return a stable HMAC reference, never the PatientID itself."""
    if not patient_id or not settings.patient_salt:
        return ""
    return hmac.new(
        settings.patient_salt.encode("utf-8"), patient_id.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def meta_hash(fields: dict) -> bytes:
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(canonical).digest()


def to_grayscale(px: np.ndarray) -> np.ndarray:
    """2-D luminance view; never used by the native tile/Merkle hash."""
    if px.ndim == 2:
        return px
    if px.shape[-1] == 2:  # LA: alpha is metadata/pixel data, not luminance
        return px[..., 0]
    rgb = px[..., :3].astype(np.float64)
    lum = rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114
    if np.issubdtype(px.dtype, np.integer):
        info = np.iinfo(px.dtype)
        lum = np.clip(np.round(lum), info.min, info.max)
    return lum.astype(px.dtype)


def display_pixels(image: "LoadedImage") -> np.ndarray:
    """Return the 2-D display view used by previews and AI, never by tile hashing."""
    if image.kind == "png":
        return to_grayscale(image.px).astype(np.float32)
    ds = image.dataset
    if ds is None:
        return to_grayscale(image.px).astype(np.float32)
    values = apply_modality_lut(image.px, ds)
    has_voi = "WindowCenter" in ds or "WindowWidth" in ds or "VOILUTSequence" in ds
    if has_voi:
        try:
            values = apply_voi_lut(values, ds)
        except Exception:
            # A malformed optional LUT must not make an otherwise readable image unusable;
            # the display remains the modality-correct view and metadata verification still flags it.
            pass
    if str(getattr(ds, "PhotometricInterpretation", "")).upper() == "MONOCHROME1":
        values = float(np.max(values)) - values
    return np.asarray(values, dtype=np.float32)


def ai_applicable(image: "LoadedImage") -> bool:
    """The bundled models are chest X-ray models; do not apply them to CT/other modalities."""
    if image.px.ndim != 2:
        return False
    if image.kind == "png":
        return True
    modality = str(getattr(image.dataset, "Modality", "")).upper() if image.dataset is not None else ""
    return modality in {"CR", "DX"}


def _to_uint8(px: np.ndarray) -> np.ndarray:
    """1st-99th percentile window so 16-bit CT/high-dynamic-range views are usable at 8 bits."""
    if px.dtype == np.uint8:
        return px
    lo, hi = np.percentile(px, [1, 99])
    if hi <= lo:
        hi = lo + 1
    return np.clip((px.astype(np.float64) - lo) * 255.0 / (hi - lo), 0, 255).astype(np.uint8)


def dhash(gray: np.ndarray) -> str:
    """64-bit difference hash for content-based recovery; not a security decision by itself."""
    small = Image.fromarray(_to_uint8(gray)).resize((9, 8), Image.Resampling.LANCZOS)
    arr = np.asarray(small, dtype=np.int16)
    bits = arr[:, 1:] > arr[:, :-1]
    value = 0
    for b in bits.flatten():
        value = (value << 1) | int(b)
    return f"{value:016x}"


def hamming_distance(a_hex: str, b_hex: str) -> int:
    return bin(int(a_hex, 16) ^ int(b_hex, 16)).count("1")


def assign_uid(image: LoadedImage) -> str:
    """Give an unsealed image an ID. DICOM gets a SOPInstanceUID, PNG a UUID."""
    if image.uid is None:
        if image.kind == "dicom":
            image.uid = str(generate_uid())
            image.dataset.SOPInstanceUID = image.uid
        else:
            image.uid = str(uuid.uuid4())
    return image.uid


def sealed_file_bytes(image: LoadedImage) -> tuple[bytes, str]:
    """File to hand back after sealing: DICOM without patient tags, or PNG with a medseal_uid chunk."""
    buf = io.BytesIO()
    if image.kind == "dicom":
        image.dataset.save_as(buf, enforce_file_format=True)
        return buf.getvalue(), "dcm"
    info = PngImagePlugin.PngInfo()
    for k, v in image.pil.text.items():
        if k != PNG_UID_KEY:
            info.add_text(k, v)
    info.add_text(PNG_UID_KEY, image.uid)
    image.pil.save(buf, "PNG", pnginfo=info)
    return buf.getvalue(), "png"
