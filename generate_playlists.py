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
REQUEST_TIMEOUT = 30 # seconds

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Functions ---
def fetch_url(url, is_json=True, is_gzipped=False, headers=None, stream=False, retries=3):
    """Fetches data with retry logic and handling for 429 Rate Limits."""
    logging.info(f"Fetching URL: {url}")
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, stream=stream)
            
            # Handle GitHub Rate Limiting
            if response.status_code == 429:
                wait_time = (i + 1) * 10
                logging.warning(f"Rate limited (429). Sleeping {wait_time}s before retry...")
                time.sleep(wait_time)
                continue
                
            response.raise_for_status()

            if stream:
                return response

            content = response.content
            if is_gzipped:
                try:
                    with gzip.GzipFile(fileobj=BytesIO(content), mode='rb') as f:
                        content = f.read()
                    content = content.decode('utf-8')
                except gzip.BadGzipFile:
                    content = content.decode('utf-8')
            else:
                content = content.decode('utf-8')

            if is_json:
                return json.loads(content)
            return content

        except Exception as e:
            logging.error(f"Attempt {i+1} failed for {url}: {e}")
            if i < retries - 1:
                time.sleep(2)
    return None

def write_m3u_file(filename, content):
    """Writes content to a file in the output directory."""
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
    """Formats the #EXTINF line."""
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

def generate_pluto_m3u(regions=['us', 'ca', 'gb', 'all'], sort='name'):
    """Generates M3U playlists for PlutoTV with V4 Stitcher fix."""
    PLUTO_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/PlutoTV/.channels.json.gz'
    STREAM_URL_TEMPLATE = (
        'https://service-stitcher.clusters.pluto.tv/stitch/hls/channel/{id}/master.m3u8'
        '?advertisingId=&appName=web&appVersion=9.1.2&deviceDNT=0'
        '&deviceId={dev_id}&deviceMake=Chrome&deviceModel=web&deviceType=web'
        '&deviceVersion=126.0.0&sid={sid}&userId=&serverSideAds=true'
    )
    EPG_URL_TEMPLATE = 'https://github.com/matthuisman/i.mjh.nz/raw/master/PlutoTV/{region}.xml.gz'

    data = fetch_url(PLUTO_URL, is_json=True, is_gzipped=True)
    if not data or 'regions' not in data:
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
        time.sleep(0.5) # Anti-throttle
        epg_url = EPG_URL_TEMPLATE.replace('{region}', region)
        output_lines = [f'#EXTM3U url-tvg="{epg_url}"\n', '#EXT-X-DISCONTINUITY-SEQUENCE:0\n']
        channels_to_process = {}
        is_all_region = region.lower() == 'all'

        if is_all_region:
            for region_key, region_data in data.get('regions', {}).items():
                region_full_name = region_name_map.get(region_key, region_key.upper())
                for channel_key, channel_info in region_data.get('channels', {}).items():
                    unique_channel_id = f"{channel_key}-{region_key}"
                    channels_to_process[unique_channel_id] = {
                        **channel_info,
                        'region_code': region_key,
                        'group_title_override': region_full_name,
                        'original_id': channel_key
                    }
        else:
            region_data = data.get('regions', {}).get(region)
            if not region_data: continue
            for channel_key, channel_info in region_data.get('channels', {}).items():
                 channels_to_process[channel_key] = {
                     **channel_info,
                     'region_code': region,
                     'original_id': channel_key
                 }

        sorted_channel_ids = sorted(channels_to_process.keys(), key=lambda k: channels_to_process[k].get('name', '').lower())

        for channel_id in sorted_channel_ids:
            channel = channels_to_process[channel_id]
            extinf = format_extinf(channel_id, channel.get('original_id'), channel.get('chno'), channel.get('name'), channel.get('logo'), channel.get('group_title_override') if is_all_region else channel.get('group', 'Uncategorized'), channel.get('name'))
            stream_url = STREAM_URL_TEMPLATE.format(id=channel.get('original_id'), dev_id=str(uuid.uuid4()), sid=str(uuid.uuid4()))
            output_lines.extend([extinf, stream_url + '\n'])

        write_m3u_file(f"plutotv_{region}.m3u", "".join(output_lines))

def generate_plex_m3u(regions=['us', 'ca', 'gb', 'au', 'all'], sort='name'):
    """Generates M3U playlists for Plex using only the core MJH file."""
    PLEX_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/Plex/.channels.json.gz'
    EPG_URL_TEMPLATE = 'https://github.com/matthuisman/i.mjh.nz/raw/master/Plex/{region}.xml.gz'
    
    data = fetch_url(PLEX_URL, is_json=True, is_gzipped=True, headers={'User-Agent': USER_AGENT})
    if not data or 'channels' not in data:
        logging.error("Failed to fetch or parse Plex data.")
        return

    region_name_map = {
        "us": "United States", "mx": "Mexico", "es": "Spain", "ca": "Canada",
        "au": "Australia", "nz": "New Zealand", "br": "Brazil", "gb": "United Kingdom",
        "de": "Germany", "ch": "Switzerland", "it": "Italy", "fr": "France",
        "at": "Austria", "ie": "Ireland", "za": "South Africa"
    }

    for region in regions:
        logging.info(f"--- Generating Plex playlist for region: {region} ---")
        time.sleep(0.5) # Anti-throttle
        epg_url = EPG_URL_TEMPLATE.replace('{region}', region)
        output_lines = [f'#EXTM3U url-tvg="{epg_url}"\n']
        channels_to_process = {}
        is_all_region = region.lower() == 'all'
        all_plex_channels = data.get('channels', {})

        for channel_key, channel_info in all_plex_channels.items():
            channel_regions = channel_info.get('regions', [])
            
            if is_all_region or region in channel_regions:
                # If 'all', we create entries for every region the channel belongs to
                target_regs = channel_regions if is_all_region else [region]
                
                for reg_code in target_regs:
                    unique_id = f"{channel_key}-{reg_code}" if is_all_region else channel_key
                    group_name = region_name_map.get(reg_code, reg_code.upper())
                    
                    channels_to_process[unique_id] = {
                        **channel_info,
                        'group': group_name,
                        'original_id': channel_key
                    }

        sorted_ids = sorted(channels_to_process.keys(), key=lambda k: channels_to_process[k].get('name', '').lower())

        for cid in sorted_ids:
            ch = channels_to_process[cid]
            extinf = format_extinf(cid, ch['original_id'], ch.get('chno'), ch['name'], ch['logo'], ch['group'], ch['name'])
            stream_url = f"https://jmp2.uk/plex-{ch['original_id']}.m3u8\n"
            output_lines.extend([extinf, stream_url])

        write_m3u_file(f"plex_{region}.m3u", "".join(output_lines))

def generate_samsungtvplus_m3u(regions=['us', 'ca', 'gb', 'au', 'de', 'kr', 'all'], sort='name'):
    """Generates M3U playlists for SamsungTVPlus."""
    SAMSUNG_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/SamsungTVPlus/.channels.json.gz'
    STREAM_URL_TEMPLATE = 'https://jmp2.uk/{slug}'
    EPG_URL_TEMPLATE = 'https://github.com/matthuisman/i.mjh.nz/raw/master/SamsungTVPlus/{region}.xml.gz'

    data = fetch_url(SAMSUNG_URL, is_json=True, is_gzipped=True)
    if not data or 'regions' not in data:
        return

    for region in regions:
        logging.info(f"--- Generating SamsungTVPlus playlist for region: {region} ---")
        time.sleep(0.5)
        epg_url = EPG_URL_TEMPLATE.replace('{region}', region)
        output_lines = [f'#EXTM3U url-tvg="{epg_url}"\n']
        channels_to_process = {}
        is_all_region = region.lower() == 'all'

        if is_all_region:
            for region_key, region_data in data.get('regions', {}).items():
                region_full_name = region_data.get('name', region_key.upper())
                for channel_key, channel_info in region_data.get('channels', {}).items():
                    unique_channel_id = f"{channel_key}-{region_key}"
                    channels_to_process[unique_channel_id] = {**channel_info, 'group_title_override': region_full_name, 'original_id': channel_key}
        else:
            region_data = data.get('regions', {}).get(region)
            if not region_data: continue
            for channel_key, channel_info in region_data.get('channels', {}).items():
                 channels_to_process[channel_key] = {**channel_info, 'original_id': channel_key}

        sorted_channel_ids = sorted(channels_to_process.keys(), key=lambda k: channels_to_process[k].get('name', '').lower())

        for channel_id in sorted_channel_ids:
            channel = channels_to_process[channel_id]
            group = channel.get('group_title_override') if is_all_region else channel.get('group', 'Uncategorized')
            extinf = format_extinf(channel_id, channel.get('original_id'), channel.get('chno'), channel.get('name'), channel.get('logo'), group or 'Samsung TV', channel.get('name'))
            stream_url = STREAM_URL_TEMPLATE.format(slug=data['slug'].format(id=channel.get('original_id')))
            output_lines.extend([extinf, stream_url + '\n'])

        write_m3u_file(f"samsungtvplus_{region}.m3u", "".join(output_lines))

def generate_stirr_m3u(sort='name'):
    """Generates M3U playlist for Stirr."""
    STIRR_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/Stirr/.channels.json.gz'
    STREAM_URL_TEMPLATE = 'https://jmp2.uk/str-{id}.m3u8'
    EPG_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/master/Stirr/all.xml.gz'

    logging.info("--- Generating Stirr playlist ---")
    data = fetch_url(STIRR_URL, is_json=True, is_gzipped=True)
    if not data or 'channels' not in data: return

    output_lines = [f'#EXTM3U url-tvg="{EPG_URL}"\n']
    channels_to_process = data.get('channels', {})
    sorted_channel_ids = sorted(channels_to_process.keys(), key=lambda k: channels_to_process[k].get('name', '').lower())

    for channel_id in sorted_channel_ids:
        channel = channels_to_process[channel_id]
        groups_list = channel.get('groups', [])
        group_str = ', '.join(groups_list) if groups_list else 'Uncategorized'
        extinf = format_extinf(channel_id, channel_id, channel.get('chno'), channel.get('name'), channel.get('logo'), group_str, channel.get('name'))
        output_lines.extend([extinf, STREAM_URL_TEMPLATE.replace('{id}', channel_id) + '\n'])

    write_m3u_file("stirr_all.m3u", "".join(output_lines))

def generate_tubi_m3u():
    """Generates M3U playlist for Tubi."""
    TUBI_PLAYLIST_URL = 'https://raw.githubusercontent.com/BuddyChewChew/tubi-scraper/refs/heads/main/tubi_playlist.m3u'
    EPG_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/master/Tubi/all.xml.gz'
    
    logging.info("--- Generating Tubi playlist ---")
    playlist_content = fetch_url(TUBI_PLAYLIST_URL, is_json=False)
    if not playlist_content: return

    lines = playlist_content.strip().splitlines()
    playlist_data = "\n".join(lines[1:]) if lines and lines[0].strip().upper() == '#EXTM3U' else "\n".join(lines)
    write_m3u_file("tubi_all.m3u", f'#EXTM3U url-tvg="{EPG_URL}"\n{playlist_data}\n')

def generate_roku_m3u(sort='name'):
    """Generates M3U playlist for Roku. (UNTOUCHED)"""
    ROKU_URL = 'https://i.mjh.nz/Roku/.channels.json'
    STREAM_URL_TEMPLATE = 'https://jmp2.uk/rok-{id}.m3u8'
    EPG_URL = 'https://github.com/matthuisman/i.mjh.nz/raw/master/Roku/all.xml.gz'

    logging.info("--- Generating Roku playlist ---")
    data = fetch_url(ROKU_URL, is_json=True, is_gzipped=False) 
    if not data or 'channels' not in data:
        return

    output_lines = [f'#EXTM3U url-tvg="{EPG_URL}"\n']
    channels_to_process = data.get('channels', {})
    sorted_channel_ids = sorted(channels_to_process.keys(), key=lambda k: channels_to_process[k].get('name', '').lower())

    for channel_id in sorted_channel_ids:
        channel = channels_to_process[channel_id]
        groups = channel.get('groups', [])
        group = groups[0] if groups and len(groups) > 0 else 'Uncategorized'
        extinf = format_extinf(channel_id, channel_id, channel.get('chno'), channel.get('name'), channel.get('logo'), group, channel.get('name'))
        output_lines.append(extinf)
        output_lines.append(STREAM_URL_TEMPLATE.replace('{id}', channel_id) + '\n')

    write_m3u_file("roku_all.m3u", "".join(output_lines))

# --- Main Execution ---
if __name__ == "__main__":
    logging.info("Starting playlist generation process...")
    
    services = ['pluto', 'plex', 'samsungtvplus', 'stirr', 'tubi', 'roku']
    regions = ['us', 'ca', 'gb', 'au', 'de', 'es', 'fr', 'it', 'no', 'se', 'dk', 'br', 'ar', 'cl', 'co', 'mx', 'pe', 'latam', 'all'] 
    
    for service in services:
        try:
            if service == 'pluto':
                generate_pluto_m3u(regions=regions)
            elif service == 'plex':
                generate_plex_m3u(regions=regions)
            elif service == 'samsungtvplus':
                generate_samsungtvplus_m3u(regions=regions)
            elif service == 'stirr':
                generate_stirr_m3u()
            elif service == 'tubi':
                generate_tubi_m3u()
            elif service == 'roku':
                generate_roku_m3u()
            
            # Pause between services to avoid GitHub flagging
            time.sleep(2)
        except Exception as e:
            logging.error(f"Error generating {service} playlist: {e}")
            
    logging.info("Playlist generation process completed.")
