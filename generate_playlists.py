import requests
import gzip
import json
import os
import logging
import re
from io import BytesIO

# --- Configuration ---
OUTPUT_DIR = "playlists"
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
REQUEST_TIMEOUT = 30 

REGION_MAP = {
    'us': 'United States', 'gb': 'United Kingdom', 'ca': 'Canada',
    'de': 'Germany', 'es': 'Spain', 'fr': 'France', 'it': 'Italy', 
    'br': 'Brazil', 'mx': 'Mexico', 'ar': 'Argentina', 'au': 'Australia'
}

KEYWORD_CATEGORIES = {
    'Movies': ['movie', 'cinema', 'film', 'hallmark', 'thriller'],
    'News': ['news', 'reuters', 'bloomberg', 'weather', 'local', 'bbc', 'cnn', 'msnbc'],
    'Sports': ['sport', 'nfl', 'mlb', 'fubo', 'racing', 'fight', 'golf', 'soccer'],
    'Kids': ['kids', 'cartoon', 'nick', 'baby', 'disney'],
    'Music': ['music', 'mtv', 'vevo', 'concert', 'vh1'],
    'Comedy': ['comedy', 'funny', 'laugh', 'sitcom'],
    'Crime': ['crime', 'mystery', 'detective', 'forensic', 'law']
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_smart_category(channel_name):
    name_lower = channel_name.lower()
    for category, keywords in KEYWORD_CATEGORIES.items():
        if any(kw in name_lower for kw in keywords):
            return category
    return "Unsorted"

def cleanup_output_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    else:
        for f in os.listdir(OUTPUT_DIR):
            if f.endswith(".m3u"):
                try: os.remove(os.path.join(OUTPUT_DIR, f))
                except: pass

def fetch_url(url, is_json=True, is_gzipped=False):
    try:
        response = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        content = response.content
        if is_gzipped:
            with gzip.GzipFile(fileobj=BytesIO(content), mode='rb') as f:
                content = f.read()
        return json.loads(content.decode('utf-8')) if is_json else content.decode('utf-8')
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return None

def format_extinf(c_id, tvg_id, chno, name, logo, group):
    clean_name = name.replace('"', "'")
    return f'#EXTINF:-1 channel-id="{c_id}" tvg-id="{tvg_id}" tvg-chno="{chno or ""}" tvg-logo="{logo}" group-title="{group}",{clean_name}\n'

# --- Service Generators ---

def generate_pluto_m3u():
    data = fetch_url('https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/PlutoTV/.channels.json.gz', is_gzipped=True)
    if not data: return
    for reg in list(data['regions'].keys()) + ['all']:
        output = [f'#EXTM3U url-tvg="https://github.com/matthuisman/i.mjh.nz/raw/master/PlutoTV/{reg}.xml.gz"\n']
        channels = []
        if reg == 'all':
            for rc, rd in data['regions'].items():
                for cid, ci in rd.get('channels', {}).items():
                    grp = f"{REGION_MAP.get(rc, rc.upper())}: {ci.get('group', 'Unsorted')}"
                    channels.append({**ci, 'id': f"{cid}-{rc}", 'orig_id': cid, 'group': grp})
        else:
            r_data = data['regions'].get(reg, {}).get('channels', {})
            for cid, ci in r_data.items():
                channels.append({**ci, 'id': cid, 'orig_id': cid, 'group': ci.get('group', 'Unsorted')})
        for ch in sorted(channels, key=lambda x: x['name']):
            output.append(format_extinf(ch['id'], ch['orig_id'], ch.get('chno'), ch['name'], ch['logo'], ch['group']))
            output.append(f"https://jmp2.uk/plu-{ch['orig_id']}.m3u8\n")
        with open(os.path.join(OUTPUT_DIR, f"plutotv_{reg}.m3u"), 'w', encoding='utf-8') as f: f.write("".join(output))

def generate_plex_m3u():
    data = fetch_url('https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/Plex/.channels.json.gz', is_gzipped=True)
    if not data: return
    regs = set()
    for ch in data['channels'].values(): regs.update(ch.get('regions', []))
    for reg in list(regs) + ['all']:
        output = [f'#EXTM3U url-tvg="https://github.com/matthuisman/i.mjh.nz/raw/master/Plex/{reg}.xml.gz"\n']
        for cid, ch in data['channels'].items():
            if reg == 'all' or reg in ch.get('regions', []):
                group = get_smart_category(ch['name'])
                output.append(format_extinf(cid, cid, ch.get('chno'), ch['name'], ch['logo'], group))
                output.append(f"https://jmp2.uk/plex-{cid}.m3u8\n")
        with open(os.path.join(OUTPUT_DIR, f"plex_{reg}.m3u"), 'w', encoding='utf-8') as f: f.write("".join(output))

def generate_samsungtvplus_m3u():
    data = fetch_url('https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/SamsungTVPlus/.channels.json.gz', is_gzipped=True)
    if not data: return
    for reg in list(data['regions'].keys()) + ['all']:
        output = [f'#EXTM3U url-tvg="https://github.com/matthuisman/i.mjh.nz/raw/master/SamsungTVPlus/{reg}.xml.gz"\n']
        channels = []
        if reg == 'all':
            for rc, ri in data['regions'].items():
                for cid, ci in ri.get('channels', {}).items():
                    grp = f"{REGION_MAP.get(rc, rc.upper())}: {ci.get('group', 'Unsorted')}"
                    channels.append({**ci, 'id': f"{cid}-{rc}", 'orig_id': cid, 'group': grp})
        else:
            r_info = data['regions'].get(reg, {}).get('channels', {})
            for cid, ci in r_info.items():
                channels.append({**ci, 'id': cid, 'orig_id': cid, 'group': ci.get('group', 'Unsorted')})
        for ch in sorted(channels, key=lambda x: x['name']):
            slug = ch.get('slug', 'stvp-{id}').replace('{id}', ch['orig_id'])
            output.append(format_extinf(ch['id'], ch['orig_id'], ch.get('chno'), ch['name'], ch['logo'], ch['group']))
            output.append(f"https://jmp2.uk/{slug}\n")
        with open(os.path.join(OUTPUT_DIR, f"samsungtvplus_{reg}.m3u"), 'w', encoding='utf-8') as f: f.write("".join(output))

def generate_stirr_m3u():
    data = fetch_url('https://github.com/matthuisman/i.mjh.nz/raw/refs/heads/master/Stirr/.channels.json.gz', is_gzipped=True)
    if not data: return
    output = ['#EXTM3U url-tvg="https://github.com/matthuisman/i.mjh.nz/raw/master/Stirr/all.xml.gz"\n']
    for cid, ch in data['channels'].items():
        # SAFETY FIX: Ensure group isn't empty
        grps = ch.get('groups', [])
        group = ", ".join(grps) if grps else "Unsorted"
        output.append(format_extinf(cid, cid, ch.get('chno'), ch['name'], ch['logo'], group))
        output.append(f"https://jmp2.uk/str-{cid}.m3u8\n")
    with open(os.path.join(OUTPUT_DIR, "stirr_all.m3u"), 'w', encoding='utf-8') as f: f.write("".join(output))

def generate_roku_m3u():
    data = fetch_url('https://i.mjh.nz/Roku/.channels.json') 
    if not data: return
    output = ['#EXTM3U url-tvg="https://github.com/matthuisman/i.mjh.nz/raw/master/Roku/all.xml.gz"\n']
    for cid, ch in data['channels'].items():
        # SAFETY FIX: Prevent IndexError if groups list is empty
        grps = ch.get('groups', [])
        group = grps[0] if grps else "Unsorted"
        output.append(format_extinf(cid, cid, ch.get('chno'), ch['name'], ch['logo'], group))
        output.append(f"https://jmp2.uk/rok-{cid}.m3u8\n")
    with open(os.path.join(OUTPUT_DIR, "roku_all.m3u"), 'w', encoding='utf-8') as f: f.write("".join(output))

def generate_tubi_m3u():
    content = fetch_url('https://raw.githubusercontent.com/BuddyChewChew/tubi-scraper/refs/heads/main/tubi_playlist.m3u', is_json=False)
    if not content: return
    output = ['#EXTM3U url-tvg="https://raw.githubusercontent.com/BuddyChewChew/tubi-scraper/refs/heads/main/tubi_epg.xml"\n']
    current_line = ""
    for line in content.strip().split('\n'):
        if line.startswith('#EXTINF'):
            try:
                parts = line.rsplit(',', 1)
                name = parts[1].strip() if len(parts) > 1 else "Tubi Channel"
                group = get_smart_category(name)
                tags_part = parts[0]
                if 'group-title="' in tags_part:
                    pre_group = tags_part.split('group-title="', 1)[0]
                    post_group = tags_part.split('group-title="', 1)[1].split('"', 1)[1]
                    tags_part = f'{pre_group}group-title="{group}"{post_group}'
                else:
                    tags_part += f' group-title="{group}"'
                current_line = f"{tags_part},{name}"
            except:
                current_line = line
        elif line.startswith('http'):
            output.append(f"{current_line}\n{line}\n")
    with open(os.path.join(OUTPUT_DIR, "tubi_all.m3u"), 'w', encoding='utf-8') as f: f.write("".join(output))

if __name__ == "__main__":
    cleanup_output_dir()
    generate_pluto_m3u()
    generate_plex_m3u()
    generate_samsungtvplus_m3u()
    generate_stirr_m3u()
    generate_roku_m3u()
    generate_tubi_m3u()
    logger.info("Playlist generation complete.")
