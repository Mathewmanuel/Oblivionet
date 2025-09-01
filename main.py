import sys
import os
import json
from datetime import datetime
import importlib.util
from PIL import Image

# ✅ Force absolute paths for dynamic import
project_root = os.path.dirname(os.path.abspath(__file__))

ocr_path = os.path.join(project_root, "ocr_pipeline", "ocr_processor.py")
pii_path = os.path.join(project_root, "pii_detection", "pii_detector.py")
redactor_path = os.path.join(project_root, "redaction", "redactor.py")

def load_module(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

ocr_module = load_module("ocr_processor", ocr_path)
pii_module = load_module("pii_detector", pii_path)
redactor_module = load_module("redactor", redactor_path)

process_file = ocr_module.process_file
detect_pii = pii_module.detect_pii
redact_image = redactor_module.redact_image

def create_audit_log(file_name, pii_entities, page_num, log_folder="logs"):
    """
    Save audit log in JSON format.
    """
    if not os.path.exists(log_folder):
        os.makedirs(log_folder)

    log_data = {
        "file_name": file_name,
        "page": page_num,
        "timestamp": datetime.now().isoformat(),
        "detected_entities": pii_entities
    }

    log_file = os.path.join(log_folder, f"log_page_{page_num}.json")
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=4)

    return log_file

def merge_images_to_pdf(image_paths, output_pdf_path):
    """
    Merge multiple image files into a single PDF.
    """
    images = [Image.open(img).convert("RGB") for img in image_paths]
    if images:
        images[0].save(output_pdf_path, save_all=True, append_images=images[1:])
        print(f"[INFO] Final redacted PDF saved at: {output_pdf_path}")

def run_pipeline(file_path, output_folder="output"):
    """
    Complete pipeline: OCR -> PII detection -> Redaction -> Save outputs
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    print(f"Processing file: {file_path}")
    pages = process_file(file_path)  # OCR result

    redacted_images = []

    for page in pages:
        page_num = page["page"]
        image_path = page["image_path"]
        ocr_data = page["ocr_data"]

        print(f"\n[INFO] Page {page_num}: Running PII detection...")
        pii_entities = detect_pii(ocr_data)

        print(f"[INFO] Detected {len(pii_entities)} PII entities:")
        for e in pii_entities:
            print(f"  - {e['type']}: {e['text']}")

        # Save audit log
        log_path = create_audit_log(file_path, pii_entities, page_num)
        print(f"[INFO] Audit log saved: {log_path}")

        # Redact image
        output_img_path = os.path.join(output_folder, f"page_{page_num}_redacted.png")
        redact_image(image_path, pii_entities, output_img_path)
        redacted_images.append(output_img_path)

        print(f"[INFO] Redacted page saved: {output_img_path}")

    # ✅ Merge all redacted pages into one PDF
    final_pdf_path = os.path.join(output_folder, "final_redacted_document.pdf")
    merge_images_to_pdf(redacted_images, final_pdf_path)

if __name__ == "__main__":
    # Change this path to your sample PDF or image in the 'samples' folder
    test_file = "samples/test_doc.pdf"  # Example: samples/test_image.png
    run_pipeline(test_file)
