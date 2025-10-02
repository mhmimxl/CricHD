import os
import asyncio
import json
from datetime import datetime, timezone
from playwright.async_api import async_playwright

CHANNELS_FILE = "channels.json"
JSON_FILE = "playlist.json"
M3U_FILE = "playlist.m3u"

BASE_URL = os.getenv("STREAM_URL")

# Metadata for comments
PROJECT_INFO = {
    "name": "CricHD Channels Playlist",
    "description": "Automatically generated CricHD playlist channels",
    "version": "1.0.0",
    "developer": "@sultanarabi 161 —  credit: Toufik bro@",
    "country": "Bangladesh"
}

async def fetch_channel(ch):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        m3u8_url = None

        async def log_response(response):
            nonlocal m3u8_url
            url = response.url
            if ".m3u8" in url and "md5=" in url and "expires=" in url:
                m3u8_url = url

        page.on("response", log_response)

        
        await page.goto(f"{BASE_URL}{ch['code']}.php", timeout=60000)

        try:
            await page.wait_for_selector("video", timeout=5000)
            await page.evaluate("() => { const v=document.querySelector('video'); if(v)v.play(); }")
        except:
            pass

        await page.wait_for_timeout(5000)
        await browser.close()
        return {
            "tvg-id": ch["tvg-id"],
            "tvg-logo": ch["tvg-logo"],
            "name": ch["name"],
            "url": m3u8_url
        }

async def main():
    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        channels = json.load(f)

    tasks = [fetch_channel(ch) for ch in channels]
    result = await asyncio.gather(*tasks)

    current_time = datetime.now(timezone.utc)
    current_time_bd = current_time.strftime("%Y-%m-%d %H:%M:%S %Z")

    # JSON save with comments/metadata
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

    # M3U save with comments
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
            m3u_content += f'#EXTINF:-1 tvg-id="{ch["tvg-id"]}" tvg-logo="{ch["tvg-logo"]}", {ch["name"]}\n'
            m3u_content += f'{ch["url"]}\n'

    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write(m3u_content)

    print("✅ JSON and M3U updated successfully")
    print(f"📊 Total channels found: {len([ch for ch in result if ch.get('url')])}")
    print(f"🕐 Last update: {current_time_bd}")

if __name__ == "__main__":
    asyncio.run(main())
