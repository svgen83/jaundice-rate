import aiohttp
import asyncio
import pymorphy3
from adapters.inosmi_ru import sanitize
from text_tools import split_by_words, calculate_jaundice_rate


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
        article_words = split_by_words(morph, html_sanitized)
        rank = calculate_jaundice_rate(article_words, ['пролив', 'юридический'])
        print(rank)

morph = pymorphy3.MorphAnalyzer()
asyncio.run(main())
