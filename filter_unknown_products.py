#!/usr/bin/env python3
"""
Clean Output Script - Remove Unknown Products from output.json
This script removes products with "Unknown Product" names from the original output.json
and saves them to output_not_found.json

Developed for: DataCarts
"""

import json
import os
import sys
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

def is_unknown_product(product_data):
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

def clean_output_file(input_filename):
    """
    Clean the output file by removing unknown products and saving them separately
    
    Args:
        input_filename (str): Path to the JSON file to clean
    """
    # Determine output filename for not found products
    base_dir = os.path.dirname(input_filename)
    base_name = os.path.basename(input_filename)
    not_found_filename = os.path.join(base_dir, base_name.replace('.json', '_not_found.json'))
    
    # Check if the input file exists
    if not os.path.exists(input_filename):
        logging.error(f"Input file not found: {input_filename}")
        return False
    
    try:
        # Load the data
        print(f"📁 Loading data from: {input_filename}")
        with open(input_filename, 'r', encoding='utf-8') as f:
            all_products = json.load(f)
        
        if not isinstance(all_products, list):
            logging.error(f"Input file {input_filename} does not contain a JSON array")
            return False
        
        print(f"📊 Total products loaded: {len(all_products)}")
        
        # Separate products
        found_products = []
        not_found_products = []
        
        for product in all_products:
            if is_unknown_product(product):
                not_found_products.append(product)
            else:
                found_products.append(product)
        
        print(f"🔍 Analysis complete:")
        print(f"   - Valid products: {len(found_products)}")
        print(f"   - Unknown products: {len(not_found_products)}")
        
        # Save not found products to separate file first
        print(f"💾 Saving unknown products to: {not_found_filename}")
        with open(not_found_filename, 'w', encoding='utf-8') as f:
            json.dump(not_found_products, f, indent=2, ensure_ascii=False)
        
        # Update the original file with only found products (removing unknown products)
        print(f"🧹 Cleaning original file: {input_filename}")
        with open(input_filename, 'w', encoding='utf-8') as f:
            json.dump(found_products, f, indent=2, ensure_ascii=False)
        
        # Also update the not_found_barcodes.json file
        update_not_found_barcodes(not_found_products)
        
        # Calculate percentages safely
        total = len(all_products)
        found_count = len(found_products)
        not_found_count = len(not_found_products)
        found_percentage = (found_count / total * 100) if total > 0 else 0
        not_found_percentage = (not_found_count / total * 100) if total > 0 else 0
        
        print(f"\n" + "="*60)
        print("✅ CLEANING COMPLETED SUCCESSFULLY")
        print("="*60)
        print(f"📈 Results Summary:")
        print(f"   Total products processed: {total}")
        print(f"   Products remaining in {os.path.basename(input_filename)}: {found_count} ({found_percentage:.1f}%)")
        print(f"   Products removed to {os.path.basename(not_found_filename)}: {not_found_count} ({not_found_percentage:.1f}%)")
        print(f"\n📂 Files updated:")
        print(f"   ✓ Original file (cleaned): {input_filename}")
        print(f"   ✓ Removed products saved: {not_found_filename}")
        print(f"   ✓ Barcode tracking: output/not_found_barcodes.json")
        print("="*60)
        
        logging.info(f"Successfully removed {not_found_count} unknown products from {input_filename}")
        
        return True
        
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON in input file: {input_filename}")
        return False
    except Exception as e:
        logging.error(f"Error processing file {input_filename}: {str(e)}")
        return False

def update_not_found_barcodes(not_found_products):
    """
    Update the not_found_barcodes.json file with the unknown products
    
    Args:
        not_found_products (list): List of products that were not found
    """
    not_found_file = "output/not_found_barcodes.json"
    not_found_data = []
    
    # Load existing not found data if available
    if os.path.exists(not_found_file):
        try:
            with open(not_found_file, 'r') as f:
                not_found_data = json.load(f)
        except json.JSONDecodeError:
            logging.warning(f"Could not parse existing not found file, starting fresh")
    
    # Track existing barcodes
    existing_barcodes = {item.get('barcode'): item for item in not_found_data}
    
    # Process each not found product
    for product in not_found_products:
        barcode = product.get('Barcode')
        if not barcode:
            continue
            
        if barcode in existing_barcodes:
            # Update existing entry
            existing_barcodes[barcode]['attempts'] = existing_barcodes[barcode].get('attempts', 0) + 1
            existing_barcodes[barcode]['last_attempt'] = product.get('Timestamp')
        else:
            # Add new entry
            not_found_data.append({
                'barcode': barcode,
                'attempts': 1,
                'first_attempt': product.get('Timestamp'),
                'last_attempt': product.get('Timestamp'),
                'reasons': ["No product data found"]
            })
    
    # Save updated list
    os.makedirs("output", exist_ok=True)
    with open(not_found_file, 'w') as f:
        json.dump(not_found_data, f, indent=2)
    
    logging.info(f"Updated not_found_barcodes.json with {len(not_found_products)} barcodes")

def main():
    """Main function to parse arguments and clean the output file"""
    
    print("🧹 Output File Cleaner - DataCarts")
    print("Removes 'Unknown Product' entries from output.json")
    print("-" * 50)
    
    # Default to output/output.json if no argument provided
    if len(sys.argv) < 2:
        input_filename = "output/output.json"
        print(f"📁 Using default file: {input_filename}")
    else:
        input_filename = sys.argv[1]
        print(f"📁 Using specified file: {input_filename}")
    
    # Check if file exists
    if not os.path.exists(input_filename):
        print(f"❌ File not found: {input_filename}")
        if len(sys.argv) < 2:
            print(f"💡 Make sure {input_filename} exists, or specify a different file:")
            print(f"   python3 {os.path.basename(sys.argv[0])} path/to/your/file.json")
        return
    
    print(f"⚠️  WARNING: This will modify {input_filename} and remove unknown products!")
    print(f"Unknown products will be saved to: {input_filename.replace('.json', '_not_found.json')}")
    
    # Ask for confirmation
    try:
        confirmation = input("\nDo you want to continue? (y/N): ").strip().lower()
        if confirmation not in ['y', 'yes']:
            print("❌ Operation cancelled.")
            return
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled.")
        return
    
    success = clean_output_file(input_filename)
    
    if not success:
        print("\n❌ Cleaning failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()