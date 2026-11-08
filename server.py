import httpx
import math
import asyncio
from fastmcp import FastMCP
from typing import List, Dict, Any, Optional

mcp = FastMCP("FoodAI-Location")

# 1. Создаем пул из нескольких проверенных зеркал Overpass API
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",          # Основной (часто падает, но пробуем первым)
    "https://overpass.kumi.systems/api/interpreter",    # Немецкое зеркало (очень стабильное)
    "https://overpass.openstreetmap.ru/api/interpreter",# Российское зеркало
]

HEADERS = {"User-Agent": "FoodAI-MCP-Server/1.0 (student_project)"}

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

async def _fetch_from_overpass(endpoint: str, query: str, client: httpx.AsyncClient) -> Optional[dict]:
    """Вспомогательная функция для запроса к одному эндпоинту."""
    try:
        response = await client.post(endpoint, data={'data': query}, headers=HEADERS, timeout=30.0)
        # Если сервер перегружен (429) или упал (5xx), возвращаем None, чтобы попробовать следующее зеркало
        if response.status_code in [429, 500, 502, 503, 504]:
            print(f"Эндпоинт {endpoint} вернул ошибку {response.status_code}. Пробуем следующее зеркало...")
            return None
        response.raise_for_status()
        return response.json()
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        print(f"Сетевая ошибка при запросе к {endpoint}: {e}")
        return None

@mcp.tool()
async def find_restaurants(latitude: float, longitude: float, budget: int) -> List[Dict[str, Any]]:
    """
    Находит рестораны и фастфуд, используя пул зеркал Overpass API.
    """
    overpass_query = f"""
    [out:json][timeout:25];
    (
      node["amenity"~"restaurant|fast_food"](around:500,{latitude},{longitude});
      way["amenity"~"restaurant|fast_food"](around:500,{latitude},{longitude});
    );
    out center 15;
    """

    data = None
    # 2. Проходим по списку эндпоинтов, пока не получим успешный ответ
    async with httpx.AsyncClient() as client:
        for endpoint in OVERPASS_ENDPOINTS:
            data = await _fetch_from_overpass(endpoint, overpass_query, client)
            if data is not None:
                # Успех! Выходим из цикла.
                break
        
        if data is None:
            return [{"status": "error", "message": "Все серверы Overpass API временно недоступны. Пожалуйста, попробуйте позже."}]

    # ... (дальнейшая обработка data и формирование списка ресторанов остается без изменений)
    restaurants = []
    for element in data.get("elements", []):
        # (код обработки элемента такой же, как и раньше)
        tags = element.get("tags", {})
        name = tags.get("name") or tags.get("brand")
        if not name: continue
        lat = element.get("lat") or element.get("center", {}).get("lat")
        lon = element.get("lon") or element.get("center", {}).get("lon")
        if not lat or not lon: continue

        distance_meters = haversine_distance(latitude, longitude, lat, lon)
        distance_minutes = round(distance_meters / 80)
        cuisine = tags.get("cuisine", "fast_food")
        min_price = 150 
        
        if min_price <= budget:
            restaurants.append({
                "name": name, "distance_meters": round(distance_meters),
                "distance_min": distance_minutes, "cuisine": cuisine,
                "min_price_estimate": min_price, "lat": lat, "lon": lon
            })

    if not restaurants:
        return [{"status": "error", "message": "В радиусе 500 метров не найдено подходящих ресторанов."}]

    restaurants.sort(key=lambda x: x["distance_meters"])
    return restaurants[:5]
