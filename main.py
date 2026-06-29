import aiohttp
import asyncio
from adapters.inosmi_ru import sanitize


async def fetch(session, url):
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def main():
    async with aiohttp.ClientSession() as session:
        #html = await fetch(session, 'http://example.com')
        html = await fetch(session, 'https://inosmi.ru/20260629/ormuz-279091044.html')
        html_sanitized = sanitize(html)
        print(html_sanitized)


asyncio.run(main())
