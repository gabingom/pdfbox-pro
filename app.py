from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess, os, platform

app = Flask(__name__)
CORS(app)

# ── Séparateur classpath selon l'OS ──────────────────────────────────────────
SEP = ";" if platform.system() == "Windows" else ":"

# ── Chemins ──────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CLIENT_BIN = os.path.join(BASE_DIR, "CorbaPDFBoxClient", "bin")
LIB_DIR    = os.path.join(BASE_DIR, "lib")

# ── NOMS EXACTS des JARs ─────────────────────────────────────────────────────
JARS = [
    os.path.join(LIB_DIR, "pdfbox-2.0.29.jar"),      # ← nom exact
    os.path.join(LIB_DIR, "fontbox2.jar"),
    os.path.join(LIB_DIR, "commons-logging.jar"),
    os.path.join(LIB_DIR, "corba-jdk8.jar"),
]

CLASSPATH = SEP.join([CLIENT_BIN] + JARS)
ORB_ARGS  = ["-ORBInitialPort", "1050", "-ORBInitialHost", "localhost"]

def call_corba(action, args_input):
    cmd = ["java", "-cp", CLASSPATH, "CallClient", action] + args_input + ORB_ARGS
    print(f"[CMD] {' '.join(cmd)}", flush=True)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        out = result.stdout.strip()
        err = result.stderr.strip()
        print(f"[OUT] {out}", flush=True)
        if err: print(f"[ERR] {err}", flush=True)
        if result.returncode != 0 and not out:
            return f"ERREUR: {err or 'Erreur inconnue'}"
        return out if out else f"ERREUR: {err}"
    except subprocess.TimeoutExpired:
        return "ERREUR: Timeout — le serveur CORBA ne répond pas"
    except FileNotFoundError:
        return "ERREUR: java introuvable"

@app.route("/", methods=["GET"])
def home():
    return "pdfBOX Bridge actif", 200

@app.route("/merge", methods=["POST"])
def merge():
    d = request.json or {}
    return jsonify(result=call_corba("merge", [d.get("inputPaths",""), d.get("outputPath","")]))

@app.route("/split", methods=["POST"])
def split():
    d = request.json or {}
    return jsonify(result=call_corba("split", [d.get("inputPath",""), d.get("outputDir","")]))

@app.route("/extract", methods=["POST"])
def extract():
    d = request.json or {}
    return jsonify(result=call_corba("extract", [d.get("inputPath",""), str(d.get("pageNumber",1)), d.get("outputPath","")]))

@app.route("/delete", methods=["POST"])
def delete():
    d = request.json or {}
    return jsonify(result=call_corba("delete", [d.get("inputPath",""), str(d.get("pageNumber",1)), d.get("outputPath","")]))

@app.route("/protect", methods=["POST"])
def protect():
    d = request.json or {}
    return jsonify(result=call_corba("protect", [d.get("inputPath",""), d.get("password",""), d.get("outputPath","")]))

@app.route("/images", methods=["POST"])
def images():
    d = request.json or {}
    return jsonify(result=call_corba("images", [d.get("inputPath",""), d.get("outputDir",""), d.get("format","png")]))

@app.route("/text", methods=["POST"])
def text():
    d = request.json or {}
    return jsonify(result=call_corba("text", [d.get("inputPath","")]))

@app.route("/create", methods=["POST"])
def create():
    d = request.json or {}
    return jsonify(result=call_corba("create", [d.get("title",""), d.get("content",""), d.get("outputPath","")]))

if __name__ == "__main__":
    print(f"\n=== pdfBOX Bridge — classpath : {CLASSPATH} ===\n", flush=True)
    app.run(port=5000, debug=False)
