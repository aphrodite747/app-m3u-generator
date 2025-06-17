# ⭐ FAST Service M3U Playlist Generator

This repository automatically generates M3U playlist files for various free ad-supported streaming television (FAST) services using a Python script and GitHub Actions. The playlists include embedded EPG (Electronic Program Guide) information via the `url-tvg` tag in the M3U header.

## ▶️ How It Works

1.  **Data Fetching:** A Python script (`generate_playlists.py`) fetches the latest channel data from reliable upstream sources ( primarily repositories maintained by [matthuisman/i.mjh.nz](https://github.com/matthuisman/i.mjh.nz ) and [BuddyChewChew/tubi-scraper](https://github.com/BuddyChewChew/tubi-scraper)).
2.  **M3U Generation:** The script parses the data, formats it into the standard M3U playlist format, and includes the appropriate `url-tvg` EPG link in the header for compatible players.
3.  **GitHub Action:** A scheduled GitHub Action (`.github/workflows/generate_playlists.yml`) runs the Python script daily (around 03:00 UTC by default).
4.  **Commit Updates:** The workflow checks if the newly generated playlists differ from the ones currently in the repository. If changes are detected, the Action commits and pushes the updated files to the `playlists/` directory. If no changes are detected, no commit is made, keeping the history clean.

## ▶️ Services Included

This generator currently creates playlists for:

*   **Pluto TV** (`plutotv_us.m3u`, `plutotv_all.m3u`)
*   **Plex Live TV** (`plex_us.m3u`, `plex_all.m3u`)
*   **Samsung TV Plus** (`samsungtvplus_us.m3u`, `samsungtvplus_all.m3u`)
*   **Stirr TV** (`stirr_all.m3u`) 👉 Might be removing. No working EPG.
*   **Tubi TV** (`tubi_all.m3u`) 

**Example URLs:**

*   **Plex US:** `https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/refs/heads/main/playlists/plex_us.m3u`
*   **Plex All Regions:** `https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/refs/heads/main/playlists/plex_all.m3u`

*(Note: The `_us` versions contain channels specific to the US region, while `_all` versions attempt to combine channels from multiple available regions, grouped by region/country.)*

## ▶️ How to Use

The generated M3U files can be found in the [`playlists/`](https://github.com/BuddyChewChew/app-m3u-generator/tree/main/playlists) directory of this repository.

You can use these playlists in any IPTV player application that supports M3U playlists with remote URLs (e.g., TiviMate, IPTV Smarters, VLC, Kodi PVR IPTV Simple Client, OTT Navigator, etc.).

**To get the URL for a specific playlist:**

1.  Navigate to the [`playlists/`](https://github.com/BuddyChewChew/app-m3u-generator/tree/main/playlists) directory.
2.  Click on the desired `.m3u` file (e.g., `plutotv_us.m3u`).
3.  On the file page, click the **"Raw"** button.
4.  Copy the URL from your browser's address bar.

The URL will look like this pattern:
https://raw.githubusercontent.com/BuddyChewChew/app-to-iptv/main/playlists/FILENAME.m3u


*Replace `FILENAME.m3u` with the specific playlist file you want (e.g., `plex_all.m3u`).*

Paste this complete raw URL into your IPTV player's M3U playlist source field. The player should automatically fetch the playlist and the EPG data specified in the `url-tvg` tag.

## ▶️ Update Schedule

Playlists are automatically checked for updates daily via the GitHub Action workflow (around 03:00 UTC, unless the schedule in the `.yml` file is changed). Your IPTV player should periodically refresh the playlist URL to get the latest channel updates automatically if they have been committed.

## ▶️ Customization

If you want to change the specific regions generated, the update schedule, or the script logic:

1.  **Fork** this repository.
2.  Modify the `regions` lists within the `generate_playlists.py` script.
3.  Adjust the `cron` schedule in `.github/workflows/generate_playlists.yml`.
4.  Make any other desired changes to the Python script.
5.  Ensure GitHub Actions are enabled on your fork.

## ▶️ Disclaimer

*   This repository merely aggregates publicly available channel information and stream URLs from the upstream sources mentioned.
*   The availability, legality, and stability of the streams themselves depend entirely on the original service providers and the upstream data sources. Streams may stop working, change format, or be removed without notice.
*   Ensure your use of these streams complies with the terms of service of the respective platforms and any applicable laws in your region.
*   The EPG data is also provided by the upstream sources and its accuracy is not guaranteed.

