# --- Configuration & Setup ---
DB_PATH = "expenses.db"
# If a category has no specific limit, you can set it to 0 or None
CATEGORY_CONFIG = {
    "Transporte": 150000,
    "Vivienda": 1200000,
    "Ocio" : 400000,
    "Salud" : 300000,
    "Ropa" : 300000,
    "Misceláneo": 1000000,
    "Departamento" : 700000,
    "Ahorro": 0,
    "Vacaciones": 0
      
}

ALLOCATION_PCT = {
    "Transporte": 0.05,  
    "Vivienda": 0.28,     
    "Ocio": 0.09,
    "Salud": 0.02,
    "Ropa" : 0.02,
    "Misceláneo": 0.24,
    "Departamento": 0.05,
    "Ahorro": 0.20,
    "Vacaciones": 0.05
}

def get_categories():
    return list(CATEGORY_CONFIG.keys())

def get_limit(category_name):
    return CATEGORY_CONFIG.get(category_name, 0)
