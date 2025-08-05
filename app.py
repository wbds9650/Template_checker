from flask import Flask, render_template, request, jsonify
import os
import cv2
import pytesseract
import json
from pdf2image import convert_from_path
from docx import Document
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Keywords to extract from template
target_keywords = [
    'name', 'contact', 'phone', 'mobile', 'reference', 'work experience', 'experience',
    'education', 'qualification', 'skill', 'skills', 'signature', 'date', 'dob', 'email', 'certificate',
    'passport', 'application', 'fresh', 'tatkaal', 'normal', '36 pages', '60 pages',
    'validity', 'minor', '10 years', 'up to age 18',
    'surname', 'given name', 'middle name', 'aliases', 'changed name',
    'place of birth', 'village', 'town', 'city',
    'state', 'district', 'marital status', 'single', 'married',
    'citizenship', 'birth', 'pan', 'voter id', 'employment', 'private',
    'government', 'educational qualification', 'graduate', 'ecr', 'non-ecr'
]


def convert_pdf_to_image(pdf_path):
    images = convert_from_path(pdf_path, dpi=300)
    image_path = pdf_path.replace('.pdf', '.png')
    images[0].save(image_path, 'PNG')
    return image_path

def convert_txt_to_image(txt_path):
    with open(txt_path, 'r', encoding='utf-8') as f:
        text = f.read()

    font = ImageFont.load_default()
    image = Image.new('RGB', (800, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.text((10, 10), text, fill=(0, 0, 0), font=font)

    image_path = txt_path.replace('.txt', '.png')
    image.save(image_path)
    return image_path

def convert_docx_to_image(docx_path):
    doc = Document(docx_path)
    text = "\n".join([para.text for para in doc.paragraphs])

    font = ImageFont.load_default()
    image = Image.new('RGB', (800, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.text((10, 10), text, fill=(0, 0, 0), font=font)

    image_path = docx_path.replace('.docx', '.png')
    image.save(image_path)
    return image_path

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/verify', methods=['POST'])
def verify_template():
    if 'resume' not in request.files or 'template' not in request.files:
        return jsonify({'error': 'Both resume and reference template must be uploaded.'}), 400

    resume_file = request.files['resume']
    template_file = request.files['template']

    resume_ext = os.path.splitext(resume_file.filename)[1].lower()
    template_ext = os.path.splitext(template_file.filename)[1].lower()

    resume_path = os.path.join(UPLOAD_FOLDER, resume_file.filename)
    template_path = os.path.join(UPLOAD_FOLDER, template_file.filename)

    resume_file.save(resume_path)
    template_file.save(template_path)

    # Convert non-image to image
    if resume_ext == '.pdf':
        resume_path = convert_pdf_to_image(resume_path)
    elif resume_ext == '.txt':
        resume_path = convert_txt_to_image(resume_path)
    elif resume_ext == '.docx':
        resume_path = convert_docx_to_image(resume_path)

    if template_ext == '.pdf':
        template_path = convert_pdf_to_image(template_path)
    elif template_ext == '.txt':
        template_path = convert_txt_to_image(template_path)
    elif template_ext == '.docx':
        template_path = convert_docx_to_image(template_path)

    # Generate field map from reference template
    template_image = cv2.imread(template_path)
    if template_image is None:
        return jsonify({'error': 'Invalid template image'}), 400

    h_t, w_t, _ = template_image.shape
    template_data = pytesseract.image_to_data(template_image, output_type=pytesseract.Output.DICT)

    field_map = {'fields': []}
    for i in range(len(template_data['text'])):
        text = template_data['text'][i].strip().lower()
        for keyword in target_keywords:
            if keyword in text:
                x, y, width, height = (template_data['left'][i], template_data['top'][i],
                                       template_data['width'][i], template_data['height'][i])
                field_map['fields'].append({
                    "text": template_data['text'][i].strip(),
                    "x": round(x / w_t * 100),
                    "y": round(y / h_t * 100),
                    "width": round(width / w_t * 100),
                    "height": round(height / h_t * 100)
                })
                break

    # Compare resume image against the reference fields
    resume_image = cv2.imread(resume_path)
    if resume_image is None:
        return jsonify({'error': 'Invalid resume image'}), 400

    h_r, w_r, _ = resume_image.shape
    resume_data = pytesseract.image_to_data(resume_image, output_type=pytesseract.Output.DICT)

    results = []
    for ref in field_map['fields']:
        ref_text = ref['text']
        ref_x = ref['x'] * w_r // 100
        ref_y = ref['y'] * h_r // 100

        match_found = False
        for i in range(len(resume_data['text'])):
            text = resume_data['text'][i].strip()
            if text.lower() == ref_text.lower():
                x, y = resume_data['left'][i], resume_data['top'][i]
                if abs(x - ref_x) <= 30 and abs(y - ref_y) <= 30:
                    match_found = True
                    break

        results.append({
            "text": ref_text,
            "match": match_found,
            "expected_position": [ref_x, ref_y],
        })

    return jsonify({"results": results})

if __name__ == '__main__':
    app.run(debug=True)
