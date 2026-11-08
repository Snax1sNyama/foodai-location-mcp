import httpx
import math
from fastmcp import FastMCP
from typing import List, Dict, Any, Optional

mcp = FastMCP("FoodAI-Location")

# 1. Пул из нескольких проверенных зеркал Overpass API
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",           # Основной (часто падает)
    "https://overpass.kumi.systems/api/interpreter",     # Немецкое зеркало
    "https://overpass.openstreetmap.ru/api/interpreter", # Российское зеркало
]

# Обязательно указываем User-Agent, иначе Overpass может заблокировать
HEADERS = {"User-Agent": "FoodAI-MCP-Server/1.0 (student_project)"}

# Функция для расчета расстояния между двумя точками на Земле (в метрах)
def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000  # Радиус Земли в метрах
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# Вспомогательная функция для запроса к одному эндпоинту
async def _fetch_from_overpass(endpoint: str, query: str, client: httpx.AsyncClient) -> Optional[dict]:
    try:
        # Уменьшаем таймаут до 7 секунд. Если сервер тупит, мы не ждем его вечно.
        response = await client.post(endpoint, data={'data': query}, headers=HEADERS, timeout=7.0)
        
        # Если сервер перегружен или упал, возвращаем None, чтобы попробовать следующее зеркало
        if response.status_code in [429, 500, 502, 503, 504]:
            print(f"Сервер {endpoint} вернул ошибку {response.status_code}. Переключаюсь...")
            return None
            
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        print(f"Сервер {endpoint} не ответил за 7 секунд. Переключаюсь...")
        return None
    except Exception as e:
        print(f"Сетевая ошибка при запросе к {endpoint}: {e}")
        return None

@mcp.tool()
async def find_restaurants(latitude: float, longitude: float, budget: int) -> List[Dict[str, Any]]:
    """
    Находит рестораны и фастфуд в радиусе 500 метров, используя пул зеркал Overpass API.
    Сортирует по удаленности.
    """
    
    # Overpass QL запрос: ищем рестораны и фастфуд. Внутренний таймаут ставим 10 сек.
    overpass_query = f"""
    [out:json][timeout:10];
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
            print(f"Пробую подключиться к {endpoint}...")
            data = await _fetch_from_overpass(endpoint, overpass_query, client)
            if data is not None:
                print(f"Успешный ответ от {endpoint}")
                break # Выходим из цикла, если получили данные
        
        if data is None:
            return [{"status": "error", "message": "Все серверы Overpass API временно недоступны. Пожалуйста, попробуйте позже."}]

    restaurants = []
    
    # Обработка полученных данных
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        name = tags.get("name") or tags.get("brand")
        
        # Пропускаем места без названия
        if not name:
            continue
            
        # Извлекаем координаты
        lat = element.get("lat") or element.get("center", {}).get("lat")
        lon = element.get("lon") or element.get("center", {}).get("lon")
        
        if not lat or not lon:
            continue

        # Считаем реальное расстояние в метрах
        distance_meters = haversine_distance(latitude, longitude, lat, lon)
        # Примерное время ходьбы (средняя скорость 80 м/мин)
        distance_minutes = round(distance_meters / 80)

        # Тип кухни
        cuisine = tags.get("cuisine", "fast_food")
        
        # Заглушка для минимальной цены (так как в OSM нет цен)
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
        return [{"status": "error", "message": "В радиусе 500 метров не найдено подходящих ресторанов."}]

    # Сортируем по расстоянию (от ближайших к дальним) и отдаем топ-5
    restaurants.sort(key=lambda x: x["distance_meters"])
    
    return restaurants[:5]
