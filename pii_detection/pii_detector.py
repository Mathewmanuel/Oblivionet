import re
import logging
from typing import List, Dict, Optional
try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
except Exception:
    nlp = None
    logging.warning("spaCy model 'en_core_web_sm' not found. NER detection disabled, falling back to regex only.")

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# Regex patterns for PII detection
REGEX_PATTERNS = {
    "EMAIL": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
    "PHONE": re.compile(
        r'\b(\+91[\-\s]?)?(\(?\d{3,5}\)?[\-\s]?)?[\d\s\-]{6,12}\b'),  # Indian + intl simplified
    "AADHAAR": re.compile(r'\b\d{4}\s\d{4}\s\d{4}\b'),
    "PAN": re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b'),
    "CREDIT_CARD": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
    "SSN": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    "DOB": re.compile(r'\b(0?[1-9]|[12][0-9]|3[01])[-/](0?[1-9]|1[012])[-/](\d{2}|\d{4})\b'),
    "PASSPORT": re.compile(r'\b[A-PR-WYa-pr-wy][0-9]{7}\b'),
    "DRIVING_LICENSE": re.compile(r'\b[A-Z]{2}\d{2}[0-9A-Z]{11}\b'),  # Example: TN0123456789123
    "BANK_ACCOUNT": re.compile(r'\b\d{9,18}\b'),
    "IFSC": re.compile(r'\b[A-Z]{4}0[A-Z0-9]{6}\b'),
    "PINCODE": re.compile(r'\b\d{6}\b'),
    "NAME_PREFIX": re.compile(r'\b(Mr|Mrs|Ms|Dr|Prof|Miss|Mx)\.?\s+[A-Z][a-z]+\b'),
    "ADDRESS": re.compile(r'\b[\w\s,.-]+(?:Street|Road|Nagar|Colony|Avenue|Lane|Boulevard|Drive|Park|Square|Terrace)\b', re.I),
}

# Map spaCy entity labels to PII types
NER_LABEL_MAP = {
    "PERSON": "PERSON",
    "ORG": "ORG",
    "GPE": "GPE",
    "DATE": "DATE",
    "MONEY": "MONEY",
    "CARDINAL": "CARDINAL",
}

def detect_pii_with_regex(text: str, bbox: List[int]) -> List[Dict]:
    """Detect PII using regex patterns in the given text block."""
    results = []
    for pii_type, pattern in REGEX_PATTERNS.items():
        for match in pattern.finditer(text):
            results.append({
                "type": pii_type,
                "text": match.group(),
                "bbox": bbox,
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.9
            })
    return results

def detect_pii_with_ner(text: str, bbox: List[int]) -> List[Dict]:
    """Detect PII using spaCy NER in the given text block."""
    if nlp is None:
        logging.warning("spaCy model not loaded, skipping NER detection.")
        return []
    results = []
    doc = nlp(text)
    for ent in doc.ents:
        pii_type = NER_LABEL_MAP.get(ent.label_)
        if pii_type:
            results.append({
                "type": pii_type,
                "text": ent.text,
                "bbox": bbox,
                "start": ent.start_char,
                "end": ent.end_char,
                "confidence": 0.8
            })
    return results

def detect_pii(ocr_data: List[Dict], selected_types: Optional[List[str]] = None) -> List[Dict]:
    """
    Detect PII entities from OCR output.
    ocr_data: list of dicts with keys "text" and "bbox".
    selected_types: optional list of PII types to filter results.
    Returns list of detected PII entities.
    """
    all_entities = []
    for block in ocr_data:
        text = block.get("text", "")
        bbox = block.get("bbox", [0,0,0,0])
        if not text:
            continue

        # Regex detection
        regex_entities = detect_pii_with_regex(text, bbox)
        # NER detection
        ner_entities = detect_pii_with_ner(text, bbox)

        all_entities.extend(regex_entities)
        all_entities.extend(ner_entities)

    # Filter by selected_types if provided (case-insensitive)
    if selected_types:
        selected_types_upper = set(t.upper() for t in selected_types)
        all_entities = [e for e in all_entities if e["type"].upper() in selected_types_upper]

    # Remove duplicates (same text + type)
    unique = []
    seen = set()
    for ent in all_entities:
        key = (ent["text"].lower(), ent["type"].upper())
        if key not in seen:
            seen.add(key)
            unique.append(ent)

    return unique

def get_pii_summary(pii_entities: List[Dict]) -> Dict[str, int]:
    """Generate a summary count of detected PII types."""
    summary = {}
    for ent in pii_entities:
        t = ent["type"].upper()
        summary[t] = summary.get(t, 0) + 1
    return summary

# Example usage
if __name__ == "__main__":
    sample_ocr_data = [
        {"text": "Contact me at example@gmail.com or +91 98765 43210.", "bbox": [10, 10, 200, 50]},
        {"text": "My PAN is ABCDE1234F and Aadhaar 1234 5678 9012.", "bbox": [15, 60, 300, 100]},
        {"text": "Mr. John Doe lives on MG Road.", "bbox": [20, 110, 250, 150]},
        {"text": "SSN: 123-45-6789, DOB: 12/05/1980", "bbox": [25, 160, 280, 200]},
    ]

    detected = detect_pii(sample_ocr_data)
    for d in detected:
        print(d)

    summary = get_pii_summary(detected)
    print("\nSummary:", summary)
