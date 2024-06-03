import os
import io
from typing import List

import pypdfium2
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from PIL import Image
from pydantic import BaseModel
from surya.detection import batch_text_detection
from surya.layout import batch_layout_detection
from surya.model.detection.segformer import load_model, load_processor
from surya.model.recognition.model import load_model as load_rec_model
from surya.model.recognition.processor import load_processor as load_rec_processor
from surya.model.ordering.processor import load_processor as load_order_processor
from surya.model.ordering.model import load_model as load_order_model
from surya.ordering import batch_ordering
from surya.postprocessing.heatmap import draw_polys_on_image
from surya.ocr import run_ocr
from surya.postprocessing.text import draw_text_on_image
from surya.languages import CODE_TO_LANGUAGE
from surya.input.langs import replace_lang_with_code
from surya.schema import OCRResult, TextDetectionResult, LayoutResult, OrderResult
from surya.settings import settings

app = FastAPI()

# Load models and processors
det_model, det_processor = load_model(checkpoint=settings.DETECTOR_MODEL_CHECKPOINT), load_processor(checkpoint=settings.DETECTOR_MODEL_CHECKPOINT)
rec_model, rec_processor = load_rec_model(), load_rec_processor()
layout_model, layout_processor = load_model(checkpoint=settings.LAYOUT_MODEL_CHECKPOINT), load_processor(checkpoint=settings.LAYOUT_MODEL_CHECKPOINT)
order_model, order_processor = load_order_model(), load_order_processor()

class OCRRequest(BaseModel):
    languages: List[str] = ["English"]

def open_pdf(pdf_file):
    stream = io.BytesIO(pdf_file)
    return pypdfium2.PdfDocument(stream)

def get_page_image(pdf_file, page_num, dpi=96):
    doc = open_pdf(pdf_file)
    renderer = doc.render(
        pypdfium2.PdfBitmap.to_pil,
        page_indices=[page_num - 1],
        scale=dpi / 72,
    )
    png = list(renderer)[0]
    png_image = png.convert("RGB")
    return png_image

def page_count(pdf_file):
    doc = open_pdf(pdf_file)
    return len(doc)

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    file_type = file.content_type
    if "pdf" in file_type:
        page_number = 1  # default to the first page
        image = get_page_image(content, page_number)
    else:
        image = Image.open(io.BytesIO(content)).convert("RGB")
    
    return {"filename": file.filename, "file_type": file_type}

@app.post("/text-detection/")
async def text_detection(file: UploadFile = File(...)):
    content = await file.read()
    img = Image.open(io.BytesIO(content)).convert("RGB")
    pred = batch_text_detection([img], det_model, det_processor)[0]
    polygons = [p.polygon for p in pred.bboxes]
    det_img = draw_polys_on_image(polygons, img.copy())
    return {"detection_result": pred.model_dump(exclude=["heatmap", "affinity_map"])}

@app.post("/layout-detection/")
async def layout_detection(file: UploadFile = File(...)):
    content = await file.read()
    img = Image.open(io.BytesIO(content)).convert("RGB")
    _, det_pred = text_detection(img)
    pred = batch_layout_detection([img], layout_model, layout_processor, [det_pred])[0]
    polygons = [p.polygon for p in pred.bboxes]
    labels = [p.label for p in pred.bboxes]
    layout_img = draw_polys_on_image(polygons, img.copy(), labels=labels)
    return {"layout_result": pred.model_dump(exclude=["segmentation_map"])}









from fastapi import HTTPException, UploadFile, File, Form
from typing import List
from PIL import Image, UnidentifiedImageError
import io
import fitz  # PyMuPDF
import base64
import json
import tempfile
import os

def encode_image_to_base64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

@app.post("/ocr/")
async def ocr(file: UploadFile = File(...), languages: List[str] = Form(...)):
    content = await file.read()
    
    # Debugging print statements
    print("File content type:", type(content))
    print("File content length:", len(content))
    
    try:
        # Ensure the content is not empty
        if not content:
            raise HTTPException(status_code=400, detail="Empty file content")
        
        # Check if the file is a PDF
        if file.content_type == "application/pdf":
            pdf_file = io.BytesIO(content)
            doc = fitz.open(stream=pdf_file, filetype="pdf")
            images = []
            
            # Convert each page of the PDF to an image
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap()
                img = Image.open(io.BytesIO(pix.tobytes()))
                images.append(img.convert("RGB"))
            
            if not images:
                raise HTTPException(status_code=400, detail="No images found in PDF")
        else:
            # Assume it's an image file
            image_file = io.BytesIO(content)
            
            # Debugging print statement
            print("Attempting to open image from bytes")
            
            # Attempt to open the image
            img = Image.open(image_file).convert("RGB")
            
            # Debugging print statement
            print("Image opened successfully from bytes")
            
            images = [img]
    except UnidentifiedImageError as e:
        # More specific error message
        raise HTTPException(status_code=400, detail=f"Cannot identify image file: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing image file: {str(e)}")
    
    results = []
    for img in images:
        replace_lang_with_code(languages)
        img_pred = run_ocr([img], [languages], det_model, det_processor, rec_model, rec_processor)[0]

        bboxes = [l.bbox for l in img_pred.text_lines]
        text = [l.text for l in img_pred.text_lines]
        rec_img = draw_text_on_image(bboxes, text, img.size, languages, has_math="_math" in languages)
        
        # Encode image to base64
        rec_img_base64 = encode_image_to_base64(rec_img)
        
        # Ensure the OCR result is JSON-serializable
        ocr_result = json.loads(json.dumps(img_pred.model_dump(), default=str))
        
        results.append({
            "ocr_result": ocr_result,
            "image_base64": rec_img_base64
        })
    
    return {"results": results}
























@app.post("/order-detection/")
async def order_detection(file: UploadFile = File(...)):
    content = await file.read()
    img = Image.open(io.BytesIO(content)).convert("RGB")
    _, layout_pred = layout_detection(img)
    bboxes = [l.bbox for l in layout_pred.bboxes]
    pred = batch_ordering([img], [bboxes], order_model, order_processor)[0]
    polys = [l.polygon for l in pred.bboxes]
    positions = [str(l.position) for l in pred.bboxes]
    order_img = draw_polys_on_image(polys, img.copy(), labels=positions, label_font_size=20)
    return {"order_result": pred.model_dump()}

@app.get("/")
def read_root():
    return {"message": "Welcome to the Surya OCR API"}

# To run the app, use the following command:
# uvicorn main:app --reload