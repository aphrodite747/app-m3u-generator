import requests
import gzip
import json
import os
import logging
import uuid
import time
from io import BytesIO

# --- Configuration ---
OUTPUT_DIR = "playlists"
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
REQUEST_TIMEOUT = 30 

# IMPORTANT: Replace these with your actual GitHub username and repository name
GITHUB_USERNAME = "BuddyChewChew"
GITHUB_REPO = "app-m3u-generator"
# This is the single link your IPTV player will use
LOCAL_EPG_URL = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{GITHUB_REPO}/main/merged_epg.xml.gz"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Functions ---
def fetch_url(url, is_json=True, is_gzipped=False, headers=None, stream=False, retries=3):
    logging.info(f"Fetching URL: {url}")
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, stream=stream)
            if response.status_code == 429:
                wait_time = (i + 1) * 10
                time.sleep(wait_time)
                continue
            response.raise_for_status()
            if stream: return response
            content = response.content
            if is_gzipped:
                try:
                    with gzip.GzipFile(fileobj=BytesIO(content), mode='rb') as f:
                        content = f.read()
                    content = content.decode('utf-8')
                except: content = content.decode('utf-8')
            else: content = content.decode('utf-8')
            return json.loads(content) if is_json else content
        except Exception as e:
            if i < retries - 1: time.sleep(2)
    return None

def write_m3u_file(filename, content):
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    logging.info(f"Wrote playlist to {filepath}")

def format_extinf(channel_id, tvg_id, tvg_chno, tvg_name, tvg_logo, group_title, display_name):
    chno_str = str(tvg_chno) if tvg_chno and str(tvg_chno).isdigit() else ""
    return (f'#EXTINF:-1 channel-id="{channel_id}" tvg-id="{tvg_id}" tvg-chno="{chno_str}" '
            f'tvg-name="{tvg_name.replace(chr(34), chr(39))}" tvg-logo="{tvg_logo}" '
            f'group-title="{group_title.replace(chr(34), chr(39))}",{display_name.replace(",", "")}\n')

# --- Service Functions ---

def generate_pluto_m3u(regions=['us']):
    PLUTO_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/PlutoTV/.channels.json.gz'
    STREAM_URL_TEMPLATE = 'https://service-stitcher.clusters.pluto.tv/stitch/hls/channel/{id}/master.m3u8?advertisingId=&appName=web&appVersion=9.1.2&deviceDNT=0&deviceId={dev_id}&deviceMake=Chrome&deviceModel=web&deviceType=web&deviceVersion=126.0.0&sid={sid}&userId=&serverSideAds=true'
    data = fetch_url(PLUTO_URL, is_json=True, is_gzipped=True)
    if not data: return
    for region in regions:
        epg = f'https://github.com/matthuisman/i.mjh.nz/raw/master/PlutoTV/{region}.xml.gz'
        output = [f'#EXTM3U url-tvg="{epg}"\n']
        region_data = data.get('regions', {}).get(region, {})
        for cid, ch in region_data.get('channels', {}).items():
            extinf = format_extinf(cid, cid, ch.get('chno'), ch.get('name'), ch.get('logo'), ch.get('group', 'PlutoTV'), ch.get('name'))
            stream = STREAM_URL_TEMPLATE.format(id=cid, dev_id=str(uuid.uuid4()), sid=str(uuid.uuid4()))
            output.extend([extinf, stream + '\n'])
        write_m3u_file(f"plutotv_{region}.m3u", "".join(output))

def generate_plex_m3u(regions=['us']):
    PLEX_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/Plex/.channels.json.gz'
    data = fetch_url(PLEX_URL, is_json=True, is_gzipped=True, headers={'User-Agent': USER_AGENT})
    if not data: return
    for region in regions:
        epg = f'https://github.com/matthuisman/i.mjh.nz/raw/master/Plex/{region}.xml.gz'
        output = [f'#EXTM3U url-tvg="{epg}"\n']
        for cid, ch in data.get('channels', {}).items():
            if region in ch.get('regions', []):
                extinf = format_extinf(cid, cid, ch.get('chno'), ch.get('name'), ch.get('logo'), "Plex", ch.get('name'))
                output.extend([extinf, f"https://jmp2.uk/plex-{cid}.m3u8\n"])
        write_m3u_file(f"plex_{region}.m3u", "".join(output))

def generate_samsungtvplus_m3u(regions=['us']):
    SAMSUNG_URL = 'https://github
