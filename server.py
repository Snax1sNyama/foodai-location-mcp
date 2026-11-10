@mcp.tool()
async def find_restaurants(latitude: float, longitude: float, budget: int) -> List[Dict[str, Any]]:
    """
    Находит рестораны и кафе в радиусе 1000 метров, сортируя их по расстоянию.
    """
    point = f"{longitude},{latitude}"

    params = {
        "q": "ресторан",          # 👈 Упростили запрос, как в тесте
        "point": point,
        "radius": 1000,
        "key": TWOGIS_API_KEY,
        "fields": "items.point,items.address_name,items.rubrics",
        "page_size": 10
    }

    try:
        async with httpx.AsyncClient() as client:
            # 👈 Увеличили таймаут до 20 секунд, чтобы 2ГИС успел подумать
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
