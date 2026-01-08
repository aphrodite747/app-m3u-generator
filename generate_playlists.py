import uuid
import requests
import gzip
import json
import os
import logging
from io import BytesIO

# --- Configuration ---
OUTPUT_DIR = "playlists"
# Updated User-Agent to a more modern browser string
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
REQUEST_TIMEOUT = 30 # seconds

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Functions ---
def fetch_url(url, is_json=True, is_gzipped=False, headers=None, stream=False):
    """Fetches data with enhanced headers to mimic a browser and bypass 403s."""
    logging.info(f"Fetching URL: {url}")
    
    # Base headers to look like a real browser
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
            except Exception as e:
                logging.warning(f"Gzip decompression failed, trying plain text: {e}")
                content = content.decode('utf-8')
        else:
            content = content.decode('utf-8')

        return json.loads(content) if is_json else content

    except Exception as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

def write_m3u_file(filename, content):
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

def generate_pluto_m3u(regions=['us', 'ca', 'gb', 'au', 'all'], sort='name'):
    """Generates M3U for PlutoTV using Slug-based URLs and unique SIDs to bypass 403s."""
    PLUTO_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/PlutoTV/.channels.json.gz'
    # Use pluto-{slug} which is much more stable than plu-{id}
    STREAM_URL_TEMPLATE = 'https://jmp2.uk/pluto-{slug}.m3u8'
    EPG_URL_TEMPLATE = 'https://github.com/matthuisman/i.mjh.nz/raw/master/PlutoTV/{region}.xml.gz'

    data = fetch_url(PLUTO_URL, is_json=True, is_gzipped=True)
    if not data or 'regions' not in data:
        logging.error("Failed to fetch or parse PlutoTV data.")
        return

    region_name_map = {
        "ar": "Argentina", "br": "Brazil", "ca": "Canada", "cl": "Chile", "co": "Colombia",
        "cr": "Costa Rica", "de": "Germany", "dk": "Denmark", "do": "Dominican Republic",
        "ec": "Ecuador", "es": "Spain", "fr": "France", "gb": "United Kingdom", "gt": "Guatemala",
        "it": "Italy", "mx": "Mexico", "no": "Norway", "pe": "Peru", "se": "Sweden",
        "us": "United States", "latam": "Latin America"
    }

    for region in regions:
        logging.info(f"--- Generating PlutoTV playlist for region: {region} ---")
        is_all_region = region.lower() == 'all'
        epg_url = EPG_URL_TEMPLATE.replace('{region}', "all" if is_all_region else region)
        output_lines = [f'#EXTM3U url-tvg="{epg_url}"\n']
        
        channels_to_process = {}
        target_regions = data['regions'].keys() if is_all_region else [region]

        for reg_key in target_regions:
            reg_data = data['regions'].get(reg_key)
            if not reg_data: continue
            
            region_full_name = region_name_map.get(reg_key, reg_key.upper())

            for channel_key, channel_info in reg_data.get('channels', {}).items():
                unique_channel_id = f"{channel_key}-{reg_key}" if is_all_region else channel_key
                channels_to_process[unique_channel_id] = {
                    **channel_info,
                    'region_code': reg_key,
                    'group_title_override': region_full_name if is_all_region else channel_info.get('group', 'PlutoTV'),
                    'original_id': channel_key
                }

        # Sorting logic
        sorted_ids = sorted(channels_to_process.keys(), 
                            key=lambda k: int(channels_to_process[k].get('chno', 99999)) if sort == 'chno' 
                            else channels_to_process[k].get('name', '').lower())

        for channel_id in sorted_ids:
            ch = channels_to_process[channel_id]
            # Use Slug for the stream URL, fallback to ID if missing
            slug = ch.get('slug', ch['original_id'])
            
            # Add a unique Session ID (SID) to the URL to bypass 403 tokens
            sid = str(uuid.uuid4())
            stream_url = STREAM_URL_TEMPLATE.format(slug=slug) + f"?sid={sid}&device_id={sid}"
            
            extinf = format_extinf(channel_id, ch['original_id'], ch.get('chno'), 
                                  ch['name'], ch.get('logo', ''), ch['group_title_override'], ch['name'])
            
            output_lines.append(extinf)
            output_lines.append(stream_url + '\n')

        write_m3u_file(f"plutotv_{region}.m3u", "".join(output_lines))

def generate_plex_m3u(regions=['us', 'ca', 'gb', 'au', 'all'], sort='name'):
    PLEX_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/Plex/.channels.json.gz'
    STREAM_URL_TEMPLATE = 'https://jmp2.uk/plex-{id}.m3u8'
    EPG_URL_TEMPLATE = 'https://github.com/matthuisman/i.mjh.nz/raw/master/Plex/{region}.xml.gz'
    
    data = fetch_url(PLEX_URL, is_json=True, is_gzipped=True)
    if not data: return

    for region in regions:
        is_all = region.lower() == 'all'
        epg_url = EPG_URL_TEMPLATE.replace('{region}', region)
        output_lines = [f'#EXTM3U url-tvg="{epg_url}"\n']
        
        # Simple loop for Plex
        for ch_id, ch_info in data.get('channels', {}).items():
            if not is_all and region not in ch_info.get('regions', []):
                continue
            
            extinf = format_extinf(ch_id, ch_id, ch_info.get('chno'), ch_info['name'], 
                                  ch_info.get('logo', ''), ch_info.get('group', 'Plex'), ch_info['name'])
            stream_url = STREAM_URL_TEMPLATE.replace('{id}', ch_id)
            output_lines.append(extinf + stream_url + '\n')

        write_m3u_file(f"plex_{region}.m3u", "".join(output_lines))

def generate_samsungtvplus_m3u(regions=['us', 'all']):
    SAMSUNG_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/SamsungTVPlus/.channels.json.gz'
    data = fetch_url(SAMSUNG_URL, is_json=True, is_gzipped=True)
    if not data: return

    for region in regions:
        is_all = region.lower() == 'all'
        output_lines = ['#EXTM3U\n']
        target_regions = data['regions'].keys() if is_all else [region]
        
        for reg_key in target_regions:
            reg_channels = data['regions'].get(reg_key, {}).get('channels', {})
            for ch_id, ch_info in reg_channels.items():
                # Samsung uses a slug-based format in its own data structure
                slug = data.get('slug', '{id}').format(id=ch_id)
                stream_url = f"https://jmp2.uk/{slug}"
                extinf = format_extinf(ch_id, ch_id, ch_info.get('chno'), ch_info['name'], 
                                      ch_info.get('logo', ''), reg_key, ch_info['name'])
                output_lines.append(extinf + stream_url + '\n')
        
        write_m3u_file(f"samsung_{region}.m3u", "".join(output_lines))

def generate_stirr_m3u():
    STIRR_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/Stirr/.channels.json.gz'
    data = fetch_url(STIRR_URL, is_json=True, is_gzipped=True)
    if not data: return
    output_lines = ['#EXTM3U\n']
    for ch_id, ch_info in data.get('channels', {}).items():
        stream_url = f"https://jmp2.uk/str-{ch_id}.m3u8"
        extinf = format_extinf(ch_id, ch_id, ch_info.get('chno'), ch_info['name'], 
                              ch_info.get('logo', ''), "Stirr", ch_info['name'])
        output_lines.append(extinf + stream_url + '\n')
    write_m3u_file("stirr_all.m3u", "".join(output_lines))

def generate_tubi_m3u():
    TUBI_URL = 'https://raw.githubusercontent.com/BuddyChewChew/tubi-scraper/refs/heads/main/tubi_playlist.m3u'
    content = fetch_url(TUBI_URL, is_json=False)
    if content:
        # Clean up existing headers if present
        lines = content.strip().splitlines()
        if lines and lines[0].startswith('#EXTM3U'):
            content = "\n".join(lines[1:])
        write_m3u_file("tubi_all.m3u", "#EXTM3U\n" + content)

def generate_roku_m3u():
    ROKU_URL = 'https://i.mjh.nz/Roku/.channels.json'
    data = fetch_url(ROKU_URL, is_json=True)
    if not data: return
    output_lines = ['#EXTM3U\n']
    for ch_id, ch_info in data.get('channels', {}).items():
        stream_url = f"https://jmp2.uk/rok-{ch_id}.m3u8"
        extinf = format_extinf(ch_id, ch_id, ch_info.get('chno'), ch_info['name'], 
                              ch_info.get('logo', ''), "Roku", ch_info['name'])
        output_lines.append(extinf + stream_url + '\n')
    write_m3u_file("roku_all.m3u", "".join(output_lines))

# --- Main Execution ---
if __name__ == "__main__":
    logging.info("Starting playlist generation process...")
    
    # Define target regions
    regions_list = ['us', 'gb', 'ca', 'all']
    
    # Run Pluto Logic (Primary Focus)
    generate_pluto_m3u(regions=regions_list)
    
    # Run other services
    generate_plex_m3u(regions=regions_list)
    generate_samsungtvplus_m3u(regions=['us', 'all'])
    generate_stirr_m3u()
    generate_tubi_m3u()
    generate_roku_m3u()
    
    logging.info("Playlist generation process completed.")
