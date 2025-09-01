import re

# Regex patterns for PII detection
EMAIL_PATTERN = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
PHONE_PATTERN = r"(?:\+91[- ]?)?\d{10}"
AADHAAR_PATTERN = r"\d{4}\s\d{4}\s\d{4}"

def detect_pii(ocr_data):
    """
    Detect PII in OCR results using regex.
    :param ocr_data: List of OCR text blocks with bbox
    :return: List of detected PII entities
    """
    detected_entities = []
    for block in ocr_data:
        text = block["text"]
        bbox = block["bbox"]
        if re.search(EMAIL_PATTERN, text):
            detected_entities.append({"type": "EMAIL", "text": text, "bbox": bbox})
        if re.search(PHONE_PATTERN, text):
            detected_entities.append({"type": "PHONE", "text": text, "bbox": bbox})
        if re.search(AADHAAR_PATTERN, text):
            detected_entities.append({"type": "AADHAAR", "text": text, "bbox": bbox})
    return detected_entities
