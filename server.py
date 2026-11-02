"""
Async REST API Backend for A2 TV App.
Powered by aiohttp.web with CORS support and JSON endpoints.
"""

import json
from aiohttp import web
from config import API_HOST, API_PORT, APP_PACKAGE, CURRENT_APP_VERSION_CODE
from database import db

# CORS Middleware to allow requests from Android WebView
@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        response = web.Response(status=200)
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex
        except Exception as e:
            response = web.json_response({
                "status": "error",
                "message": str(e)
            }, status=500)

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    return response

# Routes Handlers
async def handle_root(request):
    return web.json_response({
        "status": "online",
        "service": "A2 TV Backend API & Telegram Bot",
        "version": "2.0.0",
        "package": APP_PACKAGE,
        "endpoints": {
            "app_config": "/api/app-config",
            "channels": "/api/channels",
            "categories": "/api/categories",
            "maintenance": "/api/maintenance",
            "update": "/api/update",
            "channel_apis": "/api/channel-apis"
        }
    })

async def handle_app_config(request):
    """Returns combined app configuration (maintenance, update, and channels overview)."""
    maintenance = db.get_maintenance()
    update_info = db.get_app_update()
    channels = db.get_channels()
    categories = db.get_categories()
    apis = db.get_channel_apis()

    return web.json_response({
        "status": "success",
        "package": APP_PACKAGE,
        "maintenance": maintenance,
        "update": update_info,
        "counts": {
            "channels": len(channels),
            "categories": len(categories),
            "apis": len(apis)
        }
    })

async def handle_categories(request):
    """Returns channel categories."""
    categories = db.get_categories()
    return web.json_response({
        "status": "success",
        "count": len(categories),
        "categories": categories
    })

async def handle_channels(request):
    """Returns all channels or filtered by category."""
    category = request.query.get("category", None)
    channels = db.get_channels(category)
    return web.json_response({
        "status": "success",
        "filter": category or "all",
        "count": len(channels),
        "channels": channels
    })

async def handle_maintenance(request):
    """Returns maintenance status."""
    maintenance = db.get_maintenance()
    return web.json_response({
        "status": "success",
        "maintenance": maintenance
    })

async def handle_update(request):
    """Checks if there is a new update available for the app."""
    update_info = db.get_app_update()
    try:
        current_v = int(request.query.get("current_version", CURRENT_APP_VERSION_CODE))
    except (ValueError, TypeError):
        current_v = CURRENT_APP_VERSION_CODE

    has_update = update_info.get("enabled", False) and (update_info.get("version_code", 0) > current_v)

    return web.json_response({
        "status": "success",
        "current_version": current_v,
        "has_update": has_update,
        "update": update_info
    })

async def handle_channel_apis(request):
    """Returns list of active channel APIs."""
    apis = db.get_channel_apis()
    return web.json_response({
        "status": "success",
        "count": len(apis),
        "apis": apis
    })

def make_app():
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/", handle_root)
    app.router.add_get("/api/app-config", handle_app_config)
    app.router.add_get("/api/categories", handle_categories)
    app.router.add_get("/api/channels", handle_channels)
    app.router.add_get("/api/maintenance", handle_maintenance)
    app.router.add_get("/api/update", handle_update)
    app.router.add_get("/api/channel-apis", handle_channel_apis)
    return app

def run_server(host=API_HOST, port=API_PORT, handle_signals=False):
    app = make_app()
    web.run_app(app, host=host, port=port, handle_signals=handle_signals, print=print)

if __name__ == "__main__":
    run_server(handle_signals=True)
