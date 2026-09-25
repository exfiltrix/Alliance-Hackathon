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
    px: np.ndarray  # 2-D grayscale, original dtype
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
    return LoadedImage("png", gray_pixels(img), img.text.get(PNG_UID_KEY), pil=img)


def gray_pixels(img: Image.Image) -> np.ndarray:
    """Grayscale pixels keeping the original bit depth (8-bit L, 16-bit I;16, 32-bit I)."""
    if img.mode not in ("L", "I", "I;16", "I;16B", "I;16L", "F"):
        img = img.convert("L")
    return np.array(img)


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
