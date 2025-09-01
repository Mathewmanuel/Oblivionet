import cv2

def redact_image(image_path, pii_entities, output_path):
    """
    Apply blur redaction to image based on detected PII entities.
    """
    img = cv2.imread(image_path)

    for entity in pii_entities:
        box = entity["box"]
        x_min = int(min(p[0] for p in box))
        y_min = int(min(p[1] for p in box))
        x_max = int(max(p[0] for p in box))
        y_max = int(max(p[1] for p in box))

        # Extract the region of interest
        roi = img[y_min:y_max, x_min:x_max]
        if roi.size > 0:  # Ensure the region exists
            # Apply Gaussian Blur
            blurred = cv2.GaussianBlur(roi, (51, 51), 30)
            img[y_min:y_max, x_min:x_max] = blurred

    cv2.imwrite(output_path, img)
    return output_path
