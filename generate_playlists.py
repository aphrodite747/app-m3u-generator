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

# IMPORTANT: Update these to match your GitHub details
GITHUB_USERNAME = "YOUR_USERNAME"
GITHUB_REPO = "YOUR_REPO_NAME"
# This is the single link you will provide to your IPTV player
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

def merge_epgs():
    """Downloads all EPG sources and merges them into one compressed file."""
    logging.info("--- Merging EPG Sources ---")
    epg_sources = [
        "https://github.com/matthuisman/i.mjh.nz/raw/master/PlutoTV/us.xml.gz",
        "https://github.com/matthuisman/i.mjh.nz/raw/master/Plex/us.xml.gz",
        "https://github.com/matthuisman/i.mjh.nz/raw/master/SamsungTVPlus/us.xml.gz",
        "https://github.com/matthuisman/i.mjh.nz/raw/master/Stirr/all.xml.gz",
        "https://github.com/matthuisman/i.mjh.nz/raw/master/Roku/all.xml.gz"
    ]
    
    combined_xml = '<?xml version="1.0" encoding="UTF-8"?><tv>'
    
    for url in epg_sources:
        try:
            # Reusing your fetch_url to get raw content
            content = fetch_url(url, is_json=False, is_gzipped=True)
            if content and '<tv' in content:
                # Extract inner content between <tv> tags
                body = content.split('>', 1)[1].rsplit('</tv>', 1)[0]
                combined_xml += body
        except Exception as e:
            logging.error(f"Failed to merge EPG from {url}: {e}")
            
    combined_xml += '</tv>'
    
    # Save as compressed .gz file in the root directory
    with gzip.open("merged_epg.xml.gz", "wb") as f:
        f.write(combined_xml.encode('utf-8'))
    logging.info("Merged EPG saved to merged_epg.xml.gz")

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

# --- Service Functions (Pluto, Plex, Samsung, etc. remain the same) ---
# ... [Keep your generate_pluto_m3u, generate_plex_m3u, etc. here] ...

# --- Updated Master Function ---
def generate_master_playlist():
    """Combines individual service files into one master playlist using the LOCAL merged EPG."""
    logging.info("--- Generating Master All-in-One Playlist ---")
    
    # Start the master file with the SINGLE merged EPG link
    master_content = f'#EXTM3U url-tvg="{LOCAL_EPG_URL}"\n\n'
    
    files_to_merge = [
        "plutotv_us.m3u", 
        "plex_us.m3u", 
        "samsungtvplus_us.m3u", 
        "stirr_all.m3u", 
        "tubi_all.m3u", 
        "roku_all.m3u"
    ]
    
    for filename in files_to_merge:
        filepath = os.path.join(OUTPUT_DIR, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) > 0:
                    master_content += "".join(lines[1:])
                    master_content += "\n"
    
    write_m3u_file("master.m3u", master_content)

# --- Updated Execution ---
if __name__ == "__main__":
    # 1. Generate the individual playlists first
    generate_pluto_m3u(regions=['us'])
    generate_plex_m3u(regions=['us'])
    generate_samsungtvplus_m3u(regions=['us'])
    generate_stirr_m3u()
    generate_tubi_m3u()
    generate_roku_m3u()
    
    # 2. Merge the EPGs into one file
    merge_epgs()
    
    # 3. Create the master playlist pointing to that merged file
    generate_master_playlist()
    
    logging.info("All tasks completed.")
