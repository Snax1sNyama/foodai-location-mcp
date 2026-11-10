import os
import httpx
from fastmcp import FastMCP
from typing import List, Dict, Any

mcp = FastMCP("FoodAI-Location")

TWOGIS_API_KEY = os.getenv("TWO_GIS_API_KEY")
TWOGIS_PLACES_URL = "https://catalog.api.2gis.com/3.0/items"

@mcp.tool()
async def find_restaurants(latitude: float, longitude: float, budget: int) -> List[Dict[str, Any]]:
    point = f"{longitude},{latitude}"

    params = {
        # 👇 МАГИЯ ЗДЕСЬ: Ищем по всем категориям общепита одновременно
        "rubric_id": "161,162,164,165", 
        "point": point,
        "radius": 2000,          # Радиус 2 км, чтобы захватить больше мест
        "type": "branch",        # Ищем только организации (не здания)
        "key": TWOGIS_API_KEY,
        "fields": "items.point,items.address_name,items.rubrics",
        "page_size": 50          # Берем до 50 результатов (максимум для 2ГИС)
    }

    try:
        async with httpx.AsyncClient() as client:
            # Даем 15 секунд на ответ
            response = await client.get(TWOGIS_PLACES_URL, params=params, timeout=15.0) 
            data = response.json()

            if data.get("meta", {}).get("code") != 200:
                print(f"Ошибка 2GIS: {data.get('meta', {}).get('error', {}).get('message')}")
                return []

    except Exception as e:
        print(f"Сетевая ошибка: {e}")
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
            return {"distance_km": round(route["distance"] / 1000, 2), "duration_min": round(route["duration"] / 60, 1), "mode": mode}
    except Exception as e:
        return {"error": f"Ошибка маршрутов: {e}"}

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
