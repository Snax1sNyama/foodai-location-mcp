from fastmcp import FastMCP
from typing import List, Dict, Any

# Для FastMCP Cloud мы НЕ указываем host, port и пути.
# Платформа сама настроит сеть. Главное - имя переменной mcp.
mcp = FastMCP("FoodAI-Location")

@mcp.tool()
def find_restaurants(latitude: float, longitude: float, budget: int) -> List[Dict[str, Any]]:
    """
    Находит рестораны быстрого питания в радиусе 5 минут ходьбы.
    Принимает широту, долготу и бюджет пользователя.
    """
    # Для прототипа (КП2) возвращаем тестовые данные.
    mock_db = [
        {"name": "Вкусно и точка", "distance_min": 3, "min_price": 150,
         "coords": [latitude + 0.001, longitude + 0.001]},
        {"name": "KFC", "distance_min": 5, "min_price": 200, "coords": [latitude - 0.001, longitude + 0.002]},
        {"name": "Burger King", "distance_min": 7, "min_price": 250, "coords": [latitude + 0.002, longitude - 0.001]}
    ]

    # Фильтруем по бюджету и расстоянию (<= 5 минут)
    valid_restaurants = [
        r for r in mock_db
        if r["min_price"] <= budget and r["distance_min"] <= 5
    ]

    if not valid_restaurants:
        return [{"status": "error", "message": "Нет подходящих ресторанов в радиусе 5 минут с таким бюджетом."}]

    return valid_restaurants

# Этот блок нужен только если ты запускаешь его локально.
# FastMCP Cloud его проигнорирует.
if __name__ == "__main__":
    mcp.run(transport="streamable-http")