import os
import asyncio
import json
import random
from datetime import datetime, timezone
from playwright.async_api import async_playwright

CHANNELS_FILE = "channels.json"
JSON_FILE = "playlist.json"
M3U_FILE = "playlist.m3u"

BASE_URL = os.getenv("STREAM_URL", "https://example.com/")  # set your base if env absent

# Allowed referrers (the two sites you mentioned)
ALLOWED_REFERRERS = [
    "https://streamcrichd.com/",
    "https://crichdi.com/"
]

PROJECT_INFO = {
    "name": "CricHD Channels Playlist",
    "description": "Automatically generated CricHD playlist channels",
    "version": "1.0.0",
    "developer": "@sultanarabi 161 —  credit: Toufik bro@",
    "country": "Bangladesh"
}

# limit concurrency to avoid launching too many browsers at once
CONCURRENCY = 4
semaphore = asyncio.Semaphore(CONCURRENCY)

async def fetch_channel(ch, playwright):
    # pick a referer randomly from allowed list
    referer = random.choice(ALLOWED_REFERRERS)
    # prepare an origin (strip trailing slash)
    origin = referer.rstrip("/")

    # keep a per-call browser context (cheaper than launching browser each time if you reuse browser)
    async with semaphore:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            extra_http_headers={
                "referer": referer,
                "origin": origin,
            },
            bypass_csp=True
        )
        page = await context.new_page()

        m3u8_url = None

        async def log_response(response):
            nonlocal m3u8_url
            try:
                url = response.url
                # adjust condition to match your target m3u8 pattern
                if ".m3u8" in url and "md5=" in url and "expires=" in url:
                    m3u8_url = url
            except Exception:
                pass

        page.on("response", log_response)

        try:
            target = f"{BASE_URL}{ch.get('code', '')}.php"
            # pass referer explicitly to navigation as well
            await page.goto(target, timeout=60000, referer=referer)
            # try to trigger playback (some players only generate m3u8 after play)
            try:
                await page.wait_for_selector("video", timeout=5000)
                await page.evaluate("() => { const v=document.querySelector('video'); if(v) v.play(); }")
            except Exception:
                # if no <video> or can't play, ignore
                pass

            # give some time for network responses to appear
            await page.wait_for_timeout(5000)

        except Exception as e:
            # keep going — return whatever we captured
            # optionally log e to file or stdout
            # print(f"Error loading {ch.get('name')}: {e}")
            pass
        finally:
            await context.close()
            await browser.close()

        return {
            "tvg-id": ch.get("tvg-id", ""),
            "tvg-logo": ch.get("tvg-logo", ""),
            "name": ch.get("name", ""),
            "url": m3u8_url
        }


async def main():
    # load channels file
    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        channels = json.load(f)

    async with async_playwright() as p:
        # prepare tasks using the same playwright handle
        tasks = [fetch_channel(ch, p) for ch in channels]
        result = await asyncio.gather(*tasks)

    current_time = datetime.now(timezone.utc)
    current_time_bd = current_time.strftime("%Y-%m-%d %H:%M:%S %Z")

    data = {
        "metadata": {
            "name": PROJECT_INFO["name"],
            "description": PROJECT_INFO["description"],
            "version": PROJECT_INFO["version"],
            "developer": PROJECT_INFO["developer"],
            "country": PROJECT_INFO["country"],
            "last_update_utc": current_time.isoformat(),
            "last_update_bd": current_time_bd,
            "total_channels": len([ch for ch in result if ch.get("url")])
        },
        "channels": result
    }

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # build m3u
    m3u_content = "#EXTM3U\n"
    m3u_content += f"#PLAYLIST: {PROJECT_INFO['name']}\n"
    m3u_content += f"#DESCRIPTION: {PROJECT_INFO['description']}\n"
    m3u_content += f"#VERSION: {PROJECT_INFO['version']}\n"
    m3u_content += f"#DEVELOPER: {PROJECT_INFO['developer']}\n"
    m3u_content += f"#COUNTRY: {PROJECT_INFO['country']}\n"
    m3u_content += f"#LAST-UPDATE-UTC: {current_time.isoformat()}\n"
    m3u_content += f"#LAST-UPDATE-BD: {current_time_bd}\n"
    m3u_content += f"#TOTAL-CHANNELS: {len([ch for ch in result if ch.get('url')])}\n\n"

    for ch in result:
        if ch.get("url"):
            m3u_content += (
                f'#EXTINF:-1 tvg-id="{ch["tvg-id"]}" tvg-logo="{ch["tvg-logo"]}", {ch["name"]}\n'
            )
            m3u_content += f'{ch["url"]}\n'

    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write(m3u_content)

    print("✅ JSON and M3U updated successfully")
    print(f"📊 Total channels found: {len([ch for ch in result if ch.get('url')])}")
    print(f"🕐 Last update: {current_time_bd}")


if __name__ == "__main__":
    asyncio.run(main())
