from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
import os, uuid, zipfile, io

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

UPLOAD = '/tmp/uploads'
OUTPUT = '/tmp/outputs'
os.makedirs(UPLOAD, exist_ok=True)
os.makedirs(OUTPUT, exist_ok=True)

def uid(): return uuid.uuid4().hex[:8]

def save(f):
    path = os.path.join(UPLOAD, f"{uid()}_{f.filename}")
    f.save(path)
    return path

@app.route('/')
def index():
    return send_file('static/index.html')

# 1. FUSION
@app.route('/merge', methods=['POST'])
def merge():
    files = request.files.getlist('files')
    if len(files) < 2:
        return jsonify(error="Selectionner au moins 2 fichiers PDF."), 400
    writer = PdfWriter()
    for f in files:
        for page in PdfReader(save(f)).pages:
            writer.add_page(page)
    out = os.path.join(OUTPUT, f"merged_{uid()}.pdf")
    with open(out, 'wb') as fh: writer.write(fh)
    return send_file(out, as_attachment=True, download_name='fusion.pdf')

# 2. DECOUPAGE
@app.route('/split', methods=['POST'])
def split():
    f = request.files.get('file')
    if not f: return jsonify(error="Aucun fichier recu."), 400
    reader = PdfReader(save(f))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(page)
            pb = io.BytesIO()
            writer.write(pb)
            zf.writestr(f"page_{i+1}.pdf", pb.getvalue())
    buf.seek(0)
    return send_file(buf, mimetype='application/zip', as_attachment=True, download_name='pages.zip')

# 3. EXTRAIRE PAGE
@app.route('/extract', methods=['POST'])
def extract():
    f = request.files.get('file')
    page_num = int(request.form.get('page', 1))
    if not f: return jsonify(error="Aucun fichier recu."), 400
    reader = PdfReader(save(f))
    if page_num < 1 or page_num > len(reader.pages):
        return jsonify(error=f"Page invalide. Ce PDF a {len(reader.pages)} page(s)."), 400
    writer = PdfWriter()
    writer.add_page(reader.pages[page_num - 1])
    out = os.path.join(OUTPUT, f"page_{uid()}.pdf")
    with open(out, 'wb') as fh: writer.write(fh)
    return send_file(out, as_attachment=True, download_name=f'page_{page_num}.pdf')

# 4. SUPPRIMER PAGE
@app.route('/delete', methods=['POST'])
def delete():
    f = request.files.get('file')
    page_num = int(request.form.get('page', 1))
    if not f: return jsonify(error="Aucun fichier recu."), 400
    reader = PdfReader(save(f))
    if page_num < 1 or page_num > len(reader.pages):
        return jsonify(error=f"Page invalide. Ce PDF a {len(reader.pages)} page(s)."), 400
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i != page_num - 1:
            writer.add_page(page)
    out = os.path.join(OUTPUT, f"deleted_{uid()}.pdf")
    with open(out, 'wb') as fh: writer.write(fh)
    return send_file(out, as_attachment=True, download_name='sans_page.pdf')

# 5. PROTEGER
@app.route('/protect', methods=['POST'])
def protect():
    f = request.files.get('file')
    password = request.form.get('password', '')
    if not f: return jsonify(error="Aucun fichier recu."), 400
    if not password: return jsonify(error="Mot de passe requis."), 400
    reader = PdfReader(save(f))
    writer = PdfWriter()
    for page in reader.pages: writer.add_page(page)
    writer.encrypt(password)
    out = os.path.join(OUTPUT, f"protected_{uid()}.pdf")
    with open(out, 'wb') as fh: writer.write(fh)
    return send_file(out, as_attachment=True, download_name='protege.pdf')

# 6. EXTRAIRE TEXTE
@app.route('/text', methods=['POST'])
def extract_text():
    f = request.files.get('file')
    if not f: return jsonify(error="Aucun fichier recu."), 400
    reader = PdfReader(save(f))
    text = ''
    for i, page in enumerate(reader.pages):
        t = page.extract_text()
        if t: text += f"--- Page {i+1} ---\n{t}\n\n"
    return jsonify(result=text.strip() or "(Aucun texte extractible)")

# 7. CREER PDF
@app.route('/create', methods=['POST'])
def create():
    data = request.json or {}
    title   = data.get('title', 'Document').strip()
    content = data.get('content', '').strip()
    if not content: return jsonify(error="Contenu vide."), 400
    out = os.path.join(OUTPUT, f"doc_{uid()}.pdf")
    doc = SimpleDocTemplate(out, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=25*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    t_style = ParagraphStyle('T', parent=styles['Title'], fontSize=20,
                             textColor=colors.HexColor('#1e293b'), spaceAfter=10)
    b_style = ParagraphStyle('B', parent=styles['Normal'], fontSize=12,
                             leading=18, textColor=colors.HexColor('#334155'))
    story = [Paragraph(title, t_style), Spacer(1, 6*mm)]
    for para in content.split('\n'):
        if para.strip():
            story.append(Paragraph(para.strip(), b_style))
            story.append(Spacer(1, 3*mm))
    doc.build(story)
    return send_file(out, as_attachment=True, download_name=f'{title[:40]}.pdf')

# 8. INFOS PDF
@app.route('/info', methods=['POST'])
def info():
    f = request.files.get('file')
    if not f: return jsonify(error="Aucun fichier recu."), 400
    reader = PdfReader(save(f))
    meta = reader.metadata or {}
    return jsonify({
        'pages':     len(reader.pages),
        'title':     meta.get('/Title', '—'),
        'author':    meta.get('/Author', '—'),
        'creator':   meta.get('/Creator', '—'),
        'encrypted': reader.is_encrypted
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
