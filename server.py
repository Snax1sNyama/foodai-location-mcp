import os
import httpx
from fastmcp import FastMCP
from typing import List, Dict, Any

mcp = FastMCP("FoodAI-Location")

# Подтягиваем ключ 2GIS из переменных окружения
TWOGIS_API_KEY = os.getenv("TWO_GIS_API_KEY")
TWOGIS_PLACES_URL = "https://catalog.api.2gis.com/3.0/items"

@mcp.tool()
async def find_restaurants(latitude: float, longitude: float, budget: int) -> List[Dict[str, Any]]:
    """
    Находит рестораны и фастфуд в радиусе 500 метров, используя 2GIS Places API.
    """
    # 2GIS ожидает координаты в формате lon,lat
    point = f"{longitude},{latitude}"
    
    params = {
        "q": "ресторан фастфуд кафе", # Поисковый запрос
        "point": point,
        "radius": 500,                # Радиус поиска в метрах
        "key": TWOGIS_API_KEY,
        "fields": "items.point,items.address_name,items.rubrics,items.contact_groups",
        "page_size": 10               # Берем топ-10 результатов
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(TWOGIS_PLACES_URL, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        return [{"status": "error", "message": f"Ошибка при запросе к 2GIS: {e}"}]

    # Проверяем, что 2GIS вернул результаты
    if "result" not in data or "items" not in data["result"]:
        return [{"status": "error", "message": "В радиусе 500 метров не найдено подходящих мест."}]

    restaurants = []
    for item in data["result"]["items"]:
        name = item.get("name")
        address = item.get("address_name", "Адрес не указан")
        
        # Достаем координаты
        point_data = item.get("point", {})
        lat = point_data.get("lat")
        lon = point_data.get("lon")
        
        # Достаем тип кухни (рубрики)
        rubrics = item.get("rubrics", [])
        cuisine = rubrics[0].get("name", "Заведение") if rubrics else "Заведение"

        if name and lat and lon:
            # Заглушка для цены (так как 2GIS не отдает меню)
            min_price_estimate = 150
            
            if min_price_estimate <= budget:
                restaurants.append({
                    "name": name,
                    "address": address,
                    "lat": lat,
                    "lon": lon,
                    "cuisine": cuisine,
                    "min_price_estimate": min_price_estimate
                })

    if not restaurants:
        return [{"status": "error", "message": "Найденные заведения не подходят под ваш бюджет."}]

    return restaurants

@mcp.tool()
async def get_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float, mode: str = "driving") -> Dict[str, Any]:
    """
    Строит маршрут между двумя точками, используя бесплатный OSRM.
    mode: "driving" (на машине), "foot" (пешком), "bike" (на велосипеде).
    """
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
