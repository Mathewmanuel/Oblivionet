import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Enhanced PII patterns with better matching
PII_PATTERNS = {
    "EMAIL": r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
    "PHONE": r"(?:\+91[- ]?)?\b\d{10}\b|\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "AADHAAR": r"\b\d{4}\s?\d{4}\s?\d{4}\b",
    "PAN": r"\b[A-Z]{5}\d{4}[A-Z]{1}\b",
    "CREDIT_CARD": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "DATE_OF_BIRTH": r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    "PASSPORT": r"\b[A-Z]\d{7}\b",
    "DRIVING_LICENSE": r"\b[A-Z]{2}\d{13}\b",
    "BANK_ACCOUNT": r"\b\d{9,18}\b",
    "IFSC": r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
    "PIN_CODE": r"\b\d{6}\b",
    "NAME": r"(?:Mr\.|Mrs\.|Ms\.|Dr\.)\s+[A-Z][a-z]+\s+[A-Z][a-z]+|(?:Name|NAME)[:]\s*[A-Z][a-z]+\s+[A-Z][a-z]+",
    "ADDRESS": r"\d+[\w\s,.-]+(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Place|Pl|Nagar|Colony)\b"
}

# Load spaCy model for NER (optional)
try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
    logger.info("SpaCy model loaded successfully")
except (OSError, ImportError):
    logger.warning("SpaCy English model not found. Using regex patterns only.")
    nlp = None

def detect_pii_with_regex(text: str, bbox: List) -> List[Dict]:
    """Detect PII using regex patterns"""
    detected_entities = []
    
    for pii_type, pattern in PII_PATTERNS.items():
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            detected_entities.append({
                "type": pii_type,
                "text": match.group(),
                "bbox": bbox,
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.9
            })
    
    return detected_entities

def detect_pii_with_ner(text: str, bbox: List) -> List[Dict]:
    """Detect PII using Named Entity Recognition"""
    if not nlp:
        return []
    
    detected_entities = []
    try:
        doc = nlp(text)
        
        for ent in doc.ents:
            if ent.label_ in ["PERSON", "ORG", "GPE", "DATE", "MONEY", "CARDINAL"]:
                detected_entities.append({
                    "type": f"NER_{ent.label_}",
                    "text": ent.text,
                    "bbox": bbox,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "confidence": 0.8
                })
    except Exception as e:
        logger.warning(f"NER processing failed: {e}")
    
    return detected_entities

def detect_pii(ocr_data: List[Dict], selected_types: List[str] = None) -> List[Dict]:
    """Main PII detection function with type filtering"""
    all_detected_entities = []
    
    if not ocr_data:
        logger.warning("No OCR data provided")
        return []
    
    for block in ocr_data:
        text = block.get("text", "")
        bbox = block.get("bbox", [])
        
        if not text.strip():
            continue
        
        # Regex-based detection
        regex_entities = detect_pii_with_regex(text, bbox)
        all_detected_entities.extend(regex_entities)
        
        # NER-based detection (if available)
        ner_entities = detect_pii_with_ner(text, bbox)
        all_detected_entities.extend(ner_entities)
    
    # Remove duplicates based on text and type
    unique_entities = []
    seen_entities = set()
    
    for entity in all_detected_entities:
        entity_key = (entity["text"].lower(), entity["type"])
        if entity_key not in seen_entities:
            seen_entities.add(entity_key)
            unique_entities.append(entity)
    
    # Filter by selected types if provided
    if selected_types:
        # Map frontend types to backend types
        type_mapping = {
            "names": ["NAME", "NER_PERSON"],
            "addresses": ["ADDRESS", "NER_GPE"],
            "phones": ["PHONE"],
            "emails": ["EMAIL"],
            "ids": ["AADHAAR", "PAN", "PASSPORT", "DRIVING_LICENSE", "SSN"],
            "faces": [],  # Handled separately in image processing
        }
        
        allowed_types = []
        for selected_type in selected_types:
            if selected_type in type_mapping:
                allowed_types.extend(type_mapping[selected_type])
        
        if allowed_types:
            unique_entities = [e for e in unique_entities if e["type"] in allowed_types]
    
    logger.info(f"Detected {len(unique_entities)} PII entities after filtering")
    return unique_entities

def get_pii_summary(pii_entities: List[Dict]) -> Dict:
    """Get summary of detected PII types"""
    summary = {}
    for entity in pii_entities:
        pii_type = entity.get("type", "UNKNOWN")
        summary[pii_type] = summary.get(pii_type, 0) + 1
    
    return summary