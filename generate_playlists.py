import requests
import gzip
import json
import os
import logging
import uuid
import time
import shutil
from io import BytesIO

# --- Configuration ---
OUTPUT_DIR = "playlists"
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
REQUEST_TIMEOUT = 30 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Functions ---

def cleanup_output_dir():
    """Removes all files in the output directory to ensure a fresh start."""
    if os.path.exists(OUTPUT_DIR):
        logging.info(f"Cleaning up old playlists in {OUTPUT_DIR}...")
        for filename in os.listdir(OUTPUT_DIR):
            file_path = os.path.join(OUTPUT_DIR, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                logging.error(f"Failed to delete {file_path}. Reason: {e}")
    else:
        os.makedirs(OUTPUT_DIR)

def fetch_url(url, is_json=True, is_gzipped=False, headers=None, stream=False, retries=3):
    logging.info(f"Fetching URL: {url}")
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, stream=stream)
            if response.status_code == 429:
                time.sleep((i + 1) * 10)
                continue
            response.raise_for_status()
            content = response.content
            if is_gzipped:
                try:
                    with gzip.GzipFile(fileobj=BytesIO(content), mode='rb') as f:
                        content = f.read()
                    content = content.decode('utf-8')
                except:
                    content = content.decode('utf-8')
            else:
                content = content.decode('utf-8')
            return json.loads(content) if is_json else content
        except Exception as e:
            if i < retries - 1: time.sleep(2)
    return None

def write_m3u_file(filename, content):
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    logging.info(f"Successfully wrote {filename}")

def format_extinf(channel_id, tvg_id, tvg_chno, tvg_name, tvg_logo, group_title, display_name):
    chno_str = str(tvg_chno) if tvg_chno and str(tvg_chno).isdigit() else ""
    return (f'#EXTINF:-1 channel-id="{channel_id}" tvg-id="{tvg_id}" tvg-chno="{chno_str}" '
            f'tvg-name="{tvg_name.replace(chr(34), chr(39))}" tvg-logo="{tvg_logo}" '
            f'group-title="{group_title.replace(chr(34), chr(39))}",{display_name.replace(",", "")}\n')

# --- Service Functions ---

def generate_pluto_m3u():
    PLUTO_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/PlutoTV/.channels.json.gz'
    STREAM_URL_TEMPLATE = 'https://service-stitcher.clusters.pluto.tv/stitch/hls/channel/{id}/master.m3u8?advertisingId=&appName=web&appVersion=9.1.2&deviceDNT=0&deviceId={dev_id}&deviceMake=Chrome&deviceModel=web&deviceType=web&deviceVersion=126.0.0&sid={sid}&userId=&serverSideAds=true'
    
    data = fetch_url(PLUTO_URL, is_json=True, is_gzipped=True)
    if not data or 'regions' not in data: return

    available_regions = list(data['regions'].keys()) + ['all']
    
    for region in available_regions:
        is_all = region == 'all'
        epg_url = f'https://github.com/matthuisman/i.mjh.nz/raw/master/PlutoTV/{region}.xml.gz'
        output_lines = [f'#EXTM3U url-tvg="{epg_url}"\n']
        
        channels = {}
        if is_all:
            for r_code, r_data in data['regions'].items():
                for c_id, c_info in r_data.get('channels', {}).items():
                    channels[f"{c_id}-{r_code}"] = {**c_info, 'original_id': c_id, 'group': r_code.upper()}
        else:
            region_data = data['regions'].get(region, {}).get('channels', {})
            for c_id, c_info in region_data.items():
                channels[c_id] = {**c_info, 'original_id': c_id, 'group': c_info.get('group', 'Pluto')}

        if not channels: continue

        for c_id, ch in sorted(channels.items(), key=lambda x: x[1].get('name', '')):
            extinf = format_extinf(c_id, ch['original_id'], ch.get('chno'), ch['name'], ch['logo'], ch['group'], ch['name'])
            url = STREAM_URL_TEMPLATE.format(id=ch['original_id'], dev_id=str(uuid.uuid4()), sid=str(uuid.uuid4()))
            output_lines.extend([extinf, url + '\n'])
        
        write_m3u_file(f"plutotv_{region}.m3u", "".join(output_lines))

def generate_plex_m3u():
    PLEX_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/Plex/.channels.json.gz'
    data = fetch_url(PLEX_URL, is_json=True, is_gzipped=True, headers={'User-Agent': USER_AGENT})
    if not data or 'channels' not in data: return

    found_regions = set()
    for ch in data['channels'].values():
        found_regions.update(ch.get('regions', []))
    available_regions = list(found_regions) + ['all']

    for region in available_regions:
        is_all = region == 'all'
        epg_url = f'https://github.com/matthuisman/i.mjh.nz/raw/master/Plex/{region}.xml.gz'
        output_lines = [f'#EXTM3U url-tvg="{epg_url}"\n']
        
        count = 0
        for c_id, ch in data['channels'].items():
            if is_all or region in ch.get('regions', []):
                extinf = format_extinf(c_id, c_id, ch.get('chno'), ch['name'], ch['logo'], "Plex", ch['name'])
                url = f"https://jmp2.uk/plex-{c_id}.m3u8\n"
                output_lines.extend([extinf, url])
                count += 1
        
        if count > 0:
            write_m3u_file(f"plex_{region}.m3u", "".join(output_lines))

def generate_samsungtvplus_m3u():
    SAMSUNG_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/SamsungTVPlus/.channels.json.gz'
    data = fetch_url(SAMSUNG_URL, is_json=True, is_gzipped=True)
    if not data or 'regions' not in data: return

    available_regions = list(data['regions'].keys()) + ['all']

    for region in available_regions:
        is_all = region == 'all'
        epg_url = f'https://github.com/matthuisman/i.mjh.nz/raw/master/SamsungTVPlus/{region}.xml.gz'
        output_lines = [f'#EXTM3U url-tvg="{epg_url}"\n']
        
        target_data = {}
        if is_all:
            for r_code, r_info in data['regions'].items():
                for c_id, c_info in r_info.get('channels', {}).items():
                    target_data[f"{c_id}-{r_code}"] = {**c_info, 'original_id': c_id}
        else:
            region_data = data['regions'].get(region, {}).get('channels', {})
            for c_id, c_info in region_data.items(): 
                target_data[c_id] = {**c_info, 'original_id': c_id}

        if not target_data: continue

        for c_id, ch in target_data.items():
            extinf = format_extinf(c_id, ch['original_id'], ch.get('chno'), ch['name'], ch['logo'], ch.get('group', 'Samsung'), ch['name'])
            url = f"https://jmp2.uk/sam-{ch['original_id']}.m3u8\n"
            output_lines.extend([extinf, url])
            
        write_m3u_file(f"samsungtvplus_{region}.m3u", "".join(output_lines))

def generate_stirr_m3u():
    STIRR_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/Stirr/.channels.json.gz'
    data = fetch_url(STIRR_URL, is_json=True, is_gzipped=True)
    if not data or 'channels' not in data: return
    output_lines = ['#EXTM3U url-tvg="https://github.com/matthuisman/i.mjh.nz/raw/master/Stirr/all.xml.gz"\n']
    for c_id, ch in data['channels'].items():
        extinf = format_extinf(c_id, c_id, ch.get('chno'), ch['name'], ch['logo'], ", ".join(ch.get('groups', ['Stirr'])), ch['name'])
        output_lines.extend([extinf, f"https://jmp2.uk/str-{c_id}.m3u8\n"])
    write_m3u_file("stirr_all.m3u", "".join(output_lines))

def generate_tubi_m3u():
    TUBI_URL = 'https://raw.githubusercontent.com/BuddyChewChew/tubi-scraper/refs/heads/main/tubi_playlist.m3u'
    content = fetch_url(TUBI_URL, is_json=False)
    if content: write_m3u_file("tubi_all.m3u", content.strip() + "\n")

def generate_roku_m3u():
    ROKU_URL = 'https://i.mjh.nz/Roku/.channels.json'
    data = fetch_url(ROKU_URL, is_json=True, is_gzipped=False)
    if not data or 'channels' not in data: return
    output_lines = ['#EXTM3U url-tvg="https://github.com/matthuisman/i.mjh.nz/raw/master/Roku/all.xml.gz"\n']
    for c_id, ch in data['channels'].items():
        group = ch.get('groups', ['Roku'])[0] if ch.get('groups') else 'Roku'
        extinf = format_extinf(c_id, c_id, ch.get('chno'), ch['name'], ch['logo'], group, ch['name'])
        output_lines.extend([extinf, f"https://jmp2.uk/rok-{c_id}.m3u8\n"])
    write_m3u_file("roku_all.m3u", "".join(output_lines))

# --- Main Execution ---
if __name__ == "__main__":
    # 1. Clean up old files first
    cleanup_output_dir()
    
    # 2. Run generators
    logging.info("Starting fresh playlist generation...")
    generate_pluto_m3u()
    generate_plex_m3u()
    generate_samsungtvplus_m3u()
    generate_stirr_m3u()
    generate_tubi_m3u()
    generate_roku_m3u()
    
    logging.info("Process completed successfully.")
