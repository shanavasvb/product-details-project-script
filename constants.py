import logging

# Logging Configuration
LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# API Configuration
DEFAULT_API_REQUEST_DELAY = 1.0
DEFAULT_MAX_RETRIES = 5
OPENFOODFACTS_BASE_URL = "https://world.openfoodfacts.org/api/v0/product/"
GOOGLE_SEARCH_API_URL = "https://www.googleapis.com/customsearch/v1"
DIGITEYES_API_URL = "https://www.digit-eyes.com/gtin/v2_0"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# File and Directory Names
OUTPUT_DIR = "output"
CACHE_DIR = "cache"
INVALID_BARCODES_FILE = "invalid_barcodes.json"
NOT_FOUND_BARCODES_FILE = "not_found_barcodes.json"
PROGRESS_FILE = "barcode_progress.pkl"
SINGLE_OUTPUT_FILE = "output.json"

# Barcode Validation
VALID_BARCODE_LENGTHS = [8, 12, 13, 14]

# AI Service Models
GEMINI_MODEL = "gemini-1.5-flash"
OPENAI_MODEL = "gpt-3.5-turbo"
DEEPSEEK_MODEL = "deepseek-chat"

# AI Request Parameters
AI_TEMPERATURE = 0.3
GEMINI_MAX_TOKENS = 800
OPENAI_MAX_TOKENS = 600
DEEPSEEK_MAX_TOKENS = 600

# Category Keywords for Product Classification
CATEGORY_KEYWORDS = {
    'Food & Beverages': ['food', 'snack', 'drink', 'beverage', 'tea', 'coffee', 'juice', 'water', 
                        'milk', 'oil', 'til', 'spice', 'ghee', 'flour', 'masala', 'biscuit'],
    'Personal Care': ['soap', 'shampoo', 'toothpaste', 'cream', 'lotion', 'gel', 'beauty', 
                     'face wash', 'body wash', 'deodorant', 'sanitizer'],
    'Household': ['detergent', 'cleaner', 'dishwash', 'dish wash', 'dish soap', 'washing', 'toilet', 
                 'kitchen', 'floor cleaner', 'disinfectant', 'dish bar', 'dish-bar', 'utensil'],
    'Health': ['medicine', 'tablet', 'capsule', 'syrup', 'vitamin', 'supplement', 'bandage', 
              'antiseptic', 'pain relief'],
    'Baby Care': ['baby', 'infant', 'diaper', 'formula', 'powder', 'wipes', 'baby food'],
    'Electronics': ['battery', 'charger', 'cable', 'phone', 'electronic', 'bulb', 'light']
}

# Subcategory Mappings
SUBCATEGORY_MAP = {
    'soap': 'Bath Soap',
    'dishwash': 'Dishwashing',
    'dish wash': 'Dishwashing',
    'dish bar': 'Dishwashing',
    'dish-bar': 'Dishwashing',
    'dishwasher': 'Dishwashing',
    'dish soap': 'Dishwashing',
    'utensil': 'Dishwashing',
    'detergent': 'Laundry',
    'laundry': 'Laundry',
    'washing powder': 'Laundry',
    'fabric': 'Laundry',
    'shampoo': 'Hair Care',
    'hair': 'Hair Care',
    'toothpaste': 'Oral Care',
    'tooth': 'Oral Care',
    'snack': 'Snacks',
    'biscuit': 'Biscuits',
    'cookie': 'Biscuits',
    'oil': 'Cooking Oil',
    'til': 'Cooking Oil',
    'ghani': 'Cooking Oil',
    'floor': 'Floor Cleaning',
    'toilet': 'Toilet Cleaning',
    'surface': 'Surface Cleaning'
}

# Indian Company Product Codes
INDIA_COMPANY_CODES = {
    "21021": "Exo/Vim (Hindustan Unilever)",
    "21022": "Lifebuoy (Hindustan Unilever)",
    "21023": "Lux (Hindustan Unilever)",
    "21027": "Pears (Hindustan Unilever)",
    "21002": "Colgate Palmolive",
    "21045": "Godrej Consumer Products",
    "21055": "Marico Limited",
    "21081": "ITC Limited",
    "21030": "Dabur India"
}

# Barcode Category Patterns
BARCODE_CATEGORY_PATTERNS = {
    "2102163": {"category": "Household", "subcategory": "Dishwashing"},
    "2102127": {"category": "Household", "subcategory": "Dishwashing"},
    "2102160": {"category": "Food & Beverages", "subcategory": "Cooking Oil"}
}

# Quantity Extraction Patterns
QUANTITY_PATTERNS = [
    # Common formats like "500g", "500 g", "500gram"
    r'(\d+(?:\.\d+)?)\s*(?:g|gm|gram|grams|grm)(?:\b|$)',
    # ml formats like "500ml", "500 ml"
    r'(\d+(?:\.\d+)?)\s*(?:ml|milli?li[dt]er)(?:\b|$)',
    # kg formats 
    r'(\d+(?:\.\d+)?)\s*(?:kg|kilo|kilogram)(?:\b|$)',
    # liter formats
    r'(\d+(?:\.\d+)?)\s*(?:l|ltr|lit|liter|litre)(?:\b|$)',
    # piece formats
    r'(\d+(?:\.\d+)?)\s*(?:pc|pcs|piece|pieces|pack)(?:\b|$)',
    # formats with "x" like "2x500g"
    r'(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(g|ml|gm|l)'
]

# AI Service Status Initial Configuration
AI_SERVICE_DEFAULT_STATUS = {
    "gemini": {"working": True, "failures": 0},  # Primary
    "openai": {"working": True, "failures": 0, "error_reason": None, "last_reset": 0},
    "deepseek": {"working": True, "failures": 0, "error_reason": None, "last_reset": 0}
}

# AI Prompt Templates
AI_ENHANCEMENT_PROMPT_TEMPLATE = """
I have a product with barcode {barcode}.
Here's the raw information I found:
{context}

Please help me structure this into a complete product entry with:
1. An accurate product name (never use 'Unknown Product' or 'Product with Barcode')
2. Brand (if identifiable)
3. Detailed description
4. Appropriate category and subcategory
5. Quantity and unit
6. At least 3-5 features of the product
7. Relevant specifications

Format the response as a JSON object that follows this exact structure:
{{
  "Barcode": "string",
  "Product Name": "string",
  "Brand": "string",
  "Description": "string",
  "Category": "string",
  "Subcategory": "string",
  "ProductLine": "string",
  "Quantity": number,
  "Unit": "string",
  "Features": ["string", "string", ...],
  "Specification": {{
    "key": "value",
    ...
  }}
}}
"""