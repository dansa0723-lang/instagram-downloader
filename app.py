import os
import re
import time
import requests
import tempfile
import threading
from pathlib import Path
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS

app = Flask(__name__, template_folder='.', static_folder='.')
CORS(app)

RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', 'ceb1656f4fmshaa112c5aba1f668p1037cdjsn2604f8be52c9')
RAPIDAPI_HOST = 'instagram-post-reels-stories-downloader-api.p.rapidapi.com'

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url', '').strip()

    if not url or 'instagram.com' not in url:
        return jsonify({'error': 'URL de Instagram inválida'}), 400

    try:
        # Llamar a la API de RapidAPI
        response = requests.get(
            'https://instagram-post-reels-stories-downloader-api.p.rapidapi.com/instagram/',
            headers={
                'Content-Type': 'application/json',
                'x-rapidapi-host': RAPIDAPI_HOST,
                'x-rapidapi-key': RAPIDAPI_KEY,
            },
            params={'url': url},
            timeout=30
        )

        if response.status_code != 200:
            return jsonify({'error': f'Error de API: {response.status_code}'}), 500

        result = response.json()

        # Extraer URLs de descarga del resultado
        download_urls = []

        # La API puede devolver diferentes estructuras
        if isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    for key in ['url', 'download_url', 'video_url', 'image_url', 'src']:
                        if key in item and item[key]:
                            download_urls.append({'url': item[key], 'type': item.get('type', 'video')})
                            break
        elif isinstance(result, dict):
            # Buscar URLs en diferentes campos
            for key in ['url', 'download_url', 'video_url', 'media_url']:
                if key in result and result[key]:
                    download_urls.append({'url': result[key], 'type': 'video'})
            # Buscar en arrays dentro del resultado
            for key in ['data', 'medias', 'items', 'result']:
                if key in result and isinstance(result[key], list):
                    for item in result[key]:
                        if isinstance(item, dict):
                            for ukey in ['url', 'download_url', 'video_url', 'src']:
                                if ukey in item and item[ukey]:
                                    download_urls.append({'url': item[ukey], 'type': item.get('type', 'video')})
                                    break

        if not download_urls:
            # Devolver el resultado raw para debug
            return jsonify({'error': 'No se encontraron URLs de descarga', 'raw': result}), 500

        if len(download_urls) == 1:
            # Descargar y servir el archivo directamente
            media_url = download_urls[0]['url']
            media_response = requests.get(media_url, stream=True, timeout=60)
            content_type = media_response.headers.get('content-type', 'video/mp4')
            
            # Determinar nombre del archivo
            ext = 'mp4' if 'video' in content_type else 'jpg'
            filename = f'instagram_media.{ext}'

            def generate():
                for chunk in media_response.iter_content(chunk_size=8192):
                    yield chunk

            return Response(
                generate(),
                headers={
                    'Content-Type': content_type,
                    'Content-Disposition': f'attachment; filename="{filename}"'
                }
            )

        # Múltiples archivos — devolver lista de URLs
        return jsonify({
            'multiple': True,
            'count': len(download_urls),
            'urls': download_urls
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
