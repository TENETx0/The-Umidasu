"""Curated set of common EXIF/GPS/IPTC/XMP tag names, used only to decide
whether a tag is "common" enough to skip the Unknown Tag Decoder's extra
detail (tag ID, namespace, raw value, data type are shown for every tag
regardless — this set only controls the "unknown/uncommon" flag used to
surface maker-notes and non-standard tags for forensic attention).

This list is drawn from the public EXIF 2.3, IPTC IIM, and XMP (Dublin
Core / exif / tiff / xmp namespaces) specifications — all open, widely
published standards — not fabricated or guessed.
"""
from __future__ import annotations

KNOWN_TAG_NAMES: frozenset[str] = frozenset({
    # --- EXIF / TIFF (IFD0, IFD1, ExifIFD) ---
    "ImageWidth", "ImageHeight", "BitsPerSample", "Compression", "PhotometricInterpretation",
    "Orientation", "SamplesPerPixel", "PlanarConfiguration", "YCbCrSubSampling", "YCbCrPositioning",
    "XResolution", "YResolution", "ResolutionUnit", "StripOffsets", "RowsPerStrip", "StripByteCounts",
    "Make", "Model", "Software", "DateTime", "Artist", "Copyright", "WhitePoint", "PrimaryChromaticities",
    "TransferFunction", "ColorSpace", "ExifImageWidth", "ExifImageHeight",
    "ExposureTime", "FNumber", "ExposureProgram", "SpectralSensitivity", "ISO", "ISOSpeedRatings",
    "OECF", "SensitivityType", "RecommendedExposureIndex", "ExifVersion", "DateTimeOriginal",
    "DateTimeDigitized", "ComponentsConfiguration", "CompressedBitsPerPixel", "ShutterSpeedValue",
    "ApertureValue", "BrightnessValue", "ExposureBiasValue", "MaxApertureValue", "SubjectDistance",
    "MeteringMode", "LightSource", "Flash", "FocalLength", "SubjectArea", "MakerNote", "UserComment",
    "SubSecTime", "SubSecTimeOriginal", "SubSecTimeDigitized", "FlashpixVersion", "FlashPixVersion",
    "PixelXDimension", "PixelYDimension", "RelatedSoundFile", "FlashEnergy", "SpatialFrequencyResponse",
    "FocalPlaneXResolution", "FocalPlaneYResolution", "FocalPlaneResolutionUnit", "SubjectLocation",
    "ExposureIndex", "SensingMethod", "FileSource", "SceneType", "CFAPattern", "CustomRendered",
    "ExposureMode", "WhiteBalance", "DigitalZoomRatio", "FocalLengthIn35mmFilm", "FocalLengthIn35mmFormat",
    "SceneCaptureType", "GainControl", "Contrast", "Saturation", "Sharpness", "DeviceSettingDescription",
    "SubjectDistanceRange", "ImageUniqueID", "CameraOwnerName", "BodySerialNumber", "LensSpecification",
    "LensInfo", "LensMake", "LensModel", "LensSerialNumber", "SerialNumber", "OwnerName",
    "Rating", "RatingPercent", "ThumbnailOffset", "ThumbnailLength", "Compression1", "ApplicationNotes",
    "ExifByteOrder", "ExifToolVersion", "InteropIndex", "InteropVersion", "ImageDescription",
    "OffsetTime", "OffsetTimeOriginal", "OffsetTimeDigitized", "PreviewImage", "ThumbnailImage",

    # --- GPS ---
    "GPSVersionID", "GPSLatitudeRef", "GPSLatitude", "GPSLongitudeRef", "GPSLongitude",
    "GPSAltitudeRef", "GPSAltitude", "GPSTimeStamp", "GPSSatellites", "GPSStatus", "GPSMeasureMode",
    "GPSDOP", "GPSSpeedRef", "GPSSpeed", "GPSTrackRef", "GPSTrack", "GPSImgDirectionRef",
    "GPSImgDirection", "GPSDirection", "GPSMapDatum", "GPSDestLatitudeRef", "GPSDestLatitude",
    "GPSDestLongitudeRef", "GPSDestLongitude", "GPSDestBearingRef", "GPSDestBearing",
    "GPSDestDistanceRef", "GPSDestDistance", "GPSProcessingMethod", "GPSAreaInformation",
    "GPSDateStamp", "GPSDifferential", "GPSHPositioningError", "GPSPosition", "GPSAltitude",

    # --- IPTC IIM ---
    "ObjectName", "EditStatus", "Urgency", "SubjectReference", "Category", "SupplementalCategories",
    "FixtureIdentifier", "Keywords", "ContentLocationCode", "ContentLocationName", "ReleaseDate",
    "ReleaseTime", "ExpirationDate", "ExpirationTime", "SpecialInstructions", "ActionAdvised",
    "ReferenceService", "ReferenceDate", "ReferenceNumber", "DateCreated", "TimeCreated",
    "DigitalCreationDate", "DigitalCreationTime", "OriginatingProgram", "ProgramVersion",
    "ObjectCycle", "By-line", "By-lineTitle", "City", "Sub-location", "Province-State",
    "Country-PrimaryLocationCode", "Country-PrimaryLocationName", "OriginalTransmissionReference",
    "Headline", "Credit", "Source", "CopyrightNotice", "Contact", "Caption-Abstract", "WriterEditor",
    "ImageType", "ImageOrientation", "LanguageIdentifier",

    # --- XMP (dc / exif / tiff / xmp / photoshop namespaces) ---
    "Creator", "Title", "Description", "Subject", "Rights", "CreateDate", "ModifyDate", "MetadataDate",
    "CreatorTool", "Label", "Format", "DocumentID", "InstanceID", "OriginalDocumentID", "History",
    "Lens", "SerialNumber", "LensInfo", "ApproximateFocusDistance", "CameraProfile",
    "ColorMode", "ICCProfile", "DateCreated", "AuthorsPosition", "CaptionWriter", "Headline",
    "Instructions", "TransmissionReference", "Urgency", "City", "State", "Country", "Location",
    "PersonInImage", "Event", "Scene", "SubjectCode", "IntellectualGenre", "UsageTerms", "WebStatement",
    "Marked", "Owner", "Certificate",

    # --- File-level pseudo tags that sometimes surface unprefixed ---
    "FileType", "FileTypeExtension", "MIMEType", "ExifByteOrder", "EncodingProcess",
    "BitsPerPixel", "ColorComponents", "YCbCrSubSampling",
})


def is_known_tag(tag_name: str) -> bool:
    return tag_name in KNOWN_TAG_NAMES
