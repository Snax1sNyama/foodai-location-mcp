import os
import httpx
from fastmcp import FastMCP
from typing import List, Dict, Any

mcp = FastMCP("FoodAI-Location")

TWOGIS_API_KEY = os.getenv("TWO_GIS_API_KEY")
# Переходим на endpoint /3.0/markers, который отлично работает с сортировкой по расстоянию
TWOGIS_MARKERS_URL = "https://catalog.api.2gis.com/3.0/markers"

@mcp.tool()
async def find_restaurants(latitude: float, longitude: float, budget: int) -> List[Dict[str, Any]]:
    """
    Находит рестораны и кафе в радиусе 1000 метров, сортируя их по реальному расстоянию.
    """
    point = f"{longitude},{latitude}"
    
    # 🚀 ГЛАВНЫЕ ИЗМЕНЕНИЯ ЗДЕСЬ:
    params = {
        "q": "ресторан кафе",          # Текстовый поиск
        "point": point,                # Точка для поиска в радиусе
        "radius": 1000,                # Радиус 1 км
        "location": point,             # Точка отсчета для сортировки
        "sort": "distance",            # Сортируем по возрастанию расстояния
        "key": TWOGIS_API_KEY,
        "fields": "items.point,items.address_name,items.rubrics",
        "page_size": 10                # Максимум 10 для демо-ключа
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(TWOGIS_MARKERS_URL, params=params, timeout=10.0)
            data = response.json()

            if data.get("meta", {}).get("code") != 200:
                error_msg = data.get("meta", {}).get("error", {}).get("message", "Неизвестная ошибка 2GIS")
                return [{"status": "error", "message": f"2GIS API вернул ошибку: {error_msg}"}]

    except Exception as e:
        return [{"status": "error", "message": f"Ошибка сети: {e}"}]

    if "result" not in data or "items" not in data["result"]:
        return [{"status": "error", "message": "2GIS вернул пустой список."}]

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

# Функция get_route остается без изменений
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
