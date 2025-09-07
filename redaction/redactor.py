import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class PIIRedactor:
    def __init__(self):
        self.redaction_methods = {
            "blackout": self._blackout_redaction,
            "blur": self._blur_redaction,
            "pixelate": self._pixelate_redaction,
            "synthetic": self._synthetic_redaction
        }
    
    def _blackout_redaction(self, image, bbox):
        """Black out the PII region"""
        draw = ImageDraw.Draw(image)
        # Convert bbox to flat coordinates
        if len(bbox) == 4 and isinstance(bbox[0], list):
            # bbox is [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            x_coords = [point[0] for point in bbox]
            y_coords = [point[1] for point in bbox]
            bbox_flat = [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]
        else:
            bbox_flat = bbox
        
        draw.rectangle(bbox_flat, fill="black")
        return image
    
    def _blur_redaction(self, image, bbox):
        """Blur the PII region"""
        img_array = np.array(image)
        
        if len(bbox) == 4 and isinstance(bbox[0], list):
            x_coords = [point[0] for point in bbox]
            y_coords = [point[1] for point in bbox]
            x1, y1, x2, y2 = int(min(x_coords)), int(min(y_coords)), int(max(x_coords)), int(max(y_coords))
        else:
            x1, y1, x2, y2 = map(int, bbox)
        
        # Extract region and blur
        region = img_array[y1:y2, x1:x2]
        blurred_region = cv2.GaussianBlur(region, (15, 15), 0)
        img_array[y1:y2, x1:x2] = blurred_region
        
        return Image.fromarray(img_array)
    
    def _pixelate_redaction(self, image, bbox):
        """Pixelate the PII region"""
        img_array = np.array(image)
        
        if len(bbox) == 4 and isinstance(bbox[0], list):
            x_coords = [point[0] for point in bbox]
            y_coords = [point[1] for point in bbox]
            x1, y1, x2, y2 = int(min(x_coords)), int(min(y_coords)), int(max(x_coords)), int(max(y_coords))
        else:
            x1, y1, x2, y2 = map(int, bbox)
        
        # Extract region
        region = img_array[y1:y2, x1:x2]
        height, width = region.shape[:2]
        
        # Pixelate by downsizing and upsizing
        pixel_size = max(10, min(width, height) // 10)
        small = cv2.resize(region, (pixel_size, pixel_size), interpolation=cv2.INTER_LINEAR)
        pixelated = cv2.resize(small, (width, height), interpolation=cv2.INTER_NEAREST)
        
        img_array[y1:y2, x1:x2] = pixelated
        return Image.fromarray(img_array)
    
    def _synthetic_redaction(self, image, bbox):
        """Replace with synthetic data"""
        draw = ImageDraw.Draw(image)
        
        if len(bbox) == 4 and isinstance(bbox[0], list):
            x_coords = [point[0] for point in bbox]
            y_coords = [point[1] for point in bbox]
            bbox_flat = [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]
        else:
            bbox_flat = bbox
        
        # Fill with light gray and add "[REDACTED]" text
        draw.rectangle(bbox_flat, fill="lightgray", outline="gray")
        
        try:
            font = ImageFont.truetype("arial.ttf", 12)
        except:
            font = ImageFont.load_default()
        
        text_bbox = draw.textbbox((0, 0), "[REDACTED]", font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        text_x = bbox_flat[0] + (bbox_flat[2] - bbox_flat[0] - text_width) // 2
        text_y = bbox_flat[1] + (bbox_flat[3] - bbox_flat[1] - text_height) // 2
        
        draw.text((text_x, text_y), "[REDACTED]", fill="black", font=font)
        return image

def redact_image(image_path: str, pii_entities: List[Dict], output_path: str, method: str = "blackout"):
    """Redact PII from image"""
    try:
        redactor = PIIRedactor()
        image = Image.open(image_path)
        
        if method not in redactor.redaction_methods:
            logger.warning(f"Unknown redaction method: {method}. Using blackout.")
            method = "blackout"
        
        for entity in pii_entities:
            bbox = entity.get("bbox", [])
            if bbox:
                image = redactor.redaction_methods[method](image, bbox)
        
        image.save(output_path)
        logger.info(f"Redacted image saved to: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error redacting image: {str(e)}")
        return False
