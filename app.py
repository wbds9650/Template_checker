from flask import Flask, render_template, request, jsonify
import os
import cv2
import pytesseract
import json

app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Keywords to extract from template
target_keywords = ['name', 'contact', 'phone', 'mobile', 'reference', 'work experience', 'experience',
                   'education', 'qualification', 'skill', 'skills', 'signature', 'date', 'dob', 'email','certificate']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/verify', methods=['POST'])
def verify_template():
    if 'resume' not in request.files or 'template' not in request.files:
        return jsonify({'error': 'Both resume and reference template must be uploaded.'}), 400

    resume_file = request.files['resume']
    template_file = request.files['template']

    resume_path = os.path.join(UPLOAD_FOLDER, resume_file.filename)
    template_path = os.path.join(UPLOAD_FOLDER, template_file.filename)

    resume_file.save(resume_path)
    template_file.save(template_path)

    #Generate field map from reference template
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

    #Compare resume image against the reference fields
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
