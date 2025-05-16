import random
import openpyxl
from openpyxl.utils import get_column_letter

first_names = ['Alice', 'Bob', 'Carol', 'Dave', 'Eve', 'Frank', 'Grace']
last_names = ['Smith', 'Johnson', 'Lee', 'Brown', 'Davis', 'Clark', 'White']

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Random Names"

# Headers
ws.append(['First Name', 'Last Name', 'Full Name'])

for _ in range(7):  # 7 rows
    first = random.choice(first_names)
    last = random.choice(last_names)
    full = f"{first} {last}"
    ws.append([first, last, full])

filename = "Random_Names.xlsx"
wb.save(filename)
print(f"Created {filename}")
