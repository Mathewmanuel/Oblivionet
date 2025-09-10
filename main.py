import os
import sys
import re
import json
import shutil
import logging
import tempfile
import datetime
from typing import List, Dict, Tuple, Optional, Any

from pdf2image import convert_from_path
from paddleocr import PaddleOCR
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import cv2
import numpy as np
import fitz  # PyMuPDF for PDF merging

try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
except Exception:
    nlp = None
    logging.warning("spaCy model 'en_core_web_sm' not found. NER disabled.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Regex patterns for PII detection
REGEX_PATTERNS = {
    "EMAIL": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
    "PHONE": re.compile(r'\b(\+91[\-\s]?)?(\(?\d{3,5}\)?[\-\s]?)?[\d\s\-]{6,12}\b'),
    "AADHAAR": re.compile(r'\b\d{4}\s\d{4}\s\d{4}\b'),
    "PAN": re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b'),
    "SSN": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    "CREDIT_CARD": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
    "DOB": re.compile(r'\b(0?[1-9]|[12][0-9]|3[01])[-/](0?[1-9]|1[012])[-/](\d{2}|\d{4})\b'),
    "PASSPORT": re.compile(r'\b[A-PR-WYa-pr-wy][0-9]{7}\b'),
    "DRIVING_LICENSE": re.compile(r'\b[A-Z]{2}\d{2}[0-9A-Z]{11}\b'),
    "BANK_ACCOUNT": re.compile(r'\b\d{9,18}\b'),
    "IFSC": re.compile(r'\b[A-Z]{4}0[A-Z0-9]{6}\b'),
    "PINCODE": re.compile(r'\b\d{6}\b'),
    "NAME_PREFIX": re.compile(r'\b(Mr|Mrs|Ms|Dr|Prof|Miss|Mx)\.?\s+[A-Z][a-z]+\b'),
    "ADDRESS": re.compile(r'\b[\w\s,.-]+(?:Street|Road|Nagar|Colony|Avenue|Lane|Boulevard|Drive|Park|Square|Terrace)\b', re.I),
}

NER_LABEL_MAP = {
    "PERSON": "PERSON",
    "ORG": "ORG",
    "GPE": "GPE",
    "DATE": "DATE",
    "MONEY": "MONEY",
    "CARDINAL": "CARDINAL",
}

class PIIRedactor:
    def __init__(self):
        # Try to load font for synthetic redaction text
        try:
            self.font = ImageFont.truetype("arial.ttf", 20)
        except Exception:
            self.font = None

    def blackout(self, img: Image.Image, bbox: Tuple[int, int, int, int]) -> None:
        draw = ImageDraw.Draw(img)
        draw.rectangle(bbox, fill="black")

    def blur(self, img: Image.Image, bbox: Tuple[int, int, int, int], ksize: int = 25) -> None:
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        x0, y0, x1, y1 = bbox
        roi = cv_img[y0:y1, x0:x1]
        if roi.size == 0:
            return
        ksize = max(3, ksize // 2 * 2 + 1)
        blurred = cv2.GaussianBlur(roi, (ksize, ksize), 0)
        cv_img[y0:y1, x0:x1] = blurred
        img.paste(Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)))

    def pixelate(self, img: Image.Image, bbox: Tuple[int, int, int, int], pixel_size: int = 10) -> None:
        x0, y0, x1, y1 = bbox
        region = img.crop(bbox)
        small = region.resize(
            ((x1 - x0) // pixel_size or 1, (y1 - y0) // pixel_size or 1),
            resample=Image.NEAREST
        )
        pixelated = small.resize(region.size, Image.NEAREST)
        img.paste(pixelated, bbox)

    def synthetic(self, img: Image.Image, bbox: Tuple[int, int, int, int]) -> None:
        draw = ImageDraw.Draw(img)
        x0, y0, x1, y1 = bbox
        draw.rectangle(bbox, fill=(200, 200, 200))
        text = "[REDACTED]"
        font = self.font
        w, h = draw.textsize(text, font=font)
        text_x = x0 + ((x1 - x0) - w) // 2
        text_y = y0 + ((y1 - y0) - h) // 2
        draw.text((text_x, text_y), text, fill="black", font=font)

def detect_pii_with_regex(text: str, bbox: List[int]) -> List[Dict]:
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
    if nlp is None:
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

def detect_pii(
    ocr_data: List[Dict],
    selected_types: Optional[List[str]] = None
) -> List[Dict]:
    all_entities = []
    for block in ocr_data:
        text = block.get("text", "")
        bbox = block.get("bbox", [0, 0, 0, 0])
        if not text:
            continue
        regex_entities = detect_pii_with_regex(text, bbox)
        ner_entities = detect_pii_with_ner(text, bbox)
        all_entities.extend(regex_entities)
        all_entities.extend(ner_entities)

    if selected_types:
        selected_types_upper = set(t.upper() for t in selected_types)
        all_entities = [e for e in all_entities if e["type"].upper() in selected_types_upper]

    unique = []
    seen = set()
    for ent in all_entities:
        key = (ent["text"].lower(), ent["type"].upper())
        if key not in seen:
            seen.add(key)
            unique.append(ent)
    return unique

def redact_image(
    image_path: str,
    pii_entities: List[Dict],
    output_path: str,
    method: str = "blackout"
) -> None:
    try:
        img = Image.open(image_path).convert("RGB")
    except Exception as e:
        logging.error(f"Failed to open image {image_path}: {e}")
        return

    redactor = PIIRedactor()
    method_func = getattr(redactor, method, None)
    if method_func is None:
        logging.warning(f"Redaction method '{method}' not found. Using blackout.")
        method_func = redactor.blackout

    for ent in pii_entities:
        bbox = ent.get("bbox")
        if bbox and len(bbox) == 4:
            bbox_int = tuple(max(0, int(c)) for c in bbox)
            method_func(img, bbox_int)

    try:
        img.save(output_path)
        logging.info(f"Saved redacted image to {output_path}")
    except Exception as e:
        logging.error(f"Failed to save redacted image {output_path}: {e}")

def ocr_image(image_path: str, ocr_model: PaddleOCR) -> List[Dict]:
    try:
        result = ocr_model.ocr(image_path, cls=True)
    except Exception as e:
        logging.error(f"OCR failed on image {image_path}: {e}")
        return []

    ocr_data = []
    for line in result:
        bbox_points = line[0]
        text, conf = line[1]
        xs = [int(p[0]) for p in bbox_points]
        ys = [int(p[1]) for p in bbox_points]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        ocr_data.append({
            "text": text,
            "confidence": float(conf),
            "bbox": bbox
        })
    return ocr_data

def run_pipeline(
    input_pdf_path: str,
    output_pdf_path: str,
    redaction_method: str = "blackout",
    selected_pii_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    logging.info(f"Starting pipeline for PDF: {input_pdf_path}")
    temp_dir = tempfile.mkdtemp(prefix="docproc_")
    temp_images_dir = os.path.join(temp_dir, "pages")
    os.makedirs(temp_images_dir, exist_ok=True)
    redacted_images_dir = os.path.join(temp_dir, "redacted")
    os.makedirs(redacted_images_dir, exist_ok=True)

    ocr_model = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
    audit_log = {
        "timestamp": datetime.datetime.now().isoformat(),
        "input_file": input_pdf_path,
        "output_file": output_pdf_path,
        "total_pii_entities": 0,
        "pii_count_by_type": {},
        "pages_processed": 0,
        "status": "success"
    }

    try:
        pages = convert_from_path(input_pdf_path, dpi=300)
    except Exception as e:
        logging.error(f"Failed to convert PDF to images: {e}")
        audit_log["status"] = "failure"
        shutil.rmtree(temp_dir)
        return audit_log

    all_pii_entities = []
    redacted_image_paths = []

    for i, page_img in enumerate(pages):
        page_num = i + 1
        page_image_path = os.path.join(temp_images_dir, f"page_{page_num}.png")
        redacted_image_path = os.path.join(redacted_images_dir, f"page_{page_num}_redacted.png")
        try:
            page_img.save(page_image_path)
            logging.info(f"Saved page {page_num} image: {page_image_path}")
        except Exception as e:
            logging.error(f"Failed to save page {page_num} image: {e}")
            continue

        ocr_data = ocr_image(page_image_path, ocr_model)
        if not ocr_data:
            logging.warning(f"No OCR data for page {page_num}, skipping redaction.")
            continue

        pii_entities = detect_pii(ocr_data, selected_pii_types)
        all_pii_entities.extend(pii_entities)

        redact_image(page_image_path, pii_entities, redacted_image_path, redaction_method)
        redacted_image_paths.append(redacted_image_path)
        audit_log["pages_processed"] += 1

    # Count PII by type
    pii_count = {}
    for ent in all_pii_entities:
        t = ent["type"].upper()
        pii_count[t] = pii_count.get(t, 0) + 1
    audit_log["total_pii_entities"] = len(all_pii_entities)
    audit_log["pii_count_by_type"] = pii_count

    # Merge redacted images into PDF
    if redacted_image_paths:
        try:
            doc = fitz.open()
            for img_path in redacted_image_paths:
                imgdoc = fitz.open(img_path)
                rect = imgdoc[0].rect
                pdfbytes = imgdoc.convert_to_pdf()
                imgpdf = fitz.open("pdf", pdfbytes)
                page = doc.new_page(width=rect.width, height=rect.height)
                page.show_pdf_page(rect, imgpdf, 0)
            doc.save(output_pdf_path)
            logging.info(f"Saved redacted PDF to {output_pdf_path}")
        except Exception as e:
            logging.error(f"Failed to merge redacted images into PDF: {e}")
            audit_log["status"] = "failure"
    else:
        logging.error("No redacted images to merge, output PDF not created.")
        audit_log["status"] = "failure"

    # Save audit log JSON next to output PDF
    audit_log_path = os.path.splitext(output_pdf_path)[0] + "_audit_log.json"
    try:
        with open(audit_log_path, "w", encoding="utf-8") as f:
            json.dump(audit_log, f, indent=2)
        logging.info(f"Saved audit log to {audit_log_path}")
    except Exception as e:
        logging.error(f"Failed to save audit log: {e}")

    # Cleanup temp files
    try:
        shutil.rmtree(temp_dir)
        logging.info("Cleaned up temporary files.")
    except Exception as e:
        logging.warning(f"Failed to clean up temp files: {e}")

    return audit_log

def process_single_image(
    input_image_path: str,
    output_image_path: str,
    redaction_method: str = "blackout",
    selected_pii_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    logging.info(f"Starting pipeline for image: {input_image_path}")
    ocr_model = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
    audit_log = {
        "timestamp": datetime.datetime.now().isoformat(),
        "input_file": input_image_path,
        "output_file": output_image_path,
        "total_pii_entities": 0,
        "pii_count_by_type": {},
        "status": "success"
    }

    ocr_data = ocr_image(input_image_path, ocr_model)
    if not ocr_data:
        logging.error("No OCR data extracted from image.")
        audit_log["status"] = "failure"
        return audit_log

    pii_entities = detect_pii(ocr_data, selected_pii_types)
    audit_log["total_pii_entities"] = len(pii_entities)
    pii_count = {}
    for ent in pii_entities:
        t = ent["type"].upper()
        pii_count[t] = pii_count.get(t, 0) + 1
    audit_log["pii_count_by_type"] = pii_count

    redact_image(input_image_path, pii_entities, output_image_path, redaction_method)
    logging.info(f"Saved redacted image to {output_image_path}")

    # Save audit log JSON next to output image
    audit_log_path = os.path.splitext(output_image_path)[0] + "_audit_log.json"
    try:
        with open(audit_log_path, "w", encoding="utf-8") as f:
            json.dump(audit_log, f, indent=2)
        logging.info(f"Saved audit log to {audit_log_path}")
    except Exception as e:
        logging.error(f"Failed to save audit log: {e}")

    return audit_log

def main():
    if len(sys.argv) < 3:
        print("Usage: python main.py <input_file> <output_file> [redaction_method]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    redaction_method = sys.argv[3] if len(sys.argv) > 3 else "blackout"
    redaction_method = redaction_method.lower()
    if redaction_method not in {"blackout", "blur", "pixelate", "synthetic"}:
        logging.warning(f"Unknown redaction method '{redaction_method}', defaulting to blackout.")
        redaction_method = "blackout"

    # Optional: filter PII types to redact (hardcoded here, can be extended)
    selected_pii_types = None  # e.g. ["EMAIL", "PHONE", "PERSON"]

    if not os.path.exists(input_path):
        logging.error(f"Input file does not exist: {input_path}")
        sys.exit(1)

    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".pdf":
        audit = run_pipeline(input_path, output_path, redaction_method, selected_pii_types)
    elif ext in {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
        audit = process_single_image(input_path, output_path, redaction_method, selected_pii_types)
    else:
        logging.error(f"Unsupported input file type: {ext}")
        sys.exit(1)

    logging.info("Processing complete.")
    logging.info(f"Pages processed: {audit.get('pages_processed', 'N/A')}")
    logging.info(f"Total PII entities detected: {audit.get('total_pii_entities', 0)}")
    logging.info(f"Output file: {audit.get('output_file')}")
    audit_log_path = os.path.splitext(output_path)[0] + "_audit_log.json"
    logging.info(f"Audit log: {audit_log_path}")

if __name__ == "__main__":
    main()
