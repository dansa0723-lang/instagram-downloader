import os
import re
import requests
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS

app = Flask(__name__, template_folder='.', static_folder='.')
CORS(app)

RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', 'ceb1656f4fmshaa112c5aba1f668p1037cdjsn2604f8be52c9')

HEADERS_DL = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.instagram.com/',
}

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/proxy')
def proxy():
    url = request.args.get('url', '')
    if not url:
        return 'URL inválida', 400
    try:
        r = requests.get(url, headers=HEADERS_DL, stream=True, timeout=20)
        content_type = r.headers.get('content-type', 'image/jpeg')
        def generate():
            for chunk in r.iter_content(chunk_size=8192):
                yield chunk
        return Response(generate(), headers={
            'Content-Type': content_type,
            'Cache-Control': 'public, max-age=3600',
        })
    except Exception as e:
        return str(e), 500

@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.get_json()
    url = data.get('url', '').strip()
    if not url or 'instagram.com' not in url:
        return jsonify({'error': 'URL inválida'}), 400
    try:
        r = requests.post(
            'https://snap-video3.p.rapidapi.com/download',
            headers={
                'x-rapidapi-host': 'snap-video3.p.rapidapi.com',
                'x-rapidapi-key': RAPIDAPI_KEY,
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            data={'url': url},
            timeout=30
        )
        result = r.json()
        if 'medias' not in result:
            return jsonify({'error': 'No se encontró contenido'}), 404

        title = result.get('title', 'instagram_post')
        thumbnail = result.get('thumbnail', '')
        medias = []

        for i, item in enumerate(result['medias']):
            media_url = item.get('url', '')
            if not media_url:
                continue
            ext = item.get('extension', 'jpg').lower()
            quality = item.get('quality', '')
            is_video = ext == 'mp4'
            # Usar la URL del media como thumbnail para imágenes
            # Para videos usar el thumbnail general
            thumb = media_url if not is_video else thumbnail
            medias.append({
                'index': i,
                'url': media_url,
                'thumb': thumb,
                'type': 'video/mp4' if is_video else 'image/jpeg',
                'ext': ext,
                'quality': quality,
            })

        return jsonify({
            'medias': medias,
            'count': len(medias),
            'title': title,
            'thumbnail': thumbnail,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def download():
    data = request.get_json()
    media_url = data.get('media_url', '').strip()
    filename = data.get('filename', 'instagram_media')
    ext = data.get('ext', 'jpg')
    if not media_url:
        return jsonify({'error': 'URL requerida'}), 400
    try:
        r = requests.get(media_url, stream=True, timeout=60, headers=HEADERS_DL)
        content_type = r.headers.get('content-type', 'image/jpeg')
        safe_name = re.sub(r'[^\w\-_]', '_', filename)[:60]
        fname = f"{safe_name}.{ext}"
        def generate():
            for chunk in r.iter_content(chunk_size=8192):
                yield chunk
        return Response(generate(), headers={
            'Content-Type': content_type,
            'Content-Disposition': f'attachment; filename="{fname}"'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
