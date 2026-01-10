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

# IMPORTANT: Replace these with your actual GitHub info
GITHUB_USERNAME = "BuddyChewChew"
GITHUB_REPO = "app-m3u-generator"
LOCAL_EPG_URL = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{GITHUB_REPO}/main/merged_epg.xml.gz"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Functions ---
def fetch_url(url, is_json=True, is_gzipped=False, headers=None, stream=False, retries=3):
    logging.info(f"Fetching: {url}")
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, stream=stream)
            if response.status_code == 429:
                time.sleep((i + 1) * 5)
                continue
            response.raise_for_status()
            if stream: return response
            content = response.content
            if is_gzipped:
                try:
                    with gzip.GzipFile(fileobj=BytesIO(content), mode='rb') as f:
                        content = f.read().decode('utf-8')
                except: content = content.decode('utf-8')
            else:
                content = content.decode('utf-8')
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
    logging.info(f"Saved: {filepath}")

def format_extinf(channel_id, tvg_id, tvg_chno, tvg_name, tvg_logo, group_title, display_name):
    chno_str = str(tvg_chno) if tvg_chno and str(tvg_chno).isdigit() else ""
    return (f'#EXTINF:-1 channel-id="{channel_id}" tvg-id="{tvg_id}" tvg-chno="{chno_str}" '
            f'tvg-name="{tvg_name.replace(chr(34), chr(39))}" tvg-logo="{tvg_logo}" '
            f'group-title="{group_title.replace(chr(34), chr(39))}",{display_name.replace(",", "")}\n')

# --- Service Functions ---

def generate_pluto_m3u(regions=['us']):
    url = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/PlutoTV/.channels.json.gz'
    template = 'https://service-stitcher.clusters.pluto.tv/stitch/hls/channel/{id}/master.m3u8?advertisingId=&appName=web&appVersion=9.1.2&deviceDNT=0&deviceId={dev_id}&deviceMake=Chrome&deviceModel=web&deviceType=web&deviceVersion=126.0.0&sid={sid}&userId=&serverSideAds=true'
    data = fetch_url(url, is_json=True, is_gzipped=True)
    if not data: return
    for reg in regions:
        output = [f'#EXTM3U\n']
        reg_data = data.get('regions', {}).get(reg, {})
        for cid, ch in reg_data.get('channels', {}).items():
            extinf = format_extinf(cid, cid, ch.get('chno'), ch.get('name'), ch.get('logo'), 'PlutoTV', ch.get('name'))
            stream = template.format(id=cid, dev_id=str(uuid.uuid4()), sid=str(uuid.uuid4()))
            output.extend([extinf, stream + '\n'])
        write_m3u_file(f"plutotv_{reg}.m3u", "".join(output))

def generate_plex_m3u(regions=['us']):
    url = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/Plex/.channels.json.gz'
    data = fetch_url(url, is_json=True, is_gzipped=True, headers={'User-Agent': USER_AGENT})
    if not data: return
    for reg in regions:
        output = [f'#EXTM3U\n']
        for cid, ch in data.get('channels', {}).items():
            if reg in ch.get('regions', []):
                extinf = format_extinf(cid, cid, ch.get('chno'), ch.get('name'), ch.get('logo'), "Plex", ch.get('name'))
                output.extend([extinf, f"https://jmp2.uk/plex-{cid}.m3u8\n"])
        write_m3u_file(f"plex_{reg}.m3u", "".join(output))

def generate_samsungtvplus_m3u(regions=['us']):
    url = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/SamsungTVPlus/.channels.json.gz'
    data = fetch_url(url, is_json=True, is_gzipped=True)
    if not data: return
    for reg in regions:
        output = [f'#EXTM3U\n']
        reg_data = data.get('regions', {}).get(reg, {})
        for cid, ch in reg_data.get('channels', {}).items():
            extinf = format_extinf(cid, cid, ch.get('chno'), ch.get('name'), ch.get('logo'), 'Samsung TV', ch.get('name'))
            output.extend([extinf, f"https://jmp2.uk/stvp-{cid}.m3u8\n"])
        write_m3u_file(f"samsungtvplus_{reg}.m3u", "".join(output))

def generate_stirr_m3u():
    url = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/Stirr/.channels.json.gz'
    data = fetch_url(url, is_json=True, is_gzipped=True)
    if not data: return
    output = [f'#EXTM3U\n']
    for cid, ch in data.get('channels', {}).items():
        extinf = format_extinf(cid, cid, ch.get('chno'), ch.get('name'), ch.get('logo'), "Stirr", ch.get('name'))
        output.extend([extinf, f"https://jmp2.uk/str-{cid}.m3u8\n"])
    write_m3u_file("stirr_all.m3u", "".join(output))

def generate_tubi_m3u():
    url = 'https://raw.githubusercontent.com/BuddyChewChew/tubi-scraper/refs/heads/main/tubi_playlist.m3u'
    content = fetch_url(url, is_json=False)
    if content: write_m3u_file("tubi_all.m3u", content.strip() + "\n")

def generate_roku_m3u():
    url = 'https://i.mjh.nz/Roku/.channels.json'
    data = fetch_url(url, is_json=True)
    if not data: return
    output = [f'#EXTM3U\n']
    for cid, ch in data.get('channels', {}).items():
        extinf = format_extinf(cid, cid, ch.get('chno'), ch.get('name'), ch.get('logo'), "Roku", ch.get('name'))
        output.extend([extinf, f"https://jmp2.uk/rok-{cid}.m3u8\n"])
    write_m3u_file("roku_all.m3u", "".join(output))

# --- EPG & Master ---

def merge_epgs():
    logging.info("--- Merging EPGs ---")
    sources = [
        "https://github.com/matthuisman/i.mjh.nz/raw/master/PlutoTV/us.xml.gz",
        "https://github.com/matthuisman/i.mjh.nz/raw/master/Plex/us.xml.gz",
        "https://github.com/matthuisman/i.mjh.nz/raw/master/SamsungTVPlus/us.xml.gz",
        "https://github.com/matthuisman/i.mjh.nz/raw/master/Stirr/all.xml.gz",
        "https://github.com/matthuisman/i.mjh.nz/raw/master/Roku/all.xml.gz"
    ]
    combined = '<?xml version="1.0" encoding="UTF-8"?><tv>'
    for s in sources:
        xml = fetch_url(s, is_json=False, is_gzipped=True)
        if xml and '<tv' in xml:
            body = xml.split('>', 1)[1].rsplit('</tv>', 1)[0]
            combined += body
    combined += '</tv>'
    with gzip.open("merged_epg.xml.gz", "wb") as f:
        f.write(combined.encode('utf-8'))

def generate_master_playlist():
    logging.info("--- Creating Master ---")
    master = f'#EXTM3U url-tvg="{LOCAL_EPG_URL}"\n\n'
    files = ["plutotv_us.m3u", "plex_us.m3u", "samsungtvplus_us.m3u", "stirr_all.m3u", "tubi_all.m3u", "roku_all.m3u"]
    for name in files:
        path = os.path.join(OUTPUT_DIR, name)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) > 0:
                    master += "".join(lines[1:]) + "\n"
    write_m3u_file("master.m3u", master)

if __name__ == "__main__":
    generate_pluto_m3u()
    generate_plex_m3u()
    generate_samsungtvplus_m3u()
    generate_stirr_m3u()
    generate_tubi_m3u()
    generate_roku_m3u()
    merge_epgs()
    generate_master_playlist()
    logging.info("Finished.")
