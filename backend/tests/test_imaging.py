import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from app.imaging import LoadedImage, display_pixels, strip_patient_tags


def _synthetic_dicom(photometric="MONOCHROME2", intercept=0.0):
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = pydicom.uid.SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID = meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    ds.Modality = "CT"
    ds.Rows = 4
    ds.Columns = 4
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = photometric
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.RescaleSlope = 1.0
    ds.RescaleIntercept = intercept
    ds.PixelData = np.arange(16, dtype=np.uint16).tobytes()
    return ds


def test_display_pixels_applies_intercept_and_inverts_monochrome1():
    raw = np.arange(16, dtype=np.uint16).reshape(4, 4)
    ds2 = _synthetic_dicom("MONOCHROME2", intercept=100)
    ds1 = _synthetic_dicom("MONOCHROME1", intercept=100)
    image2 = LoadedImage("dicom", raw.copy(), "uid", dataset=ds2)
    image1 = LoadedImage("dicom", raw.copy(), "uid", dataset=ds1)
    display2 = display_pixels(image2)
    display1 = display_pixels(image1)
    assert np.allclose(display2, raw + 100)
    assert np.allclose(display1, np.max(raw + 100) - (raw + 100))


def test_strip_patient_tags_recurses_and_keeps_uid():
    ds = _synthetic_dicom()
    ds.PatientName = "Example^Person"
    ds.AccessionNumber = "ACC-1"
    ds.StudyID = "STUDY-1"
    ds.StudyInstanceUID = "1.2.3.4"
    item = Dataset()
    item.PatientID = "NESTED"
    item.StudyInstanceUID = "1.2.3.5"
    item.add_new((0x0010, 0x0010), "PN", "Sequence^Person")
    ds.ReferencedImageSequence = [item]
    ds.add_new((0x0011, 0x0010), "LO", "private value")

    strip_patient_tags(ds)
    assert "PatientName" not in ds and "AccessionNumber" not in ds and "StudyID" not in ds
    assert ds.StudyInstanceUID == "1.2.3.4"
    assert "PatientID" not in ds.ReferencedImageSequence[0]
    assert ds.ReferencedImageSequence[0].StudyInstanceUID == "1.2.3.5"
    assert (0x0011, 0x0010) not in ds
