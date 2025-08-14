from flask import Flask, render_template, request, jsonify, send_file
import os
import cv2
import pytesseract
from pdf2image import convert_from_path
from docx import Document
from PIL import Image, ImageDraw, ImageFont
import re
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# -------- Conversion functions --------
def convert_pdf_to_images(pdf_path):
    images = convert_from_path(pdf_path, dpi=300)
    image_paths = []
    for i, img in enumerate(images):
        img_path = pdf_path.replace('.pdf', f'_page{i+1}.png')
        img.save(img_path, 'PNG')
        image_paths.append(img_path)
    return image_paths

def convert_txt_to_image(txt_path):
    with open(txt_path, 'r', encoding='utf-8') as f:
        text = f.read()
    font = ImageFont.load_default()
    image = Image.new('RGB', (800, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.text((10, 10), text, fill=(0, 0, 0), font=font)
    image_path = txt_path.replace('.txt', '.png')
    image.save(image_path)
    return [image_path]

def convert_docx_to_image(docx_path):
    doc = Document(docx_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    font = ImageFont.load_default()
    image = Image.new('RGB', (800, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.text((10, 10), text, fill=(0, 0, 0), font=font)
    image_path = docx_path.replace('.docx', '.png')
    image.save(image_path)
    return [image_path]

# -------- Heading detection --------
def detect_headings(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    headings = {}
    for i, line in enumerate(lines):
        if (line.isupper() and len(line.split()) <= 6) or line.endswith(":") \
           or (1 <= len(line.split()) <= 4 and line.istitle()):
            context = " ".join(lines[i+1:i+4]).strip()
            if line not in headings:
                headings[line] = context
    return headings

# -------- OCR Extractor --------
def extract_headings_from_images(image_paths):
    all_text = []
    for img_path in image_paths:
        img = cv2.imread(img_path)
        if img is None:
            continue
        extracted_text = pytesseract.image_to_string(img)
        all_text.append(extracted_text)
    full_text = "\n".join(all_text)
    return detect_headings(full_text)

# -------- Routes --------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/verify", methods=["POST"])
def verify_template():
    if "resume" not in request.files or "template" not in request.files:
        return jsonify({"error": "Both resume and reference template must be uploaded."}), 400

    resume_file = request.files["resume"]
    template_file = request.files["template"]

    resume_ext = os.path.splitext(resume_file.filename)[1].lower()
    template_ext = os.path.splitext(template_file.filename)[1].lower()

    resume_path = os.path.join(UPLOAD_FOLDER, resume_file.filename)
    template_path = os.path.join(UPLOAD_FOLDER, template_file.filename)
    resume_file.save(resume_path)
    template_file.save(template_path)

    if resume_ext == ".pdf":
        resume_images = convert_pdf_to_images(resume_path)
    elif resume_ext == ".txt":
        resume_images = convert_txt_to_image(resume_path)
    elif resume_ext == ".docx":
        resume_images = convert_docx_to_image(resume_path)
    else:
        resume_images = [resume_path]

    if template_ext == ".pdf":
        template_images = convert_pdf_to_images(template_path)
    elif template_ext == ".txt":
        template_images = convert_txt_to_image(template_path)
    elif template_ext == ".docx":
        template_images = convert_docx_to_image(template_path)
    else:
        template_images = [template_path]

    template_headings = extract_headings_from_images(template_images)
    resume_headings = extract_headings_from_images(resume_images)

    results = []
    for heading, tmpl_context in template_headings.items():
        res_context = resume_headings.get(heading)
        if res_context is None:
            status = "missing"
            accuracy = 0
        elif tmpl_context.strip().lower() == res_context.strip().lower():
            status = "match"
            accuracy = 100
        else:
            status = "mismatch"
            tmpl_words = set(tmpl_context.lower().split())
            res_words = set(res_context.lower().split())
            accuracy = round((len(tmpl_words & res_words) / max(len(tmpl_words), 1)) * 100, 2)
        results.append({
            "heading": heading,
            "template_context": tmpl_context,
            "resume_context": res_context,
            "status": status,
            "accuracy": accuracy
        })

    request.session_data = results  # Store for PDF generation
    return jsonify({"results": results})

@app.route("/download_pdf", methods=["POST"])
def download_pdf():
    data = request.get_json()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph("<b>Resume Verification Report</b>", styles["Title"]), Spacer(1, 20)]

    for item in data["results"]:
        elements.append(Paragraph(f"<b>{item['heading']}</b> - {item['status'].upper()} (Accuracy: {item['accuracy']}%)", styles["Heading3"]))
        elements.append(Paragraph(f"<b>Template:</b> {item['template_context'] or 'N/A'}", styles["Normal"]))
        elements.append(Paragraph(f"<b>Resume:</b> {item['resume_context'] or 'N/A'}", styles["Normal"]))
        elements.append(Spacer(1, 12))

    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="verification_report.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    app.run(debug=True)
