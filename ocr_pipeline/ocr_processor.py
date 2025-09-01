import os
from paddleocr import PaddleOCR
from pdf2image import convert_from_path

# Initialize PaddleOCR model
ocr_model = PaddleOCR(use_angle_cls=True)

def extract_text_from_image(image_path):
    results = ocr_model.ocr(image_path)
    extracted_text = []
    if results and len(results) > 0:
        for line in results[0]:
            if len(line) > 1 and isinstance(line[1], (list, tuple)) and len(line[1]) >= 2:
                text = line[1][0]        # text content
                confidence = line[1][1]  # confidence score
                extracted_text.append((text, confidence))
            else:
                # Fallback if confidence is missing
                text = str(line[1]) if len(line) > 1 else ""
                extracted_text.append((text, 0.0))
    return extracted_text



def pdf_to_images(pdf_path, output_folder="samples/temp_pages"):
    """
    Convert a PDF into a list of image paths (one per page).
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    images = convert_from_path(pdf_path, dpi=300, poppler_path=r"C:\poppler-25.07.0\Library\bin")
    image_paths = []

    for i, img in enumerate(images):
        img_path = os.path.join(output_folder, f"page_{i + 1}.png")
        img.save(img_path, "PNG")
        image_paths.append(img_path)

    return image_paths

def extract_text_from_pdf(pdf_path):
    """
    Perform OCR on all pages of a PDF and return combined results.
    """
    page_images = pdf_to_images(pdf_path)
    all_pages_data = []

    for page_num, img_path in enumerate(page_images, start=1):
        ocr_result = extract_text_from_image(img_path)
        all_pages_data.append({
            "page": page_num,
            "image_path": img_path,
            "ocr_data": ocr_result
        })

    return all_pages_data

def process_file(file_path):
    """
    Process a file (image or PDF) and return OCR data.
    """
    if file_path.lower().endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    else:
        ocr_result = extract_text_from_image(file_path)
        return [{
            "page": 1,
            "image_path": file_path,
            "ocr_data": ocr_result
        }]
