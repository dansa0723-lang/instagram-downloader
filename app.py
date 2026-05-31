import os
import re
import json
import tempfile
import threading
import time
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "instadown"
DOWNLOAD_DIR.mkdir(exist_ok=True)

def parse_shortcode(url):
    url = url.strip().rstrip('/')
    for pat in [
        r'instagram\.com/p/([A-Za-z0-9_-]+)',
        r'instagram\.com/reel/([A-Za-z0-9_-]+)',
        r'instagram\.com/tv/([A-Za-z0-9_-]+)',
    ]:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None

def parse_profile(url):
    url = url.strip().rstrip('/')
    m = re.search(r'instagram\.com/([A-Za-z0-9_.]+)/?$', url)
    if m and m.group(1) not in ['p','reel','tv','stories','explore','accounts']:
        return m.group(1)
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url', '').strip()

    if not url or 'instagram.com' not in url:
        return jsonify({'error': 'URL de Instagram inválida'}), 400

    shortcode = parse_shortcode(url)
    username  = parse_profile(url)

    if not shortcode and not username:
        return jsonify({'error': 'No se reconoce el tipo de contenido'}), 400

    try:
        import instaloader
        L = instaloader.Instaloader(
            download_videos=True,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            post_metadata_txt_pattern="",
            dirname_pattern=str(DOWNLOAD_DIR / "{target}"),
            filename_pattern="{date_utc:%Y%m%d_%H%M%S}_{shortcode}",
        )

        files_before = set(DOWNLOAD_DIR.rglob('*'))

        if shortcode:
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            owner = post.owner_username
            dest = DOWNLOAD_DIR / owner
            dest.mkdir(exist_ok=True)
            L.dirname_pattern = str(dest)
            L.download_post(post, target=owner)

            files_after = set(DOWNLOAD_DIR.rglob('*'))
            new_files = [f for f in (files_after - files_before) if f.is_file() and f.suffix.lower() in {'.jpg','.jpeg','.png','.mp4','.mov'}]

            if not new_files:
                return jsonify({'error': 'No se encontraron archivos descargados'}), 500

            # Si es un solo archivo, devuélvelo directo
            if len(new_files) == 1:
                fpath = new_files[0]
                mime = 'video/mp4' if fpath.suffix.lower() == '.mp4' else 'image/jpeg'
                return send_file(str(fpath), mimetype=mime, as_attachment=True, download_name=fpath.name)

            # Si son varios (carrusel), devuelve el primero y lista el resto
            new_files.sort(key=lambda f: f.stat().st_mtime)
            return jsonify({
                'multiple': True,
                'count': len(new_files),
                'files': [f.name for f in new_files],
                'message': f'{len(new_files)} archivos descargados en el servidor'
            })

        elif username:
            profile = instaloader.Profile.from_username(L.context, username)
            return jsonify({
                'profile': True,
                'username': profile.username,
                'full_name': profile.full_name,
                'followers': profile.followers,
                'posts': profile.mediacount,
                'private': profile.is_private,
                'pic_url': profile.profile_pic_url,
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'service': 'InstaDown'})

# Limpieza automática de archivos temporales cada hora
def cleanup():
    while True:
        time.sleep(3600)
        now = time.time()
        for f in DOWNLOAD_DIR.rglob('*'):
            if f.is_file() and (now - f.stat().st_mtime) > 3600:
                try: f.unlink()
                except: pass

threading.Thread(target=cleanup, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
