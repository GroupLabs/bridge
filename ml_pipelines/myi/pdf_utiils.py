from pdf2image import convert_from_path
from PIL import Image
import pytesseract

def handle_uploaded_file(uploaded_file, target_path):
    # Create a new file in write-binary mode
    with open(target_path, 'wb') as destination:
        # Write the contents of the uploaded file to the new file
        destination.write(uploaded_file.read())  # Read the entire content at once
    
    # Return the path of the saved file
    return target_path

def pdf_to_image(pdf_path):
    images = convert_from_path(pdf_path)

    # Calculate the total height of all images (assuming they have the same width)
    total_height = sum(img.size[1] for img in images)
    max_width = max(img.size[0] for img in images)

    # Create a new image with the appropriate height and width
    combined_image = Image.new('RGB', (max_width, total_height))

    # Paste the images together
    y_offset = 0
    for img in images:
        combined_image.paste(img, (0, y_offset))
        y_offset += img.size[1]

    return combined_image