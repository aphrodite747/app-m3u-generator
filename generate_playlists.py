import uuid
import requests
import gzip
import json
import os
import logging
from io import BytesIO

# --- Configuration ---
OUTPUT_DIR = "playlists"
# Modern User-Agent to prevent bot-detection blocks
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
REQUEST_TIMEOUT = 30 

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Functions ---
def fetch_url(url, is_json=True, is_gzipped=False, headers=None, stream=False):
    """Fetches data with headers that mimic a browser to avoid 403 Forbidden errors."""
    logging.info(f"Fetching URL: {url}")
    
    session_headers = {
        'User-Agent': USER_AGENT,
        'Accept': '*/*',
        'Origin': 'https://pluto.tv',
        'Referer': 'https://pluto.tv/'
    }
    if headers:
        session_headers.update(headers)

    try:
        response = requests.get(url, headers=session_headers, timeout=REQUEST_TIMEOUT, stream=stream)
        response.raise_for_status()

        if stream:
            return response

        content = response.content
        if is_gzipped:
            try:
                with gzip.GzipFile(fileobj=BytesIO(content), mode='rb') as f:
                    content = f.read()
                content = content.decode('utf-8')
            except Exception:
                content = content.decode('utf-8')
        else:
            content = content.decode('utf-8')

        return json.loads(content) if is_json else content

    except Exception as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

def write_m3u_file(filename, content):
    """Writes the generated M3U content to the output directory."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    filepath = os.path.join(OUTPUT_DIR, filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"Successfully wrote playlist to {filepath}")
    except IOError as e:
        logging.error(f"Error writing file {filepath}: {e}")

def format_extinf(channel_id, tvg_id, tvg_chno, tvg_name, tvg_logo, group_title, display_name):
    """Standardizes the #EXTINF line for compatibility with VLC and Tivimate."""
    chno_str = str(tvg_chno) if tvg_chno is not None and str(tvg_chno).isdigit() else ""
    sanitized_tvg_name = tvg_name.replace('"', "'")
    sanitized_group_title = group_title.replace('"', "'")
    sanitized_display_name = display_name.replace(',', '')

    return (f'#EXTINF:-1 '
            f'channel-id="{channel_id}" '
            f'tvg-id="{tvg_id}" '
            f'tvg-chno="{chno_str}" '
            f'tvg-name="{sanitized_tvg_name}" '
            f'tvg-logo="{tvg_logo}" '
            f'group-title="{sanitized_group_title}",'
            f'{sanitized_display_name}\n')

# --- Service Functions ---

def generate_pluto_m3u(regions=['us', 'all']):
    """Generates PlutoTV M3U with fixed .m3u8 extensions and slug-based routing."""
    PLUTO_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/PlutoTV/.channels.json.gz'
    # Base template includes .m3u8 for player compatibility
    STREAM_TEMPLATE = 'https://jmp2.uk/pluto-{slug}.m3u8'
    EPG_TEMPLATE = 'https://github.com/matthuisman/i.mjh.nz/raw/master/PlutoTV/{region}.xml.gz'

    data = fetch_url(PLUTO_URL, is_json=True, is_gzipped=True)
    if not data: return

    for region in regions:
        is_all = region.lower() == 'all'
        epg_url = EPG_TEMPLATE.format(region="all" if is_all else region)
        output = [f'#EXTM3U url-tvg="{epg_url}"\n']
        
        target_regions = data['regions'].keys() if is_all else [region]
        
        for reg_key in target_regions:
            reg_data = data['regions'].get(reg_key)
            if not reg_data: continue
            
            for ch_id, ch_info in reg_data.get('channels', {}).items():
                # Fix: Use Slug to ensure bridge compatibility
                slug = ch_info.get('slug', ch_id)
                unique_id = f"{ch_id}-{reg_key}" if is_all else ch_id
                
                # Fix: Ensure .m3u8 is present BEFORE query parameters
                sid = str(uuid.uuid4())
                stream_url = f"{STREAM_TEMPLATE.format(slug=slug)}?sid={sid}"
                
                group = reg_data.get('name', reg_key.upper()) if is_all else ch_info.get('group', 'PlutoTV')
                extinf = format_extinf(unique_id, ch_id, ch_info.get('chno'), 
                                      ch_info['name'], ch_info['logo'], group, ch_info['name'])
                output.append(extinf + stream_url + '\n')

        write_m3u_file(f"plutotv_{region}.m3u", "".join(output))

def generate_plex_m3u(regions=['us', 'all']):
    PLEX_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/Plex/.channels.json.gz'
    data = fetch_url(PLEX_URL, is_json=True, is_gzipped=True)
    if not data: return

    for region in regions:
        is_all = region.lower() == 'all'
        epg_url = f"https://github.com/matthuisman/i.mjh.nz/raw/master/Plex/{region}.xml.gz"
        output = [f'#EXTM3U url-tvg="{epg_url}"\n']
        
        for ch_id, ch_info in data.get('channels', {}).items():
            if not is_all and region not in ch_info.get('regions', []):
                continue
            stream_url = f"https://jmp2.uk/plex-{ch_id}.m3u8"
            extinf = format_extinf(ch_id, ch_id, ch_info.get('chno'), ch_info['name'], 
                                  ch_info.get('logo', ''), ch_info.get('group', 'Plex'), ch_info['name'])
            output.append(extinf + stream_url + '\n')
        write_m3u_file(f"plex_{region}.m3u", "".join(output))

def generate_samsung_m3u(regions=['us', 'all']):
    SAMSUNG_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/SamsungTVPlus/.channels.json.gz'
    data = fetch_url(SAMSUNG_URL, is_json=True, is_gzipped=True)
    if not data: return

    for region in regions:
        is_all = region.lower() == 'all'
        output = ['#EXTM3U\n']
        target_regions = data['regions'].keys() if is_all else [region]
        
        for reg_key in target_regions:
            reg_channels = data['regions'].get(reg_key, {}).get('channels', {})
            for ch_id, ch_info in reg_channels.items():
                # Samsung bridge often uses a custom slug format
                slug_format = data.get('slug', '{id}')
                slug = slug_format.format(id=ch_id)
                stream_url = f"https://jmp2.uk/{slug}"
                extinf = format_extinf(ch_id, ch_id, ch_info.get('chno'), ch_info['name'], 
                                      ch_info.get('logo', ''), reg_key.upper(), ch_info['name'])
                output.append(extinf + stream_url + '\n')
        write_m3u_file(f"samsung_{region}.m3u", "".join(output))

def generate_roku_m3u():
    ROKU_URL = 'https://i.mjh.nz/Roku/.channels.json'
    data = fetch_url(ROKU_URL, is_json=True)
    if not data: return
    output = ['#EXTM3U\n']
    for ch_id, ch_info in data.get('channels', {}).items():
        stream_url = f"https://jmp2.uk/rok-{ch_id}.m3u8"
        extinf = format_extinf(ch_id, ch_id, ch_info.get('chno'), ch_info['name'], 
                              ch_info.get('logo', ''), "Roku", ch_info['name'])
        output.append(extinf + stream_url + '\n')
    write_m3u_file("roku_all.m3u", "".join(output))

def generate_tubi_m3u():
    TUBI_URL = 'https://raw.githubusercontent.com/BuddyChewChew/tubi-scraper/refs/heads/main/tubi_playlist.m3u'
    content = fetch_url(TUBI_URL, is_json=False)
    if content:
        lines = content.strip().splitlines()
        if lines and lines[0].startswith('#EXTM3U'):
            content = "\n".join(lines[1:])
        write_m3u_file("tubi_all.m3u", "#EXTM3U\n" + content)

def generate_stirr_m3u():
    STIRR_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/Stirr/.channels.json.gz'
    data = fetch_url(STIRR_URL, is_json=True, is_gzipped=True)
    if not data: return
    output = ['#EXTM3U\n']
    for ch_id, ch_info in data.get('channels', {}).items():
        stream_url = f"https://jmp2.uk/str-{ch_id}.m3u8"
        extinf = format_extinf(ch_id, ch_id, ch_info.get('chno'), ch_info['name'], 
                              ch_info.get('logo', ''), "Stirr", ch_info['name'])
        output.append(extinf + stream_url + '\n')
    write_m3u_file("stirr_all.m3u", "".join(output))

# --- Main Execution ---
if __name__ == "__main__":
    logging.info("Starting updated playlist generation...")
    
    # Run all services
    generate_pluto_m3u(regions=['us', 'gb', 'ca', 'all'])
    generate_plex_m3u(regions=['us', 'all'])
    generate_samsung_m3u(regions=['us', 'all'])
    generate_roku_m3u()
    generate_tubi_m3u()
    generate_stirr_m3u()
    
    logging.info("Process complete. Check the 'playlists' folder.")
