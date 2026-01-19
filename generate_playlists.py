import requests
import gzip
import json
import os
import logging
import uuid
import time
import shutil
import random
from io import BytesIO

# --- Configuration ---
OUTPUT_DIR = "playlists"
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
REQUEST_TIMEOUT = 30 
FALLBACK_GENRE = "Uncategorised"

REGION_MAP = {
    'us': 'United States', 'gb': 'United Kingdom', 'ca': 'Canada',
    'de': 'Germany', 'at': 'Austria', 'ch': 'Switzerland',
    'es': 'Spain', 'fr': 'France', 'it': 'Italy', 'br': 'Brazil',
    'mx': 'Mexico', 'ar': 'Argentina', 'cl': 'Chile', 'co': 'Colombia',
    'pe': 'Peru', 'se': 'Sweden', 'no': 'Norway', 'dk': 'Denmark',
    'in': 'India', 'jp': 'Japan', 'kr': 'South Korea', 'au': 'Australia'
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def cleanup_output_dir():
    if os.path.exists(OUTPUT_DIR):
        for filename in os.listdir(OUTPUT_DIR):
            file_path = os.path.join(OUTPUT_DIR, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")
    else:
        os.makedirs(OUTPUT_DIR)

def fetch_url(url, is_json=True, is_gzipped=False, retries=3):
    headers = {'User-Agent': USER_AGENT}
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            content = response.content
            if is_gzipped:
                with gzip.GzipFile(fileobj=BytesIO(content), mode='rb') as f:
                    content = f.read()
            content = content.decode('utf-8')
            return json.loads(content) if is_json else content
        except Exception as e:
            logger.warning(f"Fetch failed: {e}")
            time.sleep(5)
    return None

def format_extinf(channel_id, tvg_id, tvg_chno, tvg_name, tvg_logo, group_title, display_name):
    chno_str = str(tvg_chno) if tvg_chno and str(tvg_chno).isdigit() else ""
    return (f'#EXTINF:-1 channel-id="{channel_id}" tvg-id="{tvg_id}" tvg-chno="{chno_str}" '
            f'tvg-name="{tvg_name}" tvg-logo="{tvg_logo}" '
            f'group-title="{group_title}",{display_name}\n')

# --- Service Generators ---

def generate_pluto_m3u():
    data = fetch_url('https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/PlutoTV/.channels.json.gz', is_json=True, is_gzipped=True)
    if not data or 'regions' not in data: return
    
    for region in list(data['regions'].keys()) + ['all']:
        epg_url = f'https://github.com/matthuisman/i.mjh.nz/raw/master/PlutoTV/{region}.xml.gz'
        output_lines = [f'#EXTM3U url-tvg="{epg_url}"\n']
        processed_channels = []
        
        if region == 'all':
            for r_code, r_data in data['regions'].items():
                for c_id, c_info in r_data.get('channels', {}).items():
                    # FIX: Prioritize 'category' from JSON, fallback to 'Uncategorised'
                    genre = c_info.get('category', FALLBACK_GENRE)
                    processed_channels.append({
                        'id': f"{c_id}-{r_code}", 'original_id': c_id,
                        'name': c_info['name'], 'logo': c_info['logo'],
                        'chno': c_info.get('chno'), 'group': genre
                    })
        else:
            region_data = data['regions'].get(region, {}).get('channels', {})
            for c_id, c_info in region_data.items():
                # FIX: Prioritize 'category' from JSON, fallback to 'Uncategorised'
                genre = c_info.get('category', FALLBACK_GENRE)
                processed_channels.append({
                    'id': c_id, 'original_id': c_id,
                    'name': c_info['name'], 'logo': c_info['logo'],
                    'chno': c_info.get('chno'), 'group': genre
                })
        
        if processed_channels:
            processed_channels.sort(key=lambda x: (x['group'], x['name']))
            for ch in processed_channels:
                extinf = format_extinf(ch['id'], ch['original_id'], ch['chno'], ch['name'], ch['logo'], ch['group'], ch['name'])
                url = f'https://service-stitcher.clusters.pluto.tv/stitch/hls/channel/{ch["original_id"]}/master.m3u8?advertisingId=&appName=web&appVersion=9.1.2&deviceDNT=0&deviceId={uuid.uuid4()}&deviceMake=Chrome&deviceModel=web&deviceType=web&deviceVersion=126.0.0&sid={uuid.uuid4()}&userId=&serverSideAds=true\n'
                output_lines.extend([extinf, url])
            write_m3u_file(f"plutotv_{region}.m3u", "".join(output_lines))

def write_m3u_file(filename, content):
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    cleanup_output_dir()
    generate_pluto_m3u()
    logger.info("Playlist generation complete.")
