import os
import logging
from paddleocr import PaddleOCR
from pdf2image import convert_from_path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OCR model
ocr_model = PaddleOCR(use_angle_cls=True, lang='en')

def extract_text_from_image(image_path):
    """Extract text from image using PaddleOCR"""
    try:
        results = ocr_model.ocr(image_path)
        ocr_data = []
        
        if results and len(results) > 0 and results[0]:
            for line in results[0]:
                if line and len(line) >= 2:
                    bbox = line[0]  # bounding box
                    text_info = line[1]
                    if text_info and len(text_info) >= 2:
                        text = text_info[0]  # detected text
                        confidence = text_info[1]  # confidence score
                        ocr_data.append({
                            "text": text, 
                            "confidence": confidence, 
                            "bbox": bbox
                        })
        
        logger.info(f"Extracted {len(ocr_data)} text blocks from {image_path}")
        return ocr_data
    except Exception as e:
        logger.error(f"Error extracting text from {image_path}: {str(e)}")
        return []

def pdf_to_images(pdf_path, output_folder="uploads/temp_pages"):
    """Convert PDF pages to images"""
    try:
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        # Handle different poppler installations
        poppler_paths = [
            r"C:\poppler-25.07.0\Library\bin",  # Windows
            "/usr/bin",  # Linux
            "/opt/homebrew/bin"  # macOS
        ]
        
        images = None
        for poppler_path in poppler_paths:
            try:
                if os.path.exists(poppler_path):
                    images = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_path)
                    break
            except:
                continue
        
        # Try without poppler_path if above fails
        if images is None:
            images = convert_from_path(pdf_path, dpi=300)
        
        image_paths = []
        for i, img in enumerate(images):
            img_path = os.path.join(output_folder, f"page_{i + 1}.png")
            img.save(img_path, "PNG")
            image_paths.append(img_path)
        
        logger.info(f"Converted PDF to {len(image_paths)} images")
        return image_paths
    except Exception as e:
        logger.error(f"Error converting PDF to images: {str(e)}")
        return []

def extract_text_from_pdf(pdf_path):
    """Extract text from all pages of a PDF"""
    try:
        page_images = pdf_to_images(pdf_path)
        pages = []
        
        for page_num, img_path in enumerate(page_images, start=1):
            ocr_data = extract_text_from_image(img_path)
            pages.append({
                "page": page_num, 
                "image_path": img_path, 
                "ocr_data": ocr_data
            })
        
        logger.info(f"Processed {len(pages)} pages from PDF")
        return pages
    except Exception as e:
        logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
        return []