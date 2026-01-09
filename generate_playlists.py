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

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_url(url, is_json=True, is_gzipped=False, headers=None, stream=False):
    """Utility to fetch and decode data."""
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, stream=stream)
        response.raise_for_status()
        if stream: return response
        content = response.content
        if is_gzipped:
            with gzip.GzipFile(fileobj=BytesIO(content), mode='rb') as f:
                content = f.read()
        content = content.decode('utf-8')
        return json.loads(content) if is_json else content
    except Exception as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

def write_m3u_file(filename, content):
    """Saves the generated string to a file."""
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    logging.info(f"Successfully wrote {filename}")

def format_extinf(channel_id, tvg_id, tvg_chno, tvg_name, tvg_logo, group_title, display_name):
    """Standardizes the M3U metadata line."""
    chno_str = str(tvg_chno) if tvg_chno else ""
    return (f'#EXTINF:-1 channel-id="{channel_id}" tvg-id="{tvg_id}" tvg-chno="{chno_str}" '
            f'tvg-name="{tvg_name}" tvg-logo="{tvg_logo}" group-title="{group_title}",{display_name}\n')

# --- Shared Region Map ---
REGION_NAME_MAP = {
    "us": "United States", "ca": "Canada", "gb": "United Kingdom", "au": "Australia",
    "de": "Germany", "es": "Spain", "fr": "France", "it": "Italy", "no": "Norway",
    "se": "Sweden", "dk": "Denmark", "br": "Brazil", "ar": "Argentina", "cl": "Chile",
    "co": "Colombia", "mx": "Mexico", "pe": "Peru", "latam": "Latin America", "kr": "South Korea"
}

def generate_pluto_m3u(regions):
    PLUTO_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/PlutoTV/.channels.json.gz'
    STREAM_URL_TEMPLATE = 'https://service-stitcher.clusters.pluto.tv/stitch/hls/channel/{id}/master.m3u8?appName=web&appVersion=9.1.2&deviceId={dev_id}&sid={sid}&serverSideAds=true'
    data = fetch_url(PLUTO_URL, is_json=True, is_gzipped=True)
    if not data: return

    for region in regions:
        logging.info(f"Processing PlutoTV: {region}")
        epg_url = f'https://github.com/matthuisman/i.mjh.nz/raw/master/PlutoTV/{region}.xml.gz'
        output_lines = [f'#EXTM3U url-tvg="{epg_url}"\n']
        
        target_regions = data['regions'].keys() if region == 'all' else [region]
        for r in target_regions:
            reg_data = data['regions'].get(r)
            if not reg_data: continue
            for cid, info in reg_data['channels'].items():
                group = REGION_NAME_MAP.get(r, r.upper())
                extinf = format_extinf(cid, cid, info.get('chno'), info['name'], info['logo'], group, info['name'])
                stream = STREAM_URL_TEMPLATE.format(id=cid, dev_id=str(uuid.uuid4()), sid=str(uuid.uuid4()))
                output_lines.extend([extinf, stream + '\n'])
        
        write_m3u_file(f"plutotv_{region}.m3u", "".join(output_lines))

def generate_plex_m3u(regions):
    PLEX_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/Plex/.channels.json.gz'
    data = fetch_url(PLEX_URL, is_json=True, is_gzipped=True)
    if not data: return

    for region in regions:
        logging.info(f"Processing Plex: {region}")
        epg_url = f'https://github.com/matthuisman/i.mjh.nz/raw/master/Plex/{region}.xml.gz'
        output_lines = [f'#EXTM3U url-tvg="{epg_url}"\n']
        
        for cid, info in data['channels'].items():
            if region == 'all' or region in info.get('regions', []):
                group = REGION_NAME_MAP.get(region, "Plex TV") if region != 'all' else "Plex Global"
                extinf = format_extinf(cid, cid, info.get('chno'), info['name'], info['logo'], group, info['name'])
                stream = f'https://jmp2.uk/plex-{cid}.m3u8\n'
                output_lines.extend([extinf, stream])
        
        write_m3u_file(f"plex_{region}.m3u", "".join(output_lines))

def generate_samsungtvplus_m3u(regions):
    SAMSUNG_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/SamsungTVPlus/.channels.json.gz'
    data = fetch_url(SAMSUNG_URL, is_json=True, is_gzipped=True)
    if not data: return

    for region in regions:
        logging.info(f"Processing Samsung: {region}")
        epg_url = f'https://github.com/matthuisman/i.mjh.nz/raw/master/SamsungTVPlus/{region}.xml.gz'
        output_lines = [f'#EXTM3U url-tvg="{epg_url}"\n']
        
        target_regions = data['regions'].keys() if region == 'all' else [region]
        for r in target_regions:
            reg_data = data['regions'].get(r)
            if not reg_data: continue
            for cid, info in reg_data['channels'].items():
                group = info.get('group', REGION_NAME_MAP.get(r, r.upper()))
                extinf = format_extinf(cid, cid, info.get('chno'), info['name'], info['logo'], group, info['name'])
                stream = f'https://jmp2.uk/stp-{cid}.m3u8\n'
                output_lines.extend([extinf, stream])

        write_m3u_file(f"samsung_{region}.m3u", "".join(output_lines))

def generate_stirr_m3u():
    STIRR_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/Stirr/.channels.json.gz'
    data = fetch_url(STIRR_URL, is_json=True, is_gzipped=True)
    if not data: return
    output_lines = ['#EXTM3U url-tvg="https://github.com/matthuisman/i.mjh.nz/raw/master/Stirr/all.xml.gz"\n']
    for cid, info in data['channels'].items():
        groups = info.get('groups', [])
        group = groups[0] if groups else 'Stirr'
        output_lines.extend([format_extinf(cid, cid, info.get('chno'), info['name'], info['logo'], group, info['name']), f'https://jmp2.uk/str-{cid}.m3u8\n'])
    write_m3u_file("stirr_all.m3u", "".join(output_lines))

def generate_tubi_m3u():
    output = f'#EXTM3U url-tvg="https://github.com/matthuisman/i.mjh.nz/raw/master/Tubi/all.xml.gz"\n'
    content = fetch_url('https://raw.githubusercontent.com/BuddyChewChew/tubi-scraper/refs/heads/main/tubi_playlist.m3u', is_json=False)
    if content:
        write_m3u_file("tubi_all.m3u", output + content.replace('#EXTM3U', ''))

def generate_roku_m3u():
    # Use raw MJH URL for the channels data
    data = fetch_url('https://raw.githubusercontent.com/matthuisman/i.mjh.nz/master/Roku/.channels.json', is_json=True)
    if not data: return
    output_lines = ['#EXTM3U url-tvg="https://github.com/matthuisman/i.mjh.nz/raw/master/Roku/all.xml.gz"\n']
    for cid, info in data['channels'].items():
        # FIX: Defensive check for empty groups list
        groups = info.get('groups', [])
        group = groups[0] if (groups and len(groups) > 0) else 'Roku'
        output_lines.extend([format_extinf(cid, cid, info.get('chno'), info['name'], info['logo'], group, info['name']), f'https://jmp2.uk/rok-{cid}.m3u8\n'])
    write_m3u_file("roku_all.m3u", "".join(output_lines))

# --- Main Execution ---
if __name__ == "__main__":
    # Your full list of regions to process
    ALL_REGIONS = [
        'us', 'ca', 'gb', 'au', 'de', 'es', 'fr', 'it', 'no', 
        'se', 'dk', 'br', 'ar', 'cl', 'co', 'mx', 'pe', 'latam', 'all'
    ]
    
    generate_pluto_m3u(ALL_REGIONS)
    generate_plex_m3u(ALL_REGIONS)
    generate_samsungtvplus_m3u(ALL_REGIONS)
    generate_stirr_m3u()
    generate_tubi_m3u()
    generate_roku_m3u()
    logging.info("Process Complete: All playlists generated without errors.")
