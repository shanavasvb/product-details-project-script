import requests
import json
import re
import time
import logging
import os
import pandas as pd
import signal
import pickle
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Import constants
from constants import (
    LOG_LEVEL, LOG_FORMAT, DEFAULT_API_REQUEST_DELAY, DEFAULT_MAX_RETRIES,
    OPENFOODFACTS_BASE_URL, GOOGLE_SEARCH_API_URL, DIGITEYES_API_URL,
    GEMINI_API_URL, OPENAI_API_URL, DEEPSEEK_API_URL, OUTPUT_DIR, CACHE_DIR,
    INVALID_BARCODES_FILE, NOT_FOUND_BARCODES_FILE, PROGRESS_FILE,
    SINGLE_OUTPUT_FILE, VALID_BARCODE_LENGTHS, GEMINI_MODEL, OPENAI_MODEL,
    DEEPSEEK_MODEL, AI_TEMPERATURE, GEMINI_MAX_TOKENS, OPENAI_MAX_TOKENS,
    DEEPSEEK_MAX_TOKENS, CATEGORY_KEYWORDS, SUBCATEGORY_MAP, INDIA_COMPANY_CODES,
    BARCODE_CATEGORY_PATTERNS, QUANTITY_PATTERNS, AI_SERVICE_DEFAULT_STATUS,
    AI_ENHANCEMENT_PROMPT_TEMPLATE,JSON_CODEBLOCK_PATTERN, JSON_UNQUOTED_PROPERTY_PATTERN,JSON_TRAILING_COMMA_PATTERN,JSON_MISSING_COMMA_PATTERN,JSON_UNQUOTED_VALUE_PATTERN,
    JSON_MAX_CLEANUP_ATTEMPTS
)

# Setup logging
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('barcode_processor')

class BarcodeProcessor:
    """Barcode processor that reads from Excel file and searches for product information."""
    def __init__(self, output_dir: str = OUTPUT_DIR, single_file: bool = True):
        """Initialize the barcode processor with API keys from environment."""
        # Load environment variables from .env file
        load_dotenv()
        
        self.output_dir = output_dir
        self.single_file = single_file
        self.single_file_path = os.path.join(output_dir, SINGLE_OUTPUT_FILE)
        self.all_products = []
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Load existing data if file exists
        if single_file and os.path.exists(self.single_file_path):
            try:
                with open(self.single_file_path, 'r') as f:
                    self.all_products = json.load(f)
                logger.info(f"Loaded {len(self.all_products)} existing products from {self.single_file_path}")
            except json.JSONDecodeError:
                logger.warning(f"Could not parse existing file {self.single_file_path}, starting fresh")
        
        # API Keys from environment variables
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.google_cx = os.getenv("GOOGLE_SEARCH_CX")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        self.digiteyes_app_key = os.getenv("DIGITEYES_APP_KEY")
        self.digiteyes_signature = os.getenv("DIGITEYES_SIGNATURE")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.invalid_barcodes_file = os.path.join(output_dir, INVALID_BARCODES_FILE)
        self.invalid_barcodes = self._load_invalid_barcodes()
        logger.info(f"Loaded {len(self.invalid_barcodes)} known invalid barcodes")

        # Configuration
        self.api_request_delay = float(os.getenv("API_REQUEST_DELAY", str(DEFAULT_API_REQUEST_DELAY)))
        self.max_retries = int(os.getenv("MAX_RETRIES", str(DEFAULT_MAX_RETRIES)))
        self.openfoodfacts_url = os.getenv("OPENFOODFACTS_URL", OPENFOODFACTS_BASE_URL)
        self.stop_requested = False
        
        # Add local cache for Google search results
        self.search_cache_dir = os.path.join(output_dir, CACHE_DIR)
        os.makedirs(self.search_cache_dir, exist_ok=True)
        
        # Track processed items
        self.last_processed_item = None
        self.valid_barcodes = []
        self.processed_barcodes = []
        
        # AI failure tracking - set Gemini as the primary service
        self.ai_service_status = AI_SERVICE_DEFAULT_STATUS.copy()
        
        # Added failover info for common Indian product companies
        self.india_company_codes = INDIA_COMPANY_CODES
        
        # Common product categories by barcode patterns (for when all else fails)
        self.barcode_category_patterns = BARCODE_CATEGORY_PATTERNS
        
        logger.info("Barcode processor initialized with Gemini as the primary AI service")
        
        # Log configuration information
        logger.info(f"Using environment variables from .env file")
        logger.info(f"Output directory: {output_dir}")
        logger.info(f"Cache directory: {self.search_cache_dir}")
        logger.info(f"API request delay: {self.api_request_delay}s")
        logger.info(f"Maximum API retries: {self.max_retries}")
        
        # Verify API keys are loaded
        self._check_api_keys()

    def _load_invalid_barcodes(self):
        """Load previously identified invalid barcodes."""
        if os.path.exists(self.invalid_barcodes_file):
            try:
                with open(self.invalid_barcodes_file, 'r') as f:
                    data = json.load(f)
                    # Extract just the barcode values as a set for fast lookups
                    return {item['barcode'] for item in data if 'barcode' in item}
            except Exception as e:
                logger.warning(f"Error loading invalid barcodes: {e}")
        return set()  # Return empty set if file doesn't exist or can't be read

    def _check_api_keys(self):
        """Verify API keys are loaded and log warnings for missing keys."""
        missing_keys = []
        
        if not self.google_api_key:
            missing_keys.append("GOOGLE_API_KEY")
        if not self.google_cx:
            missing_keys.append("GOOGLE_SEARCH_CX")
        if not self.openai_api_key:
            missing_keys.append("OPENAI_API_KEY")
        if not self.gemini_api_key:
            missing_keys.append("GEMINI_API_KEY")
        if not self.deepseek_api_key:
            missing_keys.append("DEEPSEEK_API_KEY")
        if not self.digiteyes_app_key:
            missing_keys.append("DIGITEYES_APP_KEY")
        if not self.digiteyes_signature:
            missing_keys.append("DIGITEYES_SIGNATURE")
        
        if missing_keys:
            logger.warning(f"Missing environment variables: {', '.join(missing_keys)}")
            logger.warning("Some API services may not function correctly. Please check your .env file.")
        else:
            logger.info("All required API keys loaded successfully.")

    def setup_signal_handler(self):
        """Set up signal handler for graceful termination."""
        def signal_handler(sig, frame):
            logger.info("Interrupt received, finishing current barcode and stopping...")
            self.stop_requested = True
        
        signal.signal(signal.SIGINT, signal_handler)
    
    def process_excel_file(self, file_path: str) -> Tuple[List[str], List[str]]:
        """Process barcodes from an Excel file."""
        try:
            # Setup signal handler
            self.setup_signal_handler()
            
            # Read the Excel file
            logger.info(f"Reading barcodes from {file_path}")
            df = pd.read_excel(file_path)
            
            # Identify the barcode column (assuming it's the first column)
            barcode_col = df.columns[0]
            
            # Extract barcodes and convert to strings
            all_barcodes = [str(code).strip() for code in df[barcode_col].tolist() if str(code).strip()]
            
            # Validate barcodes
            valid_barcodes = []
            invalid_barcodes = []
            
            for barcode in all_barcodes:
                if self._is_valid_barcode(barcode):
                    valid_barcodes.append(barcode)
                else:
                    invalid_barcodes.append(barcode)
            
            self.valid_barcodes = valid_barcodes
            self.invalid_barcodes = invalid_barcodes
            
            logger.info(f"Found {len(valid_barcodes)} valid barcodes and {len(invalid_barcodes)} invalid barcodes")
            
            # Process valid barcodes
            results = []
            for barcode in valid_barcodes:
                # Check if processing should stop
                if self.stop_requested:
                    logger.info("Stopping barcode processing as requested")
                    break
                
                # Check if barcode is already in our results (from previous run)
                skip_barcode = False
                for existing_product in self.all_products:
                    if existing_product.get('Barcode') == barcode:
                        logger.info(f"Barcode {barcode} already exists in output file, using existing data")
                        results.append(existing_product)
                        self.last_processed_item = existing_product
                        self.processed_barcodes.append(barcode)
                        skip_barcode = True
                        break
                
                if skip_barcode:
                    continue
                
                # Process the barcode
                result = self.process_single_barcode(barcode)
                if result:
                    results.append(result)
                    self.processed_barcodes.append(barcode)
            
            # Display summary even if interrupted
            self.display_processing_summary()
            
            # Return lists of valid and invalid barcodes
            return valid_barcodes, invalid_barcodes
            
        except Exception as e:
            logger.error(f"Error processing Excel file: {e}")
            return [], []
    
    def process_single_barcode(self, barcode: str) -> Optional[Dict]:
        """Process a single barcode and return the product data."""
        logger.info(f"Processing barcode: {barcode}")
    
        # First try OpenFoodFacts
        product_data = self._search_openfoodfacts(barcode)
        failure_reasons = []
    
        # If not found, try Google Search
        if not product_data or not product_data.get('name'):
            logger.info(f"No data found in OpenFoodFacts, trying Google for: {barcode}")
            failure_reasons.append("Not found in OpenFoodFacts")
            product_data = self._search_google(barcode)
    
        # If not found, try DigiTeyes API
        if not product_data or not product_data.get('name'):
            logger.info(f"No data found in Google, trying DigiTeyes for: {barcode}")
            failure_reasons.append("Not found in Google Search")
            product_data = self._search_digiteyes(barcode)
    
        # If we have data, enhance it with AI
        if product_data and product_data.get('name'):
            logger.info(f"Found product data: {product_data.get('name')}")
            product_data = self._enhance_with_ai(product_data, barcode)
            
            # Save product data
            self._save_product_data(product_data)
            self.last_processed_item = product_data
            return product_data
        else:
            logger.warning(f"No product information found for barcode: {barcode}")
            failure_reasons.append("Not found in DigiTeyes")
            
            # Save to not found barcodes file
            self._save_not_found_barcode(barcode, failure_reasons)
            return None
    
    def _is_valid_barcode(self, barcode: str) -> bool:
        """Check if barcode has a valid format."""
        # First check: must be all digits
        if not barcode.isdigit():
            logger.warning(f"Invalid barcode (non-digits): {barcode}")
            return False
            
        # Second check: must be of valid length
        if len(barcode) not in VALID_BARCODE_LENGTHS:
            logger.warning(f"Invalid barcode (wrong length): {barcode}")
            return False
        
        return True
    
    def _search_openfoodfacts(self, barcode: str) -> Optional[Dict]:
        """Search for barcode in OpenFoodFacts."""
        try:
            url = f"{self.openfoodfacts_url}{barcode}.json"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if data.get('status') == 1 and 'product' in data:
                product = data['product']
                
                # Extract relevant information
                product_data = {
                    'name': product.get('product_name', ''),
                    'brand': product.get('brands', ''),
                    'description': product.get('generic_name', ''),
                    'ingredients': product.get('ingredients_text', ''),
                    'image_url': product.get('image_url', ''),
                    'quantity': product.get('quantity', ''),
                    'source': 'OpenFoodFacts'
                }
                
                # Try to extract numbers from quantity
                if product_data['quantity']:
                    qty_match = re.search(r'(\d+(?:\.\d+)?)\s*(g|ml|l|kg)', product_data['quantity'].lower())
                    if qty_match:
                        product_data['quantity_value'] = float(qty_match.group(1))
                        product_data['quantity_unit'] = qty_match.group(2)
                
                return product_data
            return None
        except Exception as e:
            logger.error(f"Error in OpenFoodFacts search: {e}")
            return None
    
    def resume_processing_from_last_position(self, excel_file: str) -> int:
        """
        Determine the row to resume processing from by finding the last processed barcode
        in the Excel file.
        
        Args:
            excel_file: Path to Excel file containing barcodes
            
        Returns:
            row_index: The row index to resume from (0-based)
        """
        last_barcode = None
        last_timestamp = None
        
        # Try to get last processed barcode from pickle file first (most reliable)
        progress_pickle_path = os.path.join(self.output_dir, PROGRESS_FILE)
        if os.path.exists(progress_pickle_path):
            try:
                with open(progress_pickle_path, 'rb') as f:
                    progress_data = pickle.load(f)
                    last_barcode = progress_data.get('last_processed_barcode')
                    logger.info(f"Found last processed barcode in pickle file: {last_barcode}")
                    
                    # If pickle contains exact row number, use that directly
                    if 'current_row' in progress_data:
                        next_row = progress_data['current_row'] + 1
                        logger.info(f"Resuming from row {next_row} based on pickle data")
                        return next_row
            except:
                logger.warning("Could not read pickle file, trying output.json")
        
        # Fall back to output.json if pickle not available or doesn't contain row number
        if not last_barcode and os.path.exists(self.single_file_path):
            try:
                with open(self.single_file_path, 'r') as f:
                    output_data = json.load(f)
                    
                    # Find most recent entry by timestamp
                    for entry in output_data:
                        timestamp = entry.get('Timestamp')
                        if timestamp:
                            try:
                                entry_time = datetime.fromisoformat(timestamp)
                                if not last_timestamp or entry_time > last_timestamp:
                                    last_timestamp = entry_time
                                    last_barcode = entry.get('Barcode')
                            except:
                                continue
                    
                    if last_barcode:
                        logger.info(f"Found last processed barcode in output.json: {last_barcode}")
            except:
                logger.warning("Could not determine last processed barcode from output.json")
        
        # If we found a last barcode, locate its position in the Excel file
        if last_barcode:
            try:
                # Read barcode column from Excel
                df = pd.read_excel(excel_file)
                barcode_column = None
                
                # Try to identify the barcode column
                for column in df.columns:
                    if 'barcode' in str(column).lower() or 'code' in str(column).lower():
                        barcode_column = column
                        break
                
                if not barcode_column and len(df.columns) > 0:
                    # If no column name contains 'barcode', use the first column
                    barcode_column = df.columns[0]
                
                if barcode_column:
                    # Convert all to string for comparison
                    df[barcode_column] = df[barcode_column].astype(str)
                    
                    # Find the row containing the last processed barcode
                    for i, row in df.iterrows():
                        if str(row[barcode_column]) == str(last_barcode):
                            next_row = i + 1
                            logger.info(f"Found last barcode at row {i}, resuming from row {next_row}")
                            return next_row
                    
                    logger.warning(f"Last barcode {last_barcode} not found in Excel file, starting from beginning")
                else:
                    logger.warning("Could not identify barcode column in Excel file")
            except Exception as e:
                logger.error(f"Error finding row position: {e}")
        
        # If all else fails, start from the beginning
        logger.info("Starting from the beginning of the Excel file")
        return 0

    def signal_handler(self, sig, frame):
        """Handle keyboard interrupt by gracefully stopping the processor."""
        logger.info("Interrupt received, completing current barcode and stopping...")
        self.stop_requested = True

    def _add_invalid_barcode(self, barcode: str, reasons: List[str] = None) -> None:
        """Add a barcode to the invalid barcodes file."""
        invalid_data = []
        
        # Load existing invalid barcodes if file exists
        if os.path.exists(self.invalid_barcodes_file):
            try:
                with open(self.invalid_barcodes_file, 'r') as f:
                    invalid_data = json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Could not parse existing invalid barcodes file, starting fresh")
        
        # Check if barcode already exists in list
        for item in invalid_data:
            if item.get('barcode') == barcode:
                # Update reasons if needed
                if reasons:
                    item['reasons'] = list(set(item.get('reasons', []) + reasons))
                return  # Barcode already in list, no need to add again
        
        # Add to list if not exists
        invalid_data.append({
            'barcode': barcode,
            'date_added': datetime.now().isoformat(),
            'reasons': reasons or ["Unknown reason"]
        })
        
        # Save updated list
        with open(self.invalid_barcodes_file, 'w') as f:
            json.dump(invalid_data, f, indent=2)
        
        # Add to in-memory set for fast lookups
        if isinstance(self.invalid_barcodes, set):
            self.invalid_barcodes.add(barcode)
        else:
            # Ensure it's a set if it somehow got created as something else
            self.invalid_barcodes = set(self.invalid_barcodes)
            self.invalid_barcodes.add(barcode)
        
        logger.info(f"Added barcode {barcode} to {INVALID_BARCODES_FILE}")

    def _is_valid_barcode_format(self, barcode: str) -> bool:
        """Check if barcode has a valid format (EAN-8, EAN-13, UPC-A, GTIN-14)."""
        # Remove any spaces or dashes
        barcode = barcode.replace(' ', '').replace('-', '')
        
        # Valid barcodes are numeric and 8, 12, 13 or 14 digits long
        if not barcode.isdigit():
            return False
            
        if len(barcode) not in VALID_BARCODE_LENGTHS:
            return False
            
        return True

    def process_barcodes_from_excel(self, excel_file: str) -> Dict:
        """Process barcodes from Excel file with efficient resume capability and invalid barcode filtering."""
        try:
            # Determine the row to resume from
            start_row = self.resume_processing_from_last_position(excel_file)
            
            # Read the Excel file
            df = pd.read_excel(excel_file)
            
            if df.empty:
                logger.warning(f"Excel file {excel_file} is empty")
                return {'status': 'error', 'message': 'Excel file is empty'}
            
            # Initialize progress tracking
            total_rows = len(df)
            processed = 0
            successful = 0
            errors = 0
            skipped_invalid = 0
            start_time = time.time()
            
            # Try to identify the barcode column
            barcode_column = None
            for column in df.columns:
                if 'barcode' in str(column).lower() or 'code' in str(column).lower():
                    barcode_column = column
                    break
            
            if not barcode_column and len(df.columns) > 0:
                # If no column name contains 'barcode', use the first column
                barcode_column = df.columns[0]
                logger.info(f"Using column '{barcode_column}' as barcode column")
            
            # Set up progress state
            progress_state = {
                'start_time': datetime.now().isoformat(),
                'current_row': start_row,
                'total_rows': total_rows,
                'processed_count': processed,
                'success_count': successful,
                'error_count': errors,
                'skipped_invalid': skipped_invalid
            }
            
            progress_pickle_path = os.path.join(self.output_dir, PROGRESS_FILE)
            
            logger.info(f"Starting to process barcodes from Excel file {excel_file} at row {start_row+1}/{total_rows}")
            
            # Process each row starting from the resume position
            for i, row in df.iloc[start_row:].iterrows():
                try:
                    if self.stop_requested:
                        logger.info("Stop requested, saving progress")
                        break
                    
                    # Update current row in progress state
                    progress_state['current_row'] = i
                    
                    # Get barcode from the appropriate column
                    if barcode_column:
                        barcode = str(row[barcode_column]).strip()
                    else:
                        # If no barcode column was identified, try to use the first cell in the row
                        barcode = str(row[0]).strip()
                    
                    # Skip empty barcodes
                    if not barcode or barcode == 'nan':
                        logger.warning(f"Empty barcode at row {i+1}, skipping")
                        processed += 1
                        errors += 1
                        continue
                    
                    # Skip already known invalid barcodes
                    if barcode in self.invalid_barcodes:
                        logger.info(f"Skipping known invalid barcode at row {i+1}: {barcode}")
                        processed += 1       # Count as processed
                        skipped_invalid += 1 # Count as skipped invalid
                        continue
                    
                    # Check if barcode is valid (proper format)
                    if not self._is_valid_barcode_format(barcode):
                        logger.warning(f"Invalid barcode format at row {i+1}: {barcode}, adding to invalid barcodes")
                        self._add_invalid_barcode(barcode, ["Invalid format"])
                        processed += 1
                        errors += 1
                        continue
                    
                    # Check if this barcode is already in our output (to avoid duplicates)
                    if self.single_file and self._is_already_processed(barcode):
                        logger.info(f"Barcode {barcode} already processed, skipping")
                        processed += 1
                        successful += 1  # Count as successful since we already have the data
                        continue
                    
                    logger.info(f"Processing row {i+1}/{total_rows}, barcode: {barcode}")
                    
                    # Process the barcode
                    result = self.process_single_barcode(barcode)
                    
                    # Update progress tracking
                    processed += 1
                    if result:
                        successful += 1
                        # Save the last successfully processed barcode
                        progress_state['last_processed_barcode'] = barcode
                    else:
                        errors += 1
                    
                    # Update progress state
                    progress_state['processed_count'] = processed
                    progress_state['success_count'] = successful
                    progress_state['error_count'] = errors
                    progress_state['skipped_invalid'] = skipped_invalid
                    
                    # Save progress state to pickle file
                    with open(progress_pickle_path, 'wb') as f:
                        pickle.dump(progress_state, f)
                    
                    # Small delay between processing to avoid overwhelming APIs
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error processing row {i+1}: {e}")
                    errors += 1
                    progress_state['error_count'] = errors
                    # Save progress even after errors
                    with open(progress_pickle_path, 'wb') as f:
                        pickle.dump(progress_state, f)
            
            # Processing completed or interrupted
            end_time = time.time()
            duration = end_time - start_time
            
            # Calculate processing stats
            avg_time_per_barcode = duration / processed if processed > 0 else 0
            completion_percentage = (processed / total_rows) * 100 if total_rows > 0 else 0
            
            logger.info(f"Barcode processing completed or paused:")
            logger.info(f"- Total rows in Excel: {total_rows}")
            logger.info(f"- Processed: {processed} ({completion_percentage:.1f}%)")
            logger.info(f"- Successful: {successful}")
            logger.info(f"- Errors: {errors}")
            logger.info(f"- Skipped (invalid): {skipped_invalid}")
            logger.info(f"- Processing time: {duration:.2f} seconds ({avg_time_per_barcode:.2f} seconds per barcode)")
            
            return {
                'status': 'success',
                'total': total_rows,
                'processed': processed,
                'successful': successful,
                'errors': errors,
                'skipped_invalid': skipped_invalid,
                'processing_time': duration,
                'avg_time_per_barcode': avg_time_per_barcode,
                'completion_percentage': completion_percentage,
                'date': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing Excel file: {e}")
            return {'status': 'error', 'message': str(e)}

    def _is_already_processed(self, barcode: str) -> bool:
        """Check if a barcode has already been processed and exists in the output."""
        if not self.all_products:
            return False
            
        # Look for barcode in already processed items
        for product in self.all_products:
            if product.get('Barcode') == barcode:
                return True
                
        return False
    def clean_and_parse_json(text):
     """
     Clean and parse potentially malformed JSON from AI responses.
     Uses multiple strategies to fix common JSON errors.
     """
     # First, try to extract JSON block if embedded in other text
     json_match = re.search(JSON_CODEBLOCK_PATTERN, text, re.DOTALL)
     if json_match:
        text = json_match.group(1)
     else:
        # Try to find JSON between curly braces
        json_start = text.find('{')
        json_end = text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            text = text[json_start:json_end]
    
     # Try direct parsing first
     try:
        return json.loads(text)
     except json.JSONDecodeError:
        pass
    
     # Fix unquoted property names (the error you're specifically seeing)
     fixed_text = re.sub(JSON_UNQUOTED_PROPERTY_PATTERN, r'\1"\2":', text)
    
     # Fix trailing commas in lists and objects
     fixed_text = re.sub(JSON_TRAILING_COMMA_PATTERN, r'\1', fixed_text)
    
     # Fix missing commas between elements
     fixed_text = re.sub(JSON_MISSING_COMMA_PATTERN, r'\1,\n\2', fixed_text)
    
     # Try parsing the fixed JSON
     try:
        return json.loads(fixed_text)
     except json.JSONDecodeError:
        # If still failing, try a more aggressive approach
        # Fix single quotes to double quotes
        fixed_text = fixed_text.replace("'", '"')
        # Fix missing quotes around string values
        fixed_text = re.sub(JSON_UNQUOTED_VALUE_PATTERN, r': "\1"\2', fixed_text)
        
        try:
            return json.loads(fixed_text)
        except json.JSONDecodeError as e:
            # Last resort, log the error and return None or raise
            print(f"Failed to parse JSON after cleanup: {e}")
            print(f"Problematic text: {text}")
            return None
    def _search_google(self, barcode: str) -> Optional[Dict]:
        """Search for barcode on Google using Google Custom Search API."""
        try:
            # First try a direct search for the barcode
            query = f"{barcode} product"
            
            # Use Google Custom Search API
            url = GOOGLE_SEARCH_API_URL
            params = {
                "key": self.google_api_key,
                "cx": self.google_cx,
                "q": query,
                "num": 10
            }
            
            logger.info(f"Searching Google for: {query}")
            
            # Add retries for API calls
            for attempt in range(self.max_retries):
                try:
                    response = requests.get(url, params=params, timeout=15)
                    if response.status_code == 200:
                        break
                    elif response.status_code == 429:  # Rate limit
                        wait_time = (attempt + 1) * 5
                        logger.warning(f"Google API rate limit hit, waiting {wait_time} seconds")
                        time.sleep(wait_time)
                    else:
                        logger.warning(f"Google API error: {response.status_code} - {response.text}")
                        break
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Request failed: {e}")
                    time.sleep(1)
            
            if response.status_code != 200:
                logger.error(f"Google API error after retries: {response.status_code} - {response.text}")
                return None
                
            data = response.json()
            time.sleep(self.api_request_delay)  # Respect rate limits
            
            # Extract search results
            search_results = []
            product_data = {'source': 'Google Search'}
            
            # Process items from search results
            if 'items' in data:
                for item in data['items'][:5]:  # Look at top 5 results
                    title = item.get('title', '')
                    snippet = item.get('snippet', '')
                    link = item.get('link', '')
                    
                    search_results.append({
                        'title': title,
                        'snippet': snippet,
                        'link': link
                    })
            
            # If no good results, try adding more context to the search
            if not search_results:
                logger.info(f"No good results, trying alternate search for barcode {barcode}")
                
                # Try specific phrases for Indian products
                if barcode.startswith('890'):
                    alternate_query = f"{barcode} indian product description"
                else:
                    alternate_query = f"{barcode} product details"
                    
                params['q'] = alternate_query
                
                # Retry mechanism for alternate search
                for attempt in range(self.max_retries):
                    try:
                        response = requests.get(url, params=params, timeout=15)
                        if response.status_code == 200:
                            break
                        elif response.status_code == 429:  # Rate limit
                            wait_time = (attempt + 1) * 5
                            logger.warning(f"Google API rate limit hit, waiting {wait_time} seconds")
                            time.sleep(wait_time)
                        else:
                            logger.warning(f"Google API error: {response.status_code} - {response.text}")
                            break
                    except requests.exceptions.RequestException as e:
                        logger.warning(f"Request failed: {e}")
                        time.sleep(1)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract from alternate search
                    if 'items' in data:
                        for item in data['items'][:5]:
                            title = item.get('title', '')
                            snippet = item.get('snippet', '')
                            link = item.get('link', '')
                            
                            search_results.append({
                                'title': title,
                                'snippet': snippet,
                                'link': link
                            })
                
                time.sleep(self.api_request_delay)  # Respect rate limits
            
            # Extract product information from search results
            if search_results:
                # Look for e-commerce sites or product listings
                ecommerce_sites = ['amazon', 'flipkart', 'bigbasket', 'grofers', 'nykaa', 
                                  'tatacliq', 'jiomart', 'walmart', 'target', 'shop']
                product_indicators = ['g', 'kg', 'ml', 'l', 'pack', 'combo', 'bar', 'bottle']
                
                # First, try to find e-commerce listings
                for result in search_results:
                    title = result['title']
                    
                    # Skip results about barcode databases or UPC listings
                    if any(term in title.lower() for term in ['upc code', 'barcode database', 'list of', 'codes beginning']):
                        continue
                    
                    # Check for e-commerce sites or product weight indicators
                    if (any(site in result['link'].lower() for site in ecommerce_sites) or
                            any(indicator in title.lower() for indicator in product_indicators)):
                        
                        # Extract product name (usually before "-" or "|")
                        if '-' in title:
                            product_name = title.split('-')[0].strip()
                        elif '|' in title:
                            product_name = title.split('|')[0].strip()
                        else:
                            product_name = title
                        
                        # Don't use very short names or names that are just "product"
                        if len(product_name.split()) >= 2 and product_name.lower() != "product":
                            product_data['name'] = product_name
                            
                            # Try to extract brand (usually first word)
                            words = product_name.split()
                            if len(words) > 1:
                                product_data['brand'] = words[0]
                            
                            # Extract description from snippet
                            product_data['description'] = result['snippet']
                            
                            # Save the URL
                            product_data['source_url'] = result['link']
                            
                            # Try to extract quantity and unit using regex
                            qty_match = re.search(r'(\d+(?:\.\d+)?)\s*(g|gm|gram|ml|l|liter|kg|pc|pack)', 
                                                 title, re.IGNORECASE)
                            if qty_match:
                                product_data['quantity_value'] = float(qty_match.group(1))
                                product_data['quantity_unit'] = qty_match.group(2).lower()
                            
                            return product_data
            
            return None
        except Exception as e:
            logger.error(f"Error in Google search: {e}")
            return None
    
    def _search_digiteyes(self, barcode: str) -> Optional[Dict]:
        """Search for barcode using DigiTeyes API."""
        try:
            url = DIGITEYES_API_URL
            params = {
                "upcCode": barcode,
                "app_key": self.digiteyes_app_key,
                "signature": self.digiteyes_signature,
                "language": "en"
            }
            
            logger.info(f"Searching DigiTeyes for barcode: {barcode}")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data and 'description' in data:
                    # Extract product information
                    product_data = {
                        'name': data.get('description', ''),
                        'brand': data.get('brand', ''),
                        'description': data.get('description', ''),
                        'image_url': data.get('image', ''),
                        'source': 'DigiTeyes'
                    }
                    
                    # Try to extract quantity
                    if 'packaging' in data:
                        qty_match = re.search(r'(\d+(?:\.\d+)?)\s*(g|gm|gram|ml|l|liter|kg|pc|pack)', 
                                            data['packaging'], re.IGNORECASE)
                        if qty_match:
                            product_data['quantity_value'] = float(qty_match.group(1))
                            product_data['quantity_unit'] = qty_match.group(2).lower()
                    
                    return product_data
            
            return None
        except Exception as e:
            logger.error(f"Error in DigiTeyes search: {e}")
            return None
    
    def _enhance_with_ai(self, product_data: Dict, barcode: str) -> Dict:
     """Enhance product data using AI, with fallback to local processing."""
     # Skip AI if all services have had multiple failures
     if (not self.ai_service_status["gemini"]["working"] and
        not self.ai_service_status["openai"]["working"] and 
        not self.ai_service_status["deepseek"]["working"]):
        logger.info("All AI services are disabled due to repeated failures, using local processing")
        return self._intelligent_format_product_data(product_data, barcode)
    
     try:
        # Prepare data for AI enhancement
        context = json.dumps(product_data, indent=2)
        
        prompt = AI_ENHANCEMENT_PROMPT_TEMPLATE.format(barcode=barcode, context=context)
        
        # Try AI enhancement with fixed error handling
        response = None
        
        # Try Gemini first (primary AI service)
        if self.ai_service_status["gemini"]["working"]:
            logger.info("Enhancing product data with Gemini API")
            response = self._call_gemini_api(prompt)
            
            # If Gemini failed 3 times in a row, mark it as not working
            if not response and self.ai_service_status["gemini"]["failures"] >= 3:
                for attempt in range(1, 30):
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"Gemini rate limit hit, waiting {wait_time} seconds")
                    time.sleep(wait_time)
                logger.warning("Gemini API marked as unavailable after repeated failures")
                self.ai_service_status["gemini"]["working"] = False
        
        # If Gemini failed, try OpenAI if it's still working
        if not response and self.ai_service_status["openai"]["working"]:
            logger.info("Gemini enhancement failed, trying OpenAI")
            response = self._call_openai_api(prompt)
            
            # If OpenAI failed 3 times in a row, mark it as not working
            if not response and self.ai_service_status["openai"]["failures"] >= 3:
                logger.warning("OpenAI API marked as unavailable after repeated failures")
                self.ai_service_status["openai"]["working"] = False
        
        # If OpenAI failed or is marked as not working, try DeepSeek
        if not response and self.ai_service_status["deepseek"]["working"]:
            logger.info("OpenAI enhancement failed, trying DeepSeek")
            response = self._call_deepseek_api(prompt)
            
            # If DeepSeek failed 3 times in a row, mark it as not working
            if not response and self.ai_service_status["deepseek"]["failures"] >= 3:
                logger.warning("DeepSeek API marked as unavailable after repeated failures")
                self.ai_service_status["deepseek"]["working"] = False
        
        if response:
            try:
                # Use the improved JSON parser
                from json_parser import clean_and_parse_json
                enhanced_data = clean_and_parse_json(response)
                
                if enhanced_data and 'Product Name' in enhanced_data and enhanced_data['Product Name']:
                    # Add timestamps and image info
                    enhanced_data['Product Image'] = product_data.get('image_url', '')
                    enhanced_data['Product Ingredient Image'] = product_data.get('ingredient_image', '')
                    enhanced_data['Data Source'] = 'AI Enhanced'
                    enhanced_data['Timestamp'] = datetime.now().isoformat()
                    
                    logger.info("Successfully enhanced product data with AI")
                    return enhanced_data
            except Exception as e:
                logger.error(f"Error parsing AI response: {e}")
    
        # If AI fails, use intelligent local processing
        logger.info("AI enhancement failed, using intelligent local processing")
        return self._intelligent_format_product_data(product_data, barcode)
        
     except Exception as e:
        logger.error(f"Error enhancing product data with AI: {e}")
        return self._intelligent_format_product_data(product_data, barcode)
    def _call_gemini_api(self, prompt: str) -> Optional[str]:
        """Call Google Gemini API with updated model name."""
        try:
            # Skip if this service is marked as not working
            if not self.ai_service_status["gemini"]["working"]:
                return None
            
            # Updated URL and model name
            url = GEMINI_API_URL
            params = {
                "key": self.gemini_api_key
            }
            data = {
                "contents": [
                    {
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "temperature": AI_TEMPERATURE,
                    "maxOutputTokens": GEMINI_MAX_TOKENS
                }
            }
            
            try:
                response = requests.post(url, params=params, json=data, timeout=30)
                
                if response.status_code == 200:
                    self.ai_service_status["gemini"]["failures"] = 0
                    response_json = response.json()
                    
                    if 'candidates' in response_json and len(response_json['candidates']) > 0:
                        content = response_json['candidates'][0].get('content', {})
                        parts = content.get('parts', [])
                        if parts and 'text' in parts[0]:
                            return parts[0]['text']
                    
                    logger.warning("Unexpected response format from Gemini API")
                    self.ai_service_status["gemini"]["failures"] += 1
                    return None
                else:
                    logger.warning(f"Gemini API error: {response.status_code} - {response.text}")
                    self.ai_service_status["gemini"]["failures"] += 1
                    return None
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Gemini request failed: {e}")
                self.ai_service_status["gemini"]["failures"] += 1
                return None
                
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
            self.ai_service_status["gemini"]["failures"] += 1
            return None

    def _call_openai_api(self, prompt: str) -> Optional[str]:
        """Call OpenAI API with better error handling."""
        try:
            if not self.ai_service_status["openai"]["working"]:
                return None
            
            url = OPENAI_API_URL
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_api_key}"
            }
            data = {
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a product data specialist who extracts and formats product information."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": AI_TEMPERATURE,
                "max_tokens": OPENAI_MAX_TOKENS  # Reduced to avoid quota issues
            }
            
            try:
                response = requests.post(url, headers=headers, json=data, timeout=30)
                
                if response.status_code == 200:
                    self.ai_service_status["openai"]["failures"] = 0
                    return response.json()["choices"][0]["message"]["content"]
                
                # Better error handling
                if response.status_code == 429:
                    error_data = response.json().get('error', {})
                    error_type = error_data.get('type', '')
                    
                    if 'insufficient_quota' in error_type:
                        logger.warning("OpenAI API quota exceeded - marking as unavailable")
                        self.ai_service_status["openai"]["working"] = False
                    else:
                        logger.warning(f"OpenAI API rate limited: {error_data.get('message', 'Unknown error')}")
                    
                    self.ai_service_status["openai"]["failures"] += 1
                    return None
                
                elif response.status_code == 401:
                    logger.error("OpenAI API authentication failed - check API key")
                    self.ai_service_status["openai"]["working"] = False
                    return None
                
                else:
                    logger.warning(f"OpenAI API error: {response.status_code} - {response.text}")
                    self.ai_service_status["openai"]["failures"] += 1
                    return None
                
            except requests.exceptions.RequestException as e:
                logger.error(f"OpenAI request failed: {e}")
                self.ai_service_status["openai"]["failures"] += 1
                return None
                
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            self.ai_service_status["openai"]["failures"] += 1
            return None

    def _call_deepseek_api(self, prompt: str) -> Optional[str]:
        """Call DeepSeek API with better balance checking."""
        try:
            if not self.ai_service_status["deepseek"]["working"]:
                return None
                
            url = DEEPSEEK_API_URL
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.deepseek_api_key}"
            }
            data = {
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a product data specialist who extracts and formats product information."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": AI_TEMPERATURE,
                "max_tokens": DEEPSEEK_MAX_TOKENS
            }
            
            try:
                response = requests.post(url, headers=headers, json=data, timeout=30)
                
                if response.status_code == 200:
                    self.ai_service_status["deepseek"]["failures"] = 0
                    return response.json()["choices"][0]["message"]["content"]
                
                # Better error handling for payment issues
                elif response.status_code == 402:
                    logger.warning("DeepSeek API insufficient balance - marking as unavailable")
                    self.ai_service_status["deepseek"]["working"] = False
                    return None
                
                elif response.status_code == 401:
                    logger.error("DeepSeek API authentication failed - check API key")
                    self.ai_service_status["deepseek"]["working"] = False
                    return None
                
                elif response.status_code == 429:
                    logger.warning("DeepSeek API rate limited")
                    self.ai_service_status["deepseek"]["failures"] += 1
                    return None
                
                else:
                    logger.error(f"DeepSeek API error: {response.status_code} - {response.text}")
                    self.ai_service_status["deepseek"]["failures"] += 1
                    return None
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"DeepSeek request failed: {e}")
                self.ai_service_status["deepseek"]["failures"] += 1
                return None
            
        except Exception as e:
            logger.error(f"Error calling DeepSeek API: {e}")
            self.ai_service_status["deepseek"]["failures"] += 1
            return None
    
    def _save_not_found_barcode(self, barcode: str, reasons: List[str] = None) -> None:
        """Save barcode with no data found to a separate JSON file."""
        not_found_file = os.path.join(self.output_dir, NOT_FOUND_BARCODES_FILE)
        not_found_data = []
        
        # Load existing not found data if available
        if os.path.exists(not_found_file):
            try:
                with open(not_found_file, 'r') as f:
                    not_found_data = json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Could not parse existing not found file, starting fresh")
        
        # Check if this barcode is already in the list
        for item in not_found_data:
            if item.get('barcode') == barcode:
                # Update existing entry with new timestamp and attempts
                item['attempts'] = item.get('attempts', 0) + 1
                item['last_attempt'] = datetime.now().isoformat()
                item['reasons'] = reasons or ["Unknown reason"]
                break
        else:
            # Add new entry if not exists
            not_found_data.append({
                'barcode': barcode,
                'attempts': 1,
                'first_attempt': datetime.now().isoformat(),
                'last_attempt': datetime.now().isoformat(),
                'reasons': reasons or ["Unknown reason"]
            })
        
        # Save updated list
        with open(not_found_file, 'w') as f:
            json.dump(not_found_data, f, indent=2)
        
        logger.info(f"Saved barcode {barcode} to {NOT_FOUND_BARCODES_FILE}")

    def _intelligent_format_product_data(self, product_data: Dict, barcode: str) -> Dict:
        """Intelligently format product data without AI, using improved pattern recognition."""
        
        # Extract and clean the product name, brand, description plus any search results
        name = product_data.get('name', '').strip()
        brand = product_data.get('brand', '').strip()
        description = product_data.get('description', '').strip()
        
        # NEW: Also look for additional data from source_url or snippet
        search_text = ''
        if 'source_url' in product_data:
            search_text += product_data.get('source_url', '') + ' '
        if 'snippet' in product_data:
            search_text += product_data.get('snippet', '') + ' '
        
        # Combine all text for analysis
        full_text = f"{name} {description} {search_text}".lower()
        
        # Detect category with improved algorithm
        category = 'Other'
        subcategory = ''
        
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(keyword in full_text for keyword in keywords):
                category = cat
                break
        
        # Detect subcategory with improved search
        for keyword, subcat in SUBCATEGORY_MAP.items():
            if keyword in full_text:
                subcategory = subcat
                break
        
        # Extract brand if not already present
        if not brand and name:
            words = name.split()
            if len(words) > 1:
                brand = words[0]
        
        # Extract quantity and unit with more comprehensive patterns
        quantity = 0
        unit = ""
        
        # Enhanced patterns for finding quantity and unit
        for pattern in QUANTITY_PATTERNS:
            # Search in full text first
            match = re.search(pattern, full_text)
            if match:
                if len(match.groups()) == 1:
                    quantity = float(match.group(1))
                    
                    # Determine unit based on pattern
                    if 'g' in pattern:
                        unit = 'g'
                    elif 'ml' in pattern:
                        unit = 'ml'
                    elif 'kg' in pattern:
                        unit = 'kg'
                    elif 'l' in pattern:
                        unit = 'l'
                    elif 'pc' in pattern or 'piece' in pattern:
                        unit = 'pc'
                        
                elif len(match.groups()) == 3:  # For patterns like "2 x 500g"
                    quantity = float(match.group(1)) * float(match.group(2))
                    unit = match.group(3)
                    
                break
        
        # If no match found, try more general numeric extraction
        if quantity == 0:
            # Look for specific numbers followed by weight units
            weight_matches = re.findall(r'(\d+)\s*(?:g|gm|gram|ml|l|kg)', full_text)
            if weight_matches:
                # Use the first found weight
                quantity = float(weight_matches[0])
                
                # Try to determine unit from context
                if f"{quantity} g" in full_text or f"{quantity}g" in full_text:
                    unit = 'g'
                elif f"{quantity} ml" in full_text or f"{quantity}ml" in full_text:
                    unit = 'ml'
                elif f"{quantity} kg" in full_text or f"{quantity}kg" in full_text:
                    unit = 'kg'
                elif f"{quantity} l" in full_text or f"{quantity}l" in full_text:
                    unit = 'l'
        
        # Look for specifically formatted weight patterns common in product listings
        if quantity == 0 and unit == "":
            # Search for weight in common formats like "500 Gm"
            weight_gm_match = re.search(r'(\d+)\s*Gm\b', full_text, re.IGNORECASE)
            if weight_gm_match:
                quantity = float(weight_gm_match.group(1))
                unit = 'g'
        
        # Generate intelligent features based on category and product info
        features = []
        
        if category == 'Personal Care':
            features.extend(['Gentle formula', 'Suitable for daily use', 'Dermatologically tested'])
            if 'soap' in full_text:
                features.extend(['Moisturizing', 'Long-lasting fragrance'])
        elif category == 'Household':
            features.extend(['Effective cleaning', 'Easy to use', 'Value for money'])
            if 'dishwash' in full_text or 'dish wash' in full_text or 'dish bar' in full_text:
                features.extend(['Cuts through grease effectively', 'Gentle on hands'])
                if 'anti-bacterial' in full_text or 'antibacterial' in full_text:
                    features.append('Anti-bacterial formula')
                if 'ginger' in full_text:
                    features.append('Ginger twist fragrance')
        elif category == 'Food & Beverages':
            features.extend(['Fresh quality', 'Nutritious', 'Ready to consume'])
    
            if 'oil' in full_text:
                features.extend(['Pure and natural', 'Rich in nutrients'])
        else:
            features.extend(['Quality product', 'Trusted brand', 'Good value'])
        
        # Create specifications
        specifications = {
            'Brand': brand or 'Unknown Brand',
            'Country of Origin': 'India' if barcode.startswith('890') else 'Unknown',
            'Barcode Type': f"{len(barcode)}-digit barcode"
        }
        
        if quantity > 0 and unit:
            specifications['Weight/Volume'] = f"{quantity} {unit}"
            specifications['Net Quantity'] = f"{quantity} {unit}"
        
        # Add category-specific specifications
        if category == 'Personal Care':
            specifications['Suitable For'] = 'All skin types'
        elif category == 'Food & Beverages':
            specifications['Storage'] = 'Store in cool, dry place'
        elif category == 'Household' and ('dishwash' in full_text or 'dish wash' in full_text):
            if 'round' in full_text:
                specifications['Form Factor'] = 'Round bar'
            if 'ginger' in full_text:
                specifications['Fragrance'] = 'Ginger twist'
        
        # Enhance the product name if it's too generic
        if len(name.split()) <= 2:  # If name is very short like "Exo Round"
            enhanced_name = name
            
            # Try to enhance with more specific details
            if 'anti-bacterial' in full_text or 'antibacterial' in full_text:
                if 'dish' not in enhanced_name.lower():
                    if 'dishwash' in full_text or 'dish wash' in full_text:
                        enhanced_name += ' Anti-Bacterial Dishwash Bar'
            
            # If still generic and we know it's a dishwashing product
            if len(enhanced_name.split()) <= 2 and 'dishwash' in full_text:
                enhanced_name += ' Dishwash Bar'
                
            name = enhanced_name
        
        # Enhance description if it's too generic
        if description in ['', f"{name}. Quality product from {brand}."]:
            if category == 'Household' and ('dishwash' in full_text or 'dish wash' in full_text):
                description = f"{brand} {name} is an effective dishwashing bar that helps remove grease and food residue from dishes."
                
                if 'anti-bacterial' in full_text or 'antibacterial' in full_text:
                    description += " With anti-bacterial properties to ensure hygienic cleaning."
                
                if 'ginger' in full_text:
                    description += " Features a refreshing ginger fragrance."
                    
        # Format the final result
        result = {
            'Barcode': barcode,
            'Product Name': name,
            'Brand': brand,
            'Description': description,
            'Category': category,
            'Subcategory': subcategory,
            'ProductLine': f"{brand} {subcategory} Products" if subcategory else f"{brand} Products",
            'Quantity': quantity,
            'Unit': unit,
            'Features': features,
            'Specification': specifications,
            'Product Image': product_data.get('image_url', ''),
            'Product Ingredient Image': product_data.get('ingredient_image', ''),
            'Nutrition Image': product_data.get('nutrition_image', ''),
            'Data Source': f"Intelligent Processing - {product_data.get('source', 'Multiple Sources')}",
            'Timestamp': datetime.now().isoformat()
        }
        
        return result 

    def _save_product_data(self, product_data: Dict) -> None:
        """Save product data to JSON file(s), excluding unknown products from the main output."""
        barcode = product_data['Barcode']
        
        # Check if this is an unknown product
        if self.is_unknown_product(product_data):
            # Save to not_found_barcodes.json only
            self._add_to_not_found_barcodes(product_data)
            logger.info(f"Product with barcode {barcode} classified as unknown, saved to {NOT_FOUND_BARCODES_FILE} only")
            return
        
        # Add to all_products list (only known products)
        if self.single_file:
            # Check if this barcode already exists in the list
            existing_index = None
            for i, existing_product in enumerate(self.all_products):
                if existing_product.get('Barcode') == barcode:
                    existing_index = i
                    break
                    
            # Replace or append product data
            if existing_index is not None:
                self.all_products[existing_index] = product_data
            else:
                self.all_products.append(product_data)
                
            # Save the updated all_products list
            with open(self.single_file_path, "w") as f:
                json.dump(self.all_products, f, indent=2)
            
            logger.info(f"Updated single JSON file with data for barcode: {barcode}")
        
        # Optionally save individual file (if not in single_file mode)
        if not self.single_file:
            filename = os.path.join(self.output_dir, f"{barcode}.json")
            with open(filename, "w") as f:
                json.dump(product_data, f, indent=2)
            logger.info(f"Saved product data for {barcode} to {filename}")

    def is_unknown_product(self, product_data):
        """
        Check if a product is considered 'unknown' or not found
        
        Args:
            product_data (dict): Product data dictionary
            
        Returns:
            bool: True if product is unknown/not found
        """
        indicators = [
            product_data.get("Product Name", "").startswith("Unknown Product"),
            product_data.get("Brand", "") == "Unknown",
            product_data.get("Category", "") == "Unknown",
            product_data.get("Data Source", "") == "No Data Found",
            product_data.get("Description", "").startswith("Could not find information"),
            "Information not available" in product_data.get("Features", [])
        ]
        
        return any(indicators)

    def _add_to_not_found_barcodes(self, product_data: Dict) -> None:
     """Add a product to the not_found_barcodes.json file."""
     barcode = product_data['Barcode']
     not_found_file = os.path.join(self.output_dir, NOT_FOUND_BARCODES_FILE)
     not_found_data = []
    
     # Load existing not found data if available
     if os.path.exists(not_found_file):
        try:
            with open(not_found_file, 'r') as f:
                not_found_data = json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"Could not parse existing not found file, starting fresh")
    
     # Check if barcode already exists in the list
     existing_index = None
     for i, item in enumerate(not_found_data):
        if item.get('barcode') == barcode:
            existing_index = i
            break
    
     # Create entry
     timestamp = product_data.get('Timestamp')
     if existing_index is not None:
        # Update existing entry
        not_found_data[existing_index]['attempts'] = not_found_data[existing_index].get('attempts', 0) + 1
        not_found_data[existing_index]['last_attempt'] = timestamp
     else:
        # Add new entry
        not_found_data.append({
            'barcode': barcode,
            'attempts': 1,
            'first_attempt': timestamp,
            'last_attempt': timestamp,
            'reasons': ["No product data found"]
        })
    
     # Save updated list
     with open(not_found_file, 'w') as f:
        json.dump(not_found_data, f, indent=2)
    
     logger.info(f"Added product with barcode {barcode} to {NOT_FOUND_BARCODES_FILE}")
    
    def display_last_processed_item(self):
        """Display the last processed item in the terminal."""
        if self.last_processed_item:
            print("\n" + "="*80)
            print(f"LAST PROCESSED ITEM: {self.last_processed_item.get('Product Name', '')}")
            print("="*80)
            print(json.dumps(self.last_processed_item, indent=2))
            print("="*80 + "\n")
        else:
            print("\nNo items processed yet.\n")
    
    def display_processing_summary(self):
        """Display a summary of processing results."""
        stats = self.get_processing_stats()
        
        print("\n" + "="*80)
        print(f"PROCESSING SUMMARY:")
        print(f"Valid barcodes: {stats['valid_barcodes']}")
        print(f"Invalid barcodes: {stats['invalid_barcodes']}")
        print(f"Successfully processed: {stats['processed_items']}")
        
        print(f"AI Service Status:")
        print(f"  Gemini (Primary): {'Working' if self.ai_service_status['gemini']['working'] else 'Disabled'} " +
              f"(Failures: {self.ai_service_status['gemini']['failures']})")
        print(f"  OpenAI (Backup 1): {'Working' if self.ai_service_status['openai']['working'] else 'Disabled'} " +
              f"(Failures: {self.ai_service_status['openai']['failures']})")
        print(f"  DeepSeek (Backup 2): {'Working' if self.ai_service_status['deepseek']['working'] else 'Disabled'} " +
              f"(Failures: {self.ai_service_status['deepseek']['failures']})")
        
        if self.single_file:
            print(f"Output file: {self.single_file_path}")
            print(f"Total products in file: {len(self.all_products)}")
            
        if self.stop_requested:
            print(f"Status: Processing stopped by user")
            print(f"Remaining: {stats['valid_barcodes'] - stats['processed_items']} barcodes not processed")
        else:
            print(f"Status: Processing complete")
        print("="*80)
    
    def get_processing_stats(self):
        """Get processing statistics."""
        return {
            "valid_barcodes": len(self.valid_barcodes),
            "invalid_barcodes": len(self.invalid_barcodes),
            "processed_items": len(self.processed_barcodes)
        }


def main():
     """Main function to process barcodes from an Excel file."""
     import sys
    
     # Check if Excel file is provided
     if len(sys.argv) < 2:
        print(f"Usage: python {os.path.basename(sys.argv[0])} <path_to_barcode.xls> [output_json_path]")
        return
    
     excel_file = sys.argv[1]
    
     # Allow specifying output JSON file name
     output_file = SINGLE_OUTPUT_FILE
     if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
     # Get directory from output file path, default to "output" if none specified
     output_dir = os.path.dirname(output_file) or OUTPUT_DIR
    
     # Create processor and process barcodes
     processor = BarcodeProcessor(
        output_dir=output_dir,  
        single_file=True
     )
     processor.single_file_path = output_file
    
     try:
        valid_barcodes, invalid_barcodes = processor.process_excel_file(excel_file)
        
        # Display the last processed item
        processor.display_last_processed_item()
        
        print(f"\nAll product data saved to: {processor.single_file_path}")
        print(f"Total products in file: {len(processor.all_products)}")
        
     except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        # Still show stats if available
        processor.display_processing_summary()
        print(f"\nAll collected product data saved to: {processor.single_file_path}")


if __name__ == "__main__":
    # Setup signal handling for graceful interruption
    import signal
    
    processor = BarcodeProcessor(output_dir=OUTPUT_DIR)
    
    def handle_interrupt(sig, frame):
        processor.stop_requested = True
        print("\nInterrupt received. Completing current barcode and saving progress...")
    
    # Register the signal handler
    signal.signal(signal.SIGINT, handle_interrupt)
    
    # Get command line arguments
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: python {os.path.basename(sys.argv[0])} <excel_file> [output_file]")
        sys.exit(1)
        
    excel_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else SINGLE_OUTPUT_FILE
    
    # Process barcodes
    print(f"Processing barcodes from {excel_file}...")
    result = processor.process_barcodes_from_excel(excel_file)
    
    if result and isinstance(result, dict) and 'processed' in result:
      print(f"Processing completed: {result['processed']} barcodes processed, "
          f"{result['successful']} successful, {result['errors']} errors")
    else:
        print(f"Processing completed with errors. Please check logs.")
    print(f"Results saved to {output_file}")