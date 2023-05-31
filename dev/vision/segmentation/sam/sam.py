import cv2
import numpy as np
from segment_anything import SamPredictor, SamAutomaticMaskGenerator, sam_model_registry
from pprint import pprint

# Initialize SAM
sam = sam_model_registry["default"](checkpoint="sam_vit_h_4b8939.pth")
mask_generator = SamAutomaticMaskGenerator(sam)

print("Initialization complete.")

import pycocotools.mask as mutils

def process_masks(image, results):
    """Overlay masks on an image."""
    overlay = image.copy()

    for annotation in results:
        rle = annotation['segmentation']
        # Decode the RLE to get the mask
        mask = mutils.decode(rle)
        color = np.random.randint(0, 256, 3)  # Random color for each mask
        mask = cv2.resize(mask, (image.shape[1], image.shape[0]))
        overlay[mask > 0] = color
    cv2.addWeighted(overlay, 0.5, image, 0.5, 0, image)

    # return overlay


# Webcam feed
cap = cv2.VideoCapture(0)
import time
while True:
    ret, frame = cap.read()
    if not ret:
        break
    results = mask_generator.generate(frame)

    with open("results.txt", "w") as f:
        f.write(str(results) + "\n")


    process_masks(frame, results)
    cv2.imshow('SAM', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

    time.sleep(5)

cap.release()
cv2.destroyAllWindows()
