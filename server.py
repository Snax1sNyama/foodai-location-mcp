import os
import httpx
from fastmcp import FastMCP
from typing import List, Dict, Any

mcp = FastMCP("FoodAI-Location")

TWOGIS_API_KEY = os.getenv("TWO_GIS_API_KEY")
# Если у тебя работает Cloudflare Worker, раскомментируй строку ниже и закомментируй следующую
# TWOGIS_PLACES_URL = "https://twogis-proxy.zherdevdenis25.workers.dev/3.0/items"
TWOGIS_PLACES_URL = "https://catalog.api.2gis.com/3.0/items"

@mcp.tool()
async def find_restaurants(latitude: float, longitude: float, budget: int) -> List[Dict[str, Any]]:
    """
    Находит еду в радиусе 1000 метров.
    """
    point = f"{longitude},{latitude}"

    params = {
        "q": "ресторан фастфуд",  # 👈 Вернули точный запрос
        "point": point,
        "radius": 1000,           # 👈 Вернули адекватный радиус
        "key": TWOGIS_API_KEY,
        "fields": "items.point,items.address_name,items.rubrics",
        "page_size": 10
    }

    try:
        async with httpx.AsyncClient() as client:
            # 👈 СТАВИМ ЖЕСТКИЙ ТАЙМАУТ 5 СЕКУНД
            response = await client.get(TWOGIS_PLACES_URL, params=params, timeout=10.0) 
            data = response.json()

            if data.get("meta", {}).get("code") != 200:
                error_msg = data.get("meta", {}).get("error", {}).get("message", "Неизвестная ошибка")
                print(f"Ошибка 2GIS API: {error_msg}")
                return []

    except httpx.TimeoutException:
        print("2GIS не ответил за 5 секунд. Сдаемся.")
        return []
    except Exception as e:
        print(f"Сетевая ошибка при запросе к 2GIS: {e}")
        return []

    if "result" not in data or "items" not in data["result"]:
        print("2GIS вернул пустой список.")
        return []

    restaurants = []
    for item in data["result"]["items"]:
        name = item.get("name")
        address = item.get("address_name", "Адрес не указан")
        
        point_data = item.get("point", {})
        lat = point_data.get("lat")
        lon = point_data.get("lon")
        
        rubrics = item.get("rubrics", [])
        cuisine = rubrics[0].get("name", "Заведение") if rubrics else "Заведение"

        if name and lat and lon:
            restaurants.append({
                "name": name,
                "address": address,
                "lat": lat,
                "lon": lon,
                "cuisine": cuisine,
            })

    return restaurants


@mcp.tool()
async def get_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float, mode: str = "driving") -> Dict[str, Any]:
    url = f"http://router.project-osrm.org/route/v1/{mode}/{start_lon},{start_lat};{end_lon},{end_lat}?overview=false"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            data = response.json()
            if data.get("code") != "Ok":
                return {"error": "Не удалось построить маршрут"}
            route = data["routes"][0]
            return {
                "distance_km": round(route["distance"] / 1000, 2),
                "duration_min": round(route["duration"] / 60, 1),
                "mode": mode
            }
    except Exception as e:
        return {"error": f"Ошибка сервиса маршрутов: {e}"}

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
