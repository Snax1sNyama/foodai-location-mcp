import httpx
import math
from fastmcp import FastMCP
from typing import List, Dict, Any

mcp = FastMCP("FoodAI-Location")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
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

@mcp.tool()
async def find_restaurants(latitude: float, longitude: float, budget: int) -> List[Dict[str, Any]]:
    """
    Находит рестораны и фастфуд в радиусе 500 метров (около 5-7 минут ходьбы),
    используя Overpass API (OpenStreetMap). Сортирует по удаленности.
    """
    
    # Ищем рестораны (amenity=restaurant) и фастфуд (amenity=fast_food)
    # Выводим не более 15 результатов, чтобы не перегружать ответ
    overpass_query = f"""
    [out:json][timeout:25];
    (
      node["amenity"~"restaurant|fast_food"](around:500,{latitude},{longitude});
      way["amenity"~"restaurant|fast_food"](around:500,{latitude},{longitude});
    );
    out center 15;
    """

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(OVERPASS_URL, data={'data': overpass_query}, headers=HEADERS, timeout=30.0)
            
            # Обработка перегрузки сервера Overpass
            if response.status_code == 429:
                return [{"status": "error", "message": "Сервер OpenStreetMap перегружен. Попробуйте позже."}]
                
            response.raise_for_status()
            data = response.json()
            
    except httpx.RequestError as e:
        return [{"status": "error", "message": f"Ошибка сети: {e}"}]
    except Exception as e:
        return [{"status": "error", "message": f"Системная ошибка: {e}"}]

    restaurants = []
    
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

        # Тип кухни (если указан в OSM)
        cuisine = tags.get("cuisine", "fast_food")
        
        # --- ОГРАНИЧЕНИЕ БЮДЖЕТА ---
        # В OSM нет цен. Мы предполагаем, что если бюджет пользователя < 150 руб., 
        # то это может быть проблемой для полноценного обеда. 
        # Оставляем заглушку min_price = 150, чтобы фильтр работал.
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
