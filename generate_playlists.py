import uuid
import requests
import gzip
import json
import os
import logging
import re
from io import BytesIO

# --- Configuration ---
OUTPUT_DIR = "playlists"
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
REQUEST_TIMEOUT = 30 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Functions ---
def fetch_url(url, is_json=True, is_gzipped=False):
    headers = {'User-Agent': USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        content = response.content
        if is_gzipped:
            with gzip.GzipFile(fileobj=BytesIO(content), mode='rb') as f:
                content = f.read()
        decoded = content.decode('utf-8')
        return json.loads(decoded) if is_json else decoded
    except Exception as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

def write_m3u_file(filename, content):
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return content

def slugify(text):
    """Fallback to create a clean slug if the official one is missing."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

def format_extinf(ch_id, name, logo, group, chno=""):
    return (f'#EXTINF:-1 tvg-id="{ch_id}" tvg-chno="{chno}" '
            f'tvg-logo="{logo}" group-title="{group}",{name}\n')

# --- Service Generation ---

def generate_pluto_m3u(region='us'):
    URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/PlutoTV/.channels.json.gz'
    data = fetch_url(URL, is_json=True, is_gzipped=True)
    if not data: return ""

    epg = f"https://github.com/matthuisman/i.mjh.nz/raw/master/PlutoTV/{region}.xml.gz"
    output = [f'#EXTM3U url-tvg="{epg}"\n']
    
    channels = data['regions'].get(region, {}).get('channels', {})
    for ch_id, ch_info in channels.items():
        # Step 1: Get the slug or make one from the name
        slug = ch_info.get('slug')
        if not slug or len(slug) > 35: 
            slug = slugify(ch_info['name'])
        
        # Step 2: Ensure .m3u8 is present before the session ID
        sid = str(uuid.uuid4())
        # The structure is strictly: BASE_URL + SLUG + .m3u8 + ?PARAMS
        stream_url = f"https://jmp2.uk/pluto-{slug}.m3u8?sid={sid}"
        
        extinf = format_extinf(ch_id, ch_info['name'], ch_info['logo'], ch_info.get('group', 'PlutoTV'), ch_info.get('chno', ''))
        output.append(extinf + stream_url + '\n')

    content = "".join(output)
    write_m3u_file(f"pluto_{region}.m3u", content)
    return content

def generate_plex_m3u():
    URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/Plex/.channels.json.gz'
    data = fetch_url(URL, is_json=True, is_gzipped=True)
    if not data: return ""
    output = ['#EXTM3U\n']
    for ch_id, ch_info in data.get('channels', {}).items():
        # Plex streams also forced to .m3u8
        stream_url = f"https://jmp2.uk/plex-{ch_id}.m3u8"
        output.append(format_extinf(ch_id, ch_info['name'], ch_info['logo'], "Plex") + stream_url + '\n')
    content = "".join(output)
    write_m3u_file("plex_all.m3u", content)
    return content

def generate_roku_m3u():
    URL = 'https://i.mjh.nz/Roku/.channels.json'
    data = fetch_url(URL, is_json=True)
    if not data: return ""
    output = ['#EXTM3U\n']
    for ch_id, ch_info in data.get('channels', {}).items():
        # Roku streams also forced to .m3u8
        stream_url = f"https://jmp2.uk/rok-{ch_id}.m3u8"
        output.append(format_extinf(ch_id, ch_info['name'], ch_info['logo'], "Roku") + stream_url + '\n')
    content = "".join(output)
    write_m3u_file("roku_all.m3u", content)
    return content

# --- Main Execution ---
if __name__ == "__main__":
    logging.info("Building full playlists with enforced .m3u8 extensions...")
    
    # Generate individual lists
    pluto_content = generate_pluto_m3u('us')
    plex_content = generate_plex_m3u()
    roku_content = generate_roku_m3u()
    
    # Merge into one Master File for VLC
    master_header = "#EXTM3U\n"
    master_body = (
        pluto_content.replace("#EXTM3U\n", "") + 
        plex_content.replace("#EXTM3U\n", "") + 
        roku_content.replace("#EXTM3U\n", "")
    )
    
    write_m3u_file("master_playlist.m3u", master_header + master_body)
    logging.info("Success! 'master_playlist.m3u' is ready in the 'playlists' folder.")
