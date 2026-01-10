import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import gzip
import json
import os
import logging
import uuid
import shutil
from io import BytesIO

# --- Configuration ---
OUTPUT_DIR = "playlists"
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
REQUEST_TIMEOUT = 30 

REGION_MAP = {
    'us': 'United States', 'gb': 'United Kingdom', 'ca': 'Canada',
    'de': 'Germany', 'at': 'Austria', 'ch': 'Switzerland',
    'es': 'Spain', 'fr': 'France', 'it': 'Italy', 'br': 'Brazil',
    'mx': 'Mexico', 'ar': 'Argentina', 'cl': 'Chile', 'co': 'Colombia',
    'pe': 'Peru', 'se': 'Sweden', 'no': 'Norway', 'dk': 'Denmark',
    'in': 'India', 'jp': 'Japan', 'kr': 'South Korea', 'au': 'Australia'
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

session = requests.Session()
retries = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))
session.headers.update({'User-Agent': USER_AGENT})

def cleanup_output_dir():
    if os.path.exists(OUTPUT_DIR):
        for filename in os.listdir(OUTPUT_DIR):
            file_path = os.path.join(OUTPUT_DIR, filename)
            try:
                if os.path.isfile(file_path): os.unlink(file_path)
                elif os.path.isdir(file_path): shutil.rmtree(file_path)
            except Exception as e: logging.error(f"Cleanup error: {e}")
    else: os.makedirs(OUTPUT_DIR)

def fetch_url(url, is_json=True, is_gzipped=False):
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        content = response.content
        if is_gzipped:
            with gzip.GzipFile(fileobj=BytesIO(content), mode='rb') as f:
                content = f.read()
        decoded = content.decode('utf-8', errors='ignore')
        return json.loads(decoded) if is_json else decoded
    except Exception as e:
        logging.error(f"Fetch error {url}: {e}")
    return None

def write_m3u_file(filename, content):
    with open(os.path.join(OUTPUT_DIR, filename), 'w', encoding='utf-8') as f:
        f.write(content)
    logging.info(f"Wrote {filename}")

# --- Fixed Pluto Generator ---
def generate_pluto_m3u():
    data = fetch_url('https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/PlutoTV/.channels.json.gz', is_json=True, is_gzipped=True)
    if not data or 'regions' not in data: return
    
    for region in list(data['regions'].keys()) + ['all']:
        is_all = region == 'all'
        epg_url = f'https://github.com/matthuisman/i.mjh.nz/raw/master/PlutoTV/{region}.xml.gz'
        output_lines = [f'#EXTM3U url-tvg="{epg_url}"\n']
        channels = {}
        
        if is_all:
            for r_code, r_data in data['regions'].items():
                # Full Name Fix
                full_name = REGION_MAP.get(r_code.lower(), r_code.upper())
                for c_id, c_info in r_data.get('channels', {}).items():
                    channels[f"{c_id}-{r_code}"] = {**c_info, 'original_id': c_id, 'group': f"Pluto TV - {full_name}"}
        else:
            region_data = data['regions'].get(region, {}).get('channels', {})
            for c_id, c_info in region_data.items():
                channels[c_id] = {**c_info, 'original_id': c_id, 'group': c_info.get('group', 'Pluto TV')}
        
        if channels:
            for c_id, ch in sorted(channels.items(), key=lambda x: x[1].get('name', '')):
                # Restored original simple #EXTINF line
                line = f'#EXTINF:-1 tvg-id="{ch["original_id"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["name"]}\n'
                # Restored original working Pluto URL format
                url = f'https://service-stitcher.clusters.pluto.tv/stitch/hls/channel/{ch["original_id"]}/master.m3u8?advertisingId=&appName=web&deviceMake=Chrome&deviceType=web&sid={uuid.uuid4()}&serverSideAds=true\n'
                output_lines.extend([line, url])
            write_m3u_file(f"plutotv_{region}.m3u", "".join(output_lines))

# --- Standardized others for consistency ---
def generate_plex_m3u():
    data = fetch_url('https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/Plex/.channels.json.gz', is_json=True, is_gzipped=True)
    if not data or 'channels' not in data: return
    found_regions = set()
    for ch in data['channels'].values(): found_regions.update(ch.get('regions', []))
    for region in list(found_regions) + ['all']:
        is_all = region == 'all'
        output_lines = [f'#EXTM3U url-tvg="https://github.com/matthuisman/i.mjh.nz/raw/master/Plex/{region}.xml.gz"\n']
        count = 0
        for c_id, ch in data['channels'].items():
            if is_all or region in ch.get('regions', []):
                line = f'#EXTINF:-1 tvg-id="{c_id}" tvg-logo="{ch["logo"]}" group-title="Plex TV",{ch["name"]}\n'
                output_lines.extend([line, f"https://jmp2.uk/plex-{c_id}.m3u8\n"])
                count += 1
        if count > 0: write_m3u_file(f"plex_{region}.m3u", "".join(output_lines))

def generate_samsungtvplus_m3u():
    data = fetch_url('https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/SamsungTVPlus/.channels.json.gz', is_json=True, is_gzipped=True)
    if not data or 'regions' not in data: return
    for region in list(data['regions'].keys()) + ['all']:
        is_all = region == 'all'
        output_lines = [f'#EXTM3U url-tvg="https://github.com/matthuisman/i.mjh.nz/raw/master/SamsungTVPlus/{region}.xml.gz"\n']
        target = {}
        if is_all:
            for r_code, r_info in data['regions'].items():
                full_name = REGION_MAP.get(r_code.lower(), r_code.upper())
                for c_id, c_info in r_info.get('channels', {}).items(): 
                    target[f"{c_id}-{r_code}"] = {**c_info, 'original_id': c_id, 'group': f"Samsung TV Plus - {full_name}"}
        else:
            region_dict = data['regions'].get(region, {}).get('channels', {})
            for c_id, c_info in region_dict.items():
                target[c_id] = {**c_info, 'original_id': c_id, 'group': c_info.get('group', 'Samsung TV Plus')}
        if target:
            for c_id, ch in target.items():
                line = f'#EXTINF:-1 tvg-id="{ch["original_id"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["name"]}\n'
                output_lines.extend([line, f"https://jmp2.uk/sam-{ch['original_id']}.m3u8\n"])
            write_m3u_file(f"samsungtvplus_{region}.m3u", "".join(output_lines))

def generate_stirr_m3u():
    data = fetch_url('https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/Stirr/.channels.json.gz', is_json=True, is_gzipped=True)
    if not data: return
    output_lines = ['#EXTM3U url-tvg="https://github.com/matthuisman/i.mjh.nz/raw/master/Stirr/all.xml.gz"\n']
    for c_id, ch in data['channels'].items():
        line = f'#EXTINF:-1 tvg-id="{c_id}" tvg-logo="{ch["logo"]}" group-title="Stirr",{ch["name"]}\n'
        output_lines.extend([line, f"https://jmp2.uk/str-{c_id}.m3u8\n"])
    if len(output_lines) > 1: write_m3u_file("stirr_all.m3u", "".join(output_lines))

def generate_tubi_m3u():
    content = fetch_url('https://raw.githubusercontent.com/BuddyChewChew/tubi-scraper/refs/heads/main/tubi_playlist.m3u', is_json=False)
    if content: write_m3u_file("tubi_all.m3u", content.strip() + "\n")

def generate_roku_m3u():
    data = fetch_url('https://i.mjh.nz/Roku/.channels.json', is_json=True)
    if not data: return
    output_lines = ['#EXTM3U url-tvg="https://github.com/matthuisman/i.mjh.nz/raw/master/Roku/all.xml.gz"\n']
    for c_id, ch in data['channels'].items():
        line = f'#EXTINF:-1 tvg-id="{c_id}" tvg-logo="{ch["logo"]}" group-title="Roku",{ch["name"]}\n'
        output_lines.extend([line, f"https://jmp2.uk/rok-{c_id}.m3u8\n"])
    if len(output_lines) > 1: write_m3u_file("roku_all.m3u", "".join(output_lines))

if __name__ == "__main__":
    cleanup_output_dir()
    generate_pluto_m3u()
    generate_plex_m3u()
    generate_samsungtvplus_m3u()
    generate_stirr_m3u()
    generate_tubi_m3u()
    generate_roku_m3u()
    logging.info("Complete.")
