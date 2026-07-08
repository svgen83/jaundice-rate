import aiohttp
import asyncio
import pymorphy3
from adapters.inosmi_ru import sanitize
from operator import itemgetter
from text_tools import split_by_words, calculate_jaundice_rate, load_charged_words


morph = pymorphy3.MorphAnalyzer()

TEST_ARTICLES = [
    'https://inosmi.ru/20260629/ormuz-279091044.html',
    'https://inosmi.ru/20260708/polsha-279211455.html',
    'https://inosmi.ru/20260708/evropa-279210264.html',
    'https://inosmi.ru/20260708/iran-279208960.html',
    'https://inosmi.ru/20260708/stubb-279208652.html',
]

async def fetch(session, url):
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def process_article(session, url, morph, charged_words):
    try:
        html = await fetch(session, url)
        html_sanitized = sanitize(html)
        article_words = split_by_words(morph, html_sanitized)
        total_words = len(article_words)
        rating = calculate_jaundice_rate(article_words, charged_words)
        return {
            "url": url,
            "total_words": total_words,
            "rating": rating,
        }
    except Exception as e:
        return {
            "url": url,
            "error": str(e),
            "total_words": 0,
            "rating": 0.0,
        }

def sort_by_rating(results):

    return sorted(results, key=itemgetter('rating'), reverse=True)


async def main():
    charged_words = load_charged_words("charged_dict")
    print(f"Загружено {len(charged_words)} заряженных слов.\n")

    async with aiohttp.ClientSession() as session:
        tasks = []
        for url in TEST_ARTICLES:
            task = process_article(session, url, morph, charged_words)
            tasks.append(task)

        results = await asyncio.gather(*tasks)

    sorted_results = sort_by_rating(results)

    print("Сравнение статей по рейтингу желтушности:")
    print("-" * 80)
    for idx, res in enumerate(sorted_results, start=1):
        if "error" in res:
            print(f"{idx}. {res['url']} -> ОШИБКА: {res['error']}")
        else:
            print(f"{idx}. {res['url']}")
            print(f"Слов: {res['total_words']}, Рейтинг: {res['rating']}%")
    print("-" * 80)


asyncio.run(main())
