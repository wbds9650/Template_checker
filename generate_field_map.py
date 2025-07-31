import cv2
import pytesseract
import json
import os

# Update if your Tesseract path is different
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

template_path = 'reference_template/resume.jpg'
output_path = 'field_map.json'

if not os.path.exists(template_path):
    raise FileNotFoundError(f"Template not found at: {template_path}")

# Load image and OCR
image = cv2.imread(template_path)
h, w, _ = image.shape
ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

# Target keywords to extract
target_keywords = ['name', 'contact', 'phone', 'mobile', 'reference', 'work experience', 'experience', 
                   'education', 'qualification', 'skill', 'skills', 'signature','date','dob','email']

fields = []

# Loop through OCR data
for i in range(len(ocr_data['text'])):
    text = ocr_data['text'][i].strip().lower()

    # Check for match with any keyword
    for keyword in target_keywords:
        if keyword in text:
            x, y, width, height = (ocr_data['left'][i], ocr_data['top'][i], 
                                   ocr_data['width'][i], ocr_data['height'][i])
            fields.append({
                "text": ocr_data['text'][i].strip(),  # original case
                "x": round(x / w * 100),
                "y": round(y / h * 100),
                "width": round(width / w * 100),
                "height": round(height / h * 100)
            })
            break  # prevent adding same word multiple times

# Save result
with open(output_path, 'w') as f:
    json.dump({"template": "full_template.png", "fields": fields}, f, indent=4)

print(f"✅ Extracted {len(fields)} fields to {output_path}")
