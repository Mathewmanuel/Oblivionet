import os
import logging
from typing import List, Dict, Any
from pdf2image import convert_from_path
from paddleocr import PaddleOCR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def pdf_to_images(pdf_path: str, output_folder: str, dpi: int = 300) -> List[str]:
    """
    Convert each page of a PDF into PNG images saved in output_folder/<pdf_name>/.
    Returns list of image file paths.
    """
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    pdf_output_folder = os.path.join(output_folder, pdf_name)
    os.makedirs(pdf_output_folder, exist_ok=True)
    image_paths = []
    try:
        logging.info(f"Converting PDF to images: {pdf_path}")
        pages = convert_from_path(pdf_path, dpi=dpi)
        for i, page in enumerate(pages):
            image_path = os.path.join(pdf_output_folder, f"page_{i+1}.png")
            page.save(image_path, "PNG")
            image_paths.append(image_path)
            logging.info(f"Saved page {i+1} image: {image_path}")
    except Exception as e:
        logging.error(f"Failed to convert PDF to images ({pdf_path}): {e}")
    return image_paths

def extract_text_from_image(image_path: str, ocr_model: PaddleOCR = None) -> List[Dict[str, Any]]:
    """
    Use PaddleOCR to extract text from a single image.
    Returns list of dicts with keys: text, confidence, bbox (4 points).
    """
    if ocr_model is None:
        ocr_model = PaddleOCR(use_angle_cls=True, lang='en')
    try:
        logging.info(f"Running OCR on image: {image_path}")
        result = ocr_model.ocr(image_path, cls=True)
        extracted = []
        for line in result:
            bbox = line[0]  # 4 points [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            text, conf = line[1]
            extracted.append({
                "text": text,
                "confidence": float(conf),
                "bbox": bbox
            })
        logging.info(f"Extracted {len(extracted)} text elements from {image_path}")
        return extracted
    except Exception as e:
        logging.error(f"OCR failed on image {image_path}: {e}")
        return []

def extract_text_from_pdf(pdf_path: str, temp_folder: str) -> List[Dict[str, Any]]:
    """
    Convert PDF pages to images and run OCR on each page.
    Returns list of dicts per page with page_number, image_path, ocr_results.
    """
    logging.info(f"Starting OCR extraction for PDF: {pdf_path}")
    image_paths = pdf_to_images(pdf_path, temp_folder)
    if not image_paths:
        logging.warning(f"No images generated for PDF: {pdf_path}")
        return []

    ocr_model = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
    page_results = []
    for i, img_path in enumerate(image_paths):
        page_num = i + 1
        try:
            ocr_results = extract_text_from_image(img_path, ocr_model)
            page_results.append({
                "page_number": page_num,
                "image_path": img_path,
                "ocr_results": ocr_results
            })
            logging.info(f"Completed OCR for page {page_num} of {pdf_path}")
        except Exception as e:
            logging.error(f"OCR failed for page {page_num} of {pdf_path}: {e}")
    return page_results

def process_all_pdfs_in_folder(
    input_folder: str,
    temp_folder: str
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Process all PDFs in input_folder.
    Returns dict mapping PDF filename to list of page OCR results.
    """
    logging.info(f"Processing all PDFs in folder: {input_folder}")
    results = {}
    if not os.path.exists(input_folder):
        logging.error(f"Input folder does not exist: {input_folder}")
        return results

    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith(".pdf")]
    if not pdf_files:
        logging.warning(f"No PDF files found in folder: {input_folder}")
        return results

    for pdf_file in pdf_files:
        pdf_path = os.path.join(input_folder, pdf_file)
        try:
            page_results = extract_text_from_pdf(pdf_path, temp_folder)
            results[pdf_file] = page_results
            logging.info(f"Finished processing {pdf_file}: {len(page_results)} pages")
        except Exception as e:
            logging.error(f"Failed to process {pdf_file}: {e}")
            results[pdf_file] = []

    logging.info("Completed processing all PDFs.")
    return results

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OCR Processor for PDFs")
    parser.add_argument("--input_folder", default="uploads", help="Folder containing PDFs to process")
    parser.add_argument("--temp_folder", default="uploads/temp_pages", help="Folder to save extracted images")
    args = parser.parse_args()

    all_results = process_all_pdfs_in_folder(args.input_folder, args.temp_folder)

    # Print summary
    for pdf_file, pages in all_results.items():
        print(f"{pdf_file}: {len(pages)} pages processed")
