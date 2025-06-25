from flask import Flask, render_template, request, jsonify, send_file
import subprocess, os, io, zipfile

app = Flask(__name__)

# ---------- página principal ----------
@app.route('/')
def home():
    return render_template('index.html')

# ---------- executar comando ----------
@app.route('/run', methods=['POST'])
def run():
    cmd = (request.json or {}).get('command', '').strip()
    if not cmd:
        return jsonify(output='Nenhum comando recebido'), 400
    try:
        out = subprocess.check_output(
            cmd,
            shell=True,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15
        )
    except subprocess.CalledProcessError as e:
        out = e.output
    except Exception as e:
        out = str(e)
    return jsonify(output=out)

# ---------- upload ----------
@app.route('/upload', methods=['POST'])
def upload():
    f = request.files.get('file')
    if not f:
        return jsonify(msg='Nenhum arquivo enviado'), 400
    f.save(os.path.join(os.path.expanduser('~'), f.filename))
    return jsonify(msg=f'Upload concluído: {f.filename}')

# ---------- listar arquivos e pastas ----------
@app.route('/files')
def files():
    home = os.path.expanduser('~')
    entries = [
        {"name": n, "is_dir": os.path.isdir(os.path.join(home, n))}
        for n in os.listdir(home)
    ]
    return render_template('files.html', entries=entries)

# ---------- download arquivo ou pasta (zip) ----------
@app.route('/download/<path:target>')
def download(target):
    home = os.path.expanduser('~')
    path = os.path.join(home, target)
    if not os.path.exists(path):
        return 'Arquivo ou pasta não encontrado', 404

    if os.path.isdir(path):
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as z:
            root_len = len(os.path.dirname(path)) + 1
            for root, _, files in os.walk(path):
                for f in files:
                    abs_path = os.path.join(root, f)
                    rel_path = abs_path[root_len:]
                    z.write(abs_path, rel_path)
        mem.seek(0)
        return send_file(mem,
                         as_attachment=True,
                         download_name=f"{os.path.basename(path)}.zip")
    else:
        return send_file(path, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5090)
