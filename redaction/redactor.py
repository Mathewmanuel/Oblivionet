import cv2
import os

def redact_image(image_path, pii_entities, output_path):
    """
    Apply blackout redaction to image based on detected PII entities.
    """
    img = cv2.imread(image_path)

    for entity in pii_entities:
        bbox = entity["bbox"]
        # Get rectangle coordinates
        x_min = int(min(p[0] for p in bbox))
        y_min = int(min(p[1] for p in bbox))
        x_max = int(max(p[0] for p in bbox))
        y_max = int(max(p[1] for p in bbox))

        # Draw black rectangle
        cv2.rectangle(img, (x_min, y_min), (x_max, y_max), (0, 0, 0), -1)

    cv2.imwrite(output_path, img)
    return output_path
