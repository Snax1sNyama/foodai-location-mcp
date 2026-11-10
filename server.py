import os
import httpx
from fastmcp import FastMCP
from typing import List, Dict, Any

# ✅ Инициализация сервера (эта строка, скорее всего, потерялась)
mcp = FastMCP("FoodAI-Location")

TWOGIS_API_KEY = os.getenv("TWO_GIS_API_KEY")
TWOGIS_PLACES_URL = "https://catalog.api.2gis.com/3.0/items"

@mcp.tool()
async def find_restaurants(latitude: float, longitude: float, budget: int) -> List[Dict[str, Any]]:
    """
    Находит рестораны и кафе в радиусе 1000 метров, сортируя их по расстоянию.
    """
    point = f"{longitude},{latitude}"

    params = {
        "q": "еда",          # Упростили запрос
        "point": point,
        "radius": 1000,
        "key": TWOGIS_API_KEY,
        "fields": "items.point,items.address_name,items.rubrics",
        "page_size": 10
    }

    try:
        async with httpx.AsyncClient() as client:
            # Увеличили таймаут до 20 секунд
            response = await client.get(TWOGIS_PLACES_URL, params=params, timeout=20.0)
            data = response.json()

            if data.get("meta", {}).get("code") != 200:
                error_msg = data.get("meta", {}).get("error", {}).get("message", "Неизвестная ошибка 2GIS")
                print(f"Ошибка 2GIS: {error_msg}")
                return []

    except Exception as e:
        print(f"Ошибка сети: {e}")
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
    """Строит маршрут между двумя точками через OSRM."""
    url = f"http://router.project-osrm.org/route/v1/{mode}/{start_lon},{start_lat};{end_lon},{end_lat}?overview=false"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            data = response.json()
            if data.get("code") != "Ok":
                return {"error": "Не удалось построить маршрут"}
            route = data["routes"][0]
            return {"distance_km": round(route["distance"] / 1000, 2), "duration_min": round(route["duration"] / 60, 1), "mode": mode}
    except Exception as e:
        return {"error": f"Ошибка маршрутов: {e}"}

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
