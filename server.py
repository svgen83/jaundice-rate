from aiohttp import web
import asyncio

async def handle(request):

    urls_param = request.query.get('urls')
    
    if urls_param is None:
        return web.json_response(
            {'error': 'Missing "urls" parameter'},
            status=400  # Bad Request
        )
    
    url_list = [url.strip() for url in urls_param.split(',') if url.strip()]
    
    return web.json_response({'urls': url_list})


app = web.Application()

app.router.add_get('/', handle)

# Запускаем сервер
if __name__ == '__main__':
    web.run_app(app, host='127.0.0.1', port=8080)
