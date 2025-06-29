from flask import Flask, render_template, request, jsonify, send_file
import subprocess, os, io, zipfile
from werkzeug.utils import secure_filename
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
import datetime
import os
import platform

app = Flask(__name__)

# Configurar logging
logging.basicConfig(filename='app.log', level=logging.INFO)

# Configurar limitação de taxa
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=["200 per day", "50 per hour"]
)

# Arquivo para histórico de comandos
HISTORY_FILE = os.path.join(os.path.expanduser('~'), '.webshell_history')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/run', methods=['POST'])
@limiter.limit("5 per minute")
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
    
    # Salvar comando no histórico
    try:
        with open(HISTORY_FILE, 'a') as f:
            f.write(f"{datetime.datetime.now().isoformat()} | {cmd}\n")
    except Exception:
        pass
    
    return jsonify(output=out)

@app.route('/history')
def history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                commands = [line.split('|', 1)[1].strip() for line in f.readlines()]
                # Remover duplicatas mantendo a ordem
                seen = set()
                unique_commands = [cmd for cmd in commands if not (cmd in seen or seen.add(cmd))]
                return jsonify(history=unique_commands[-100:])  # Últimos 100 comandos
    except Exception:
        pass
    return jsonify(history=[])

@app.route('/upload', methods=['POST'])
def upload():
    f = request.files.get('file')
    if not f:
        return jsonify(msg='Nenhum arquivo enviado'), 400
    # Sanitizar o nome do arquivo
    filename = secure_filename(f.filename)
    if filename == '':
        return jsonify(msg='Nome de arquivo inválido'), 400
    home = os.path.expanduser('~')
    f.save(os.path.join(home, filename))
    return jsonify(msg=f'Upload concluído: {filename}')

@app.route('/files', defaults={'path': ''})
@app.route('/files/<path:path>')
def files(path):
    home = os.path.expanduser('~')
    full_path = os.path.join(home, path)
    
    # Validar se o caminho está dentro do home
    if not os.path.abspath(full_path).startswith(os.path.abspath(home)):
        return 'Acesso negado', 403
    
    if not os.path.exists(full_path):
        return 'Arquivo ou pasta não encontrado', 404
    
    if os.path.isfile(full_path):
        return send_file(full_path, as_attachment=True)
    
    entries = []
    # Adicionar link para pasta superior
    if path != '':
        parent_dir = os.path.dirname(path.rstrip('/'))
        entries.append({
            "name": "..",
            "is_dir": True,
            "path": parent_dir
        })
    
    for n in os.listdir(full_path):
        if n == "..":
            continue
        abs_path = os.path.join(full_path, n)
        rel_path = os.path.join(path, n)
        entries.append({
            "name": n,
            "is_dir": os.path.isdir(abs_path),
            "path": rel_path
        })
    return render_template('files.html', entries=entries, current_path=path)

@app.route('/download/<path:target>')
def download(target):
    home = os.path.expanduser('~')
    full_path = os.path.join(home, target)
    
    # Validar se o caminho está dentro do home
    if not os.path.abspath(full_path).startswith(os.path.abspath(home)):
        return 'Acesso negado', 403
    
    if not os.path.exists(full_path):
        return 'Arquivo ou pasta não encontrado', 404

    if os.path.isdir(full_path):
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as z:
            root_len = len(os.path.dirname(full_path)) + 1
            for root, _, files in os.walk(full_path):
                for f in files:
                    abs_path = os.path.join(root, f)
                    rel_path = abs_path[root_len:]
                    z.write(abs_path, rel_path)
        mem.seek(0)
        return send_file(mem,
                         as_attachment=True,
                         download_name=f"{os.path.basename(full_path)}.zip")
    else:
        return send_file(full_path, as_attachment=True)

# Adicionar cabeçalhos de segurança
@app.after_request
def add_security_headers(resp):
    resp.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return resp

if __name__ == '__main__':
    # Limpar o terminal antes de mostrar a mensagem
    os.system('cls' if platform.system() == 'Windows' else 'clear')
    print("webshell rodando em localhost:5090")
    app.run(host='0.0.0.0', port=5090)
