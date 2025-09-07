import os
import logging
from PIL import Image
from ocr_pipeline.ocr_processor import extract_text_from_pdf
from pii_detection.pii_detector import detect_pii
from redaction.redactor import redact_image

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def merge_images_to_pdf(image_paths, output_pdf_path):
    """Merge redacted images back to PDF"""
    try:
        if not image_paths:
            logger.error("No images to merge")
            return None
            
        images = []
        for img_path in image_paths:
            if os.path.exists(img_path):
                try:
                    img = Image.open(img_path).convert("RGB")
                    images.append(img)
                    logger.info(f"Added image: {img_path}")
                except Exception as e:
                    logger.warning(f"Could not load image {img_path}: {e}")
            else:
                logger.warning(f"Image not found: {img_path}")
        
        if images:
            # Save as PDF
            images[0].save(
                output_pdf_path, 
                save_all=True, 
                append_images=images[1:] if len(images) > 1 else [],
                format='PDF'
            )
            logger.info(f"Final redacted PDF saved at: {output_pdf_path}")
            return output_pdf_path
        else:
            logger.error("No valid images to merge")
            return None
            
    except Exception as e:
        logger.error(f"Error merging images to PDF: {str(e)}")
        return None

def create_audit_log(input_path, output_path, pii_entities, log_path):
    """Create audit log for compliance"""
    try:
        import json
        from datetime import datetime
        
        # Create PII summary
        pii_summary = {}
        for entity in pii_entities:
            pii_type = entity.get("type", "UNKNOWN")
            pii_summary[pii_type] = pii_summary.get(pii_type, 0) + 1
        
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'input_file': os.path.basename(input_path),
            'output_file': os.path.basename(output_path) if output_path else None,
            'pii_entities_detected': len(pii_entities),
            'pii_types_summary': pii_summary,
            'processing_status': 'completed' if output_path else 'failed',
            'redaction_applied': True if output_path else False
        }
        
        with open(log_path, 'w') as log_file:
            json.dump(log_data, log_file, indent=2)
        
        logger.info(f"Audit log created: {log_path}")
        return log_path
        
    except Exception as e:
        logger.error(f"Error creating audit log: {str(e)}")
        return None

def run_pipeline(input_pdf_path, output_pdf_path, redaction_method="blackout", selected_pii_types=None):
    """Main pipeline to process PDF and redact PII"""
    try:
        logger.info(f"Starting OblivionNet pipeline for: {input_pdf_path}")
        logger.info(f"Redaction method: {redaction_method}")
        logger.info(f"Selected PII types: {selected_pii_types}")
        
        # Step 1: OCR extraction
        logger.info("Step 1: Extracting text from PDF...")
        pages = extract_text_from_pdf(input_pdf_path)
        if not pages:
            logger.error("Failed to extract pages from PDF")
            return None
        
        logger.info(f"Extracted {len(pages)} pages from PDF")
        
        redacted_images = []
        all_pii_entities = []
        
        # Step 2: Process each page
        logger.info("Step 2: Processing pages for PII detection and redaction...")
        for page_num, page in enumerate(pages, 1):
            logger.info(f"Processing page {page_num}/{len(pages)}")
            
            image_path = page["image_path"]
            ocr_data = page["ocr_data"]
            
            if not ocr_data:
                logger.warning(f"No OCR data for page {page_num}, skipping...")
                redacted_images.append(image_path)  # Use original
                continue
            
            # Detect PII with type filtering
            pii_entities = detect_pii(ocr_data, selected_pii_types)
            all_pii_entities.extend(pii_entities)
            
            logger.info(f"Found {len(pii_entities)} PII entities on page {page_num}")
            
            # Redact sensitive info
            output_img_path = image_path.replace(".png", "_redacted.png")
            
            if pii_entities:  # Only redact if PII found
                redaction_success = redact_image(image_path, pii_entities, output_img_path, redaction_method)
                if redaction_success:
                    redacted_images.append(output_img_path)
                    logger.info(f"Redacted page {page_num} saved to: {output_img_path}")
                else:
                    logger.warning(f"Redaction failed for page {page_num}, using original")
                    redacted_images.append(image_path)
            else:
                # No PII found, use original image
                redacted_images.append(image_path)
                logger.info(f"No PII found on page {page_num}, using original")
        
        # Step 3: Merge to PDF
        logger.info("Step 3: Merging redacted pages to PDF...")
        result_pdf = merge_images_to_pdf(redacted_images, output_pdf_path)
        
        if not result_pdf:
            logger.error("Failed to merge images to PDF")
            return None
        
        # Step 4: Create audit log
        log_path = output_pdf_path.replace(".pdf", "_audit.json")
        create_audit_log(input_pdf_path, output_pdf_path, all_pii_entities, log_path)
        
        # Step 5: Cleanup temporary files
        cleanup_temp_files(pages, redacted_images)
        
        logger.info(f"Pipeline completed successfully!")
        logger.info(f"Total PII entities found and redacted: {len(all_pii_entities)}")
        logger.info(f"Output PDF: {result_pdf}")
        
        return {
            "output_pdf": result_pdf,
            "audit_log": log_path,
            "pii_count": len(all_pii_entities),
            "pages_processed": len(pages),
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        return None

def cleanup_temp_files(pages, redacted_images):
    """Clean up temporary files"""
    try:
        # Clean up original page images
        for page in pages:
            img_path = page.get("image_path")
            if img_path and os.path.exists(img_path):
                try:
                    os.remove(img_path)
                    logger.debug(f"Cleaned up: {img_path}")
                except Exception as e:
                    logger.warning(f"Could not remove {img_path}: {e}")
        
        # Optionally clean up redacted images (keep for debugging)
        # for img_path in redacted_images:
        #     if os.path.exists(img_path):
        #         os.remove(img_path)
        
        logger.info("Temporary files cleaned up")
        
    except Exception as e:
        logger.warning(f"Error cleaning up temporary files: {str(e)}")

def process_single_image(image_path, output_path, redaction_method="blackout", selected_pii_types=None):
    """Process a single image file"""
    try:
        logger.info(f"Processing image: {image_path}")
        
        # Import here to avoid circular imports
        from ocr_pipeline.ocr_processor import extract_text_from_image
        
        # Extract text using OCR
        logger.info("Extracting text from image...")
        ocr_data = extract_text_from_image(image_path)
        
        if not ocr_data:
            logger.warning("No text found in image")
            return {
                "output_file": None,
                "pii_count": 0,
                "success": False,
                "message": "No text detected in image"
            }
        
        # Detect PII
        logger.info("Detecting PII entities...")
        pii_entities = detect_pii(ocr_data, selected_pii_types)
        logger.info(f"Found {len(pii_entities)} PII entities")
        
        # Apply redaction
        if pii_entities:
            logger.info(f"Applying {redaction_method} redaction...")
            success = redact_image(image_path, pii_entities, output_path, redaction_method)
            
            if success:
                logger.info(f"Image redaction completed: {output_path}")
                return {
                    "output_file": output_path,
                    "pii_count": len(pii_entities),
                    "success": True,
                    "message": "Image processed successfully"
                }
            else:
                logger.error("Image redaction failed")
                return {
                    "output_file": None,
                    "pii_count": len(pii_entities),
                    "success": False,
                    "message": "Redaction failed"
                }
        else:
            # No PII found, copy original
            import shutil
            shutil.copy2(image_path, output_path)
            logger.info("No PII found, original image copied")
            return {
                "output_file": output_path,
                "pii_count": 0,
                "success": True,
                "message": "No PII detected, original image returned"
            }
            
    except Exception as e:
        logger.error(f"Image processing failed: {str(e)}")
        return {
            "output_file": None,
            "pii_count": 0,
            "success": False,
            "message": f"Processing failed: {str(e)}"
        }

if __name__ == "__main__":
    # Test the pipeline
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python main.py <input_file> <output_file> [redaction_method]")
        print("Example: python main.py test.pdf output_redacted.pdf blackout")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    redaction_method = sys.argv[3] if len(sys.argv) > 3 else "blackout"
    
    if not os.path.exists(input_file):
        print(f"Input file not found: {input_file}")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Process based on file type
    file_ext = input_file.lower().split('.')[-1]
    
    if file_ext == 'pdf':
        result = run_pipeline(input_file, output_file, redaction_method)
        if result and result.get('success'):
            print(f"Success! Processed {result['pages_processed']} pages")
            print(f"Found and redacted {result['pii_count']} PII entities")
            print(f"Output: {result['output_pdf']}")
            if result.get('audit_log'):
                print(f"Audit log: {result['audit_log']}")
        else:
            print("Processing failed!")
            sys.exit(1)
    
    elif file_ext in ['png', 'jpg', 'jpeg']:
        result = process_single_image(input_file, output_file, redaction_method)
        if result['success']:
            print(f"Success! {result['message']}")
            print(f"Found and redacted {result['pii_count']} PII entities")
            print(f"Output: {result['output_file']}")
        else:
            print(f"Processing failed: {result['message']}")
            sys.exit(1)
    
    else:
        print(f"Unsupported file type: {file_ext}")
        print("Supported types: PDF, PNG, JPG, JPEG")
        sys.exit(1)