import httpx
import math
from fastmcp import FastMCP
from typing import List, Dict, Any, Optional

mcp = FastMCP("FoodAI-Location")

# Пул из нескольких зеркал Overpass API
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

HEADERS = {"User-Agent": "FoodAI-MCP-Server/1.0 (student_project)"}

# Функция для расчета расстояния (формула Haversine)
def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000  # Радиус Земли в метрах
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

async def _fetch_from_overpass(endpoint: str, query: str, client: httpx.AsyncClient) -> Optional[dict]:
    """Вспомогательная функция для запроса к одному эндпоинту."""
    try:
        # 🚀 Уменьшили таймаут до 3 секунд. Если сервер тупит, сразу идем к следующему.
        response = await client.post(endpoint, data={'data': query}, headers=HEADERS, timeout=3.0)
        
        if response.status_code in [429, 500, 502, 503, 504, 403]:
            print(f"Сервер {endpoint} вернул ошибку {response.status_code}. Переключаюсь...")
            return None
            
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        print(f"Сервер {endpoint} не ответил за 3 секунды. Переключаюсь...")
        return None
    except Exception as e:
        print(f"Ошибка при запросе к {endpoint}: {e}")
        return None

@mcp.tool()
async def find_restaurants(latitude: float, longitude: float, budget: int) -> List[Dict[str, Any]]:
    """
    Находит рестораны и фастфуд в радиусе 300 метров, используя пул зеркал Overpass API.
    """
    
    # 🚀 Оптимизировали запрос: уменьшили таймаут до 5 сек, радиус до 300 метров, лимит выдачи до 10.
    overpass_query = f"""
    [out:json][timeout:5];
    (
      node["amenity"~"restaurant|fast_food"](around:300,{latitude},{longitude});
      way["amenity"~"restaurant|fast_food"](around:300,{latitude},{longitude});
    );
    out center 10;
    """

    data = None
    
    # Перебираем зеркала
    async with httpx.AsyncClient() as client:
        for endpoint in OVERPASS_ENDPOINTS:
            print(f"Пробую подключиться к {endpoint}...")
            data = await _fetch_from_overpass(endpoint, overpass_query, client)
            if data is not None:
                print(f"Успешный ответ от {endpoint}")
                break
        
        # 🛡 FALLBACK (Защита от падения API)
        if data is None:
            print("Все серверы Overpass API недоступны! Использую резервные (тестовые) данные.")
            return [
                {"name": "Вкусно и точка (Fallback)", "distance_meters": 150, "distance_min": 2, "cuisine": "burger", "min_price_estimate": 150, "lat": latitude, "lon": longitude},
                {"name": "KFC (Fallback)", "distance_meters": 300, "distance_min": 4, "cuisine": "chicken", "min_price_estimate": 200, "lat": latitude, "lon": longitude},
                {"name": "Burger King (Fallback)", "distance_meters": 450, "distance_min": 6, "cuisine": "burger", "min_price_estimate": 250, "lat": latitude, "lon": longitude}
            ]

    restaurants = []
    
    # Обрабатываем реальные данные
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        name = tags.get("name") or tags.get("brand")
        
        if not name:
            continue
            
        lat = element.get("lat") or element.get("center", {}).get("lat")
        lon = element.get("lon") or element.get("center", {}).get("lon")
        
        if not lat or not lon:
            continue

        distance_meters = haversine_distance(latitude, longitude, lat, lon)
        distance_minutes = round(distance_meters / 80)

        cuisine = tags.get("cuisine", "fast_food")
        min_price = 150 
        
        if min_price <= budget:
            restaurants.append({
                "name": name,
                "distance_meters": round(distance_meters),
                "distance_min": distance_minutes,
                "cuisine": cuisine,
                "min_price_estimate": min_price,
                "lat": lat,
                "lon": lon
            })

    if not restaurants:
        return [{"status": "error", "message": "В радиусе 300 метров не найдено подходящих ресторанов."}]

    restaurants.sort(key=lambda x: x["distance_meters"])
    
    return restaurants[:5]
