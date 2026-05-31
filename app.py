import os
import re
import requests
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS

app = Flask(__name__, template_folder='.', static_folder='.')
CORS(app)

RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', 'ceb1656f4fmshaa112c5aba1f668p1037cdjsn2604f8be52c9')
RAPIDAPI_HOST = 'instagram-post-reels-stories-downloader-api.p.rapidapi.com'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Referer': 'https://www.instagram.com/',
}

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/proxy')
def proxy():
    """Proxy para cargar imágenes/videos de Instagram sin CORS"""
    url = request.args.get('url', '')
    if not url or 'instagram' not in url and 'cdninstagram' not in url and 'fbcdn' not in url:
        return 'URL inválida', 400
    try:
        r = requests.get(url, headers=HEADERS, stream=True, timeout=20)
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
        r = requests.get(
            f'https://{RAPIDAPI_HOST}/instagram/',
            headers={'x-rapidapi-host': RAPIDAPI_HOST, 'x-rapidapi-key': RAPIDAPI_KEY},
            params={'url': url}, timeout=30
        )
        result = r.json()
        items = result if isinstance(result, list) else result.get('result', result.get('data', []))
        medias = []
        for i, item in enumerate(items if isinstance(items, list) else [items]):
            if not isinstance(item, dict): continue
            media_url = item.get('url', '')
            thumb = item.get('thumb', item.get('thumbnail', ''))
            if not thumb:
                thumb = media_url if 'image' in item.get('type','') else ''
            mtype = item.get('type', 'image/jpeg')
            size = int(item.get('size', 0))
            size_mb = f"{size/1024/1024:.1f} MB" if size > 0 else ''
            medias.append({'index': i, 'url': media_url, 'thumb': thumb, 'type': mtype, 'size': size_mb})
        if not medias:
            return jsonify({'error': 'No se encontró contenido'}), 404
        return jsonify({'medias': medias, 'count': len(medias)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def download():
    data = request.get_json()
    media_url = data.get('media_url', '').strip()
    filename = data.get('filename', 'instagram_media')
    if not media_url:
        return jsonify({'error': 'URL requerida'}), 400
    try:
        r = requests.get(media_url, stream=True, timeout=60, headers=HEADERS)
        content_type = r.headers.get('content-type', 'video/mp4')
        ext = 'mp4' if 'video' in content_type else 'jpg'
        safe_name = re.sub(r'[^\w\-_]', '_', filename)[:50]
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
