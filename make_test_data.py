"""ПР1. Создаёт тестовые данные отделов гостиницы."""

import random
from pathlib import Path

root = Path("company_data")
# Вариант 16: три отдела, по четыре файла в каждом.
for dept in ["reception", "rooms", "restaurant"]:
    (root / dept).mkdir(parents=True, exist_ok=True)
    for i in range(1, 5):
        lines = [
            f"{dept};doc{i};{random.randint(1000, 99999)}"
            for _ in range(200)
        ]
        (root / dept / f"report_{i}.csv").write_text(
            "\n".join(lines), encoding="utf-8"
        )

print("Тестовые данные созданы в папке company_data/")
print("Отделов: 3, файлов в каждом: 4, всего файлов: 12")
