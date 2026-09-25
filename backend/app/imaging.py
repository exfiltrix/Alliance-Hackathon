"""Reading uploads (DICOM / PNG) into a grayscale pixel array plus the image ID.

Patient tags are stripped from DICOM right after parsing, before anything is stored.
"""
import io
import uuid
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pydicom
from PIL import Image, PngImagePlugin
from pydicom.uid import generate_uid

PNG_UID_KEY = "medseal_uid"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# Tags that identify the patient. Removing them does not touch pixel data.
PATIENT_TAGS = (
    "PatientName", "PatientID", "PatientBirthDate", "PatientBirthTime", "PatientSex", "PatientAge",
    "PatientAddress", "PatientTelephoneNumbers", "PatientMotherBirthName", "OtherPatientIDs",
    "OtherPatientIDsSequence", "OtherPatientNames", "PatientBirthName", "PatientComments",
    "EthnicGroup", "MilitaryRank", "BranchOfService", "MedicalRecordLocator", "PatientInsurancePlanCodeSequence",
    "IssuerOfPatientID", "PatientReligiousPreference", "PatientWeight", "PatientSize",
)


class ImageError(ValueError):
    """Upload is not a supported image. Message is safe to show to the user."""


@dataclass
class LoadedImage:
    kind: Literal["dicom", "png"]
    # DICOM: always 2-D grayscale (multi-channel DICOM is rejected below). PNG: native channel
    # layout — 2-D grayscale or 3-D (h, w, channels) for RGB/RGBA — original dtype. The seal
    # hashes this array exactly as-is (P0-3): never flatten it to grayscale before sealing.
    px: np.ndarray
    uid: str | None  # None = image carries no ID (never sealed)
    dataset: pydicom.Dataset | None = None
    pil: Image.Image | None = None


def load_image(data: bytes) -> LoadedImage:
    if data[:8] == PNG_MAGIC:
        return _load_png(data)
    if data[128:132] == b"DICM":
        return _load_dicom(data)
    raise ImageError("Only DICOM (.dcm) and PNG files are supported")


def strip_patient_tags(ds: pydicom.Dataset) -> None:
    for name in PATIENT_TAGS:
        if name in ds:
            delattr(ds, name)
    ds.remove_private_tags()


def _load_dicom(data: bytes) -> LoadedImage:
    try:
        ds = pydicom.dcmread(io.BytesIO(data))
    except Exception as e:  # pydicom raises many different types on bad input
        raise ImageError(f"Cannot read DICOM file: {e}") from e
    strip_patient_tags(ds)
    try:
        px = ds.pixel_array
    except Exception as e:
        raise ImageError(f"Cannot decode DICOM pixel data: {e}") from e
    if px.ndim != 2:
        raise ImageError(f"Only single-frame grayscale DICOM is supported (got shape {px.shape})")
    uid = str(ds.SOPInstanceUID) if "SOPInstanceUID" in ds else None
    return LoadedImage("dicom", px, uid, dataset=ds)


def _load_png(data: bytes) -> LoadedImage:
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as e:
        raise ImageError(f"Cannot read PNG file: {e}") from e
    return LoadedImage("png", native_pixels(img), img.text.get(PNG_UID_KEY), pil=img)


_NATIVE_MODES = ("L", "I", "I;16", "I;16B", "I;16L", "F", "RGB", "RGBA")


def native_pixels(img: Image.Image) -> np.ndarray:
    """Pixels in their native channel layout, original bit depth: 2-D for L/I/I;16/F, 3-D
    (h, w, channels) for RGB/RGBA. Every channel is sealed (P0-3) — a color-only edit, or making
    a region transparent, changes the hashed bytes even though luminance alone would not.
    Palette (P) images are expanded to RGB/RGBA explicitly (a palette index is not a color)."""
    if img.mode == "P":
        img = img.convert("RGBA" if "transparency" in img.info else "RGB")
    elif img.mode not in _NATIVE_MODES:
        img = img.convert("RGB")
    return np.array(img)


def to_grayscale(px: np.ndarray) -> np.ndarray:
    """2-D luminance view for display/AI purposes only — the seal always hashes the native
    array from native_pixels() above; this never feeds into a hash."""
    if px.ndim == 2:
        return px
    rgb = px[..., :3].astype(np.float64)
    lum = rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114
    if np.issubdtype(px.dtype, np.integer):
        info = np.iinfo(px.dtype)
        lum = np.clip(np.round(lum), info.min, info.max)
    return lum.astype(px.dtype)


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
    """File to hand back after sealing: DICOM without patient tags, or PNG with a medseal_uid chunk.

    Pixels are never modified. Returns (content, file extension).
    """
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
