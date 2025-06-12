import json
import csv
from collections import defaultdict

def get_categories_and_products(data):
    """
    Extract unique categories with product counts and product names.
    
    Args:
        data: List of product dictionaries or single product dictionary
    
    Returns:
        Dictionary with categories, counts, and product lists
    """
    # Handle single product or list of products
    if isinstance(data, dict):
        products = [data]
    else:
        products = data
    
    # Dictionary to store products by category
    category_data = defaultdict(list)
    
    # Process each product
    for product in products:
        category = product.get('Category', 'Unknown Category')
        product_name = product.get('Product Name', 'Unknown Product')
        barcode = product.get('Barcode', 'No Barcode')
        brand = product.get('Brand', '')
        
        # Create full product identifier
        full_product_name = f"{brand} {product_name}".strip() if brand else product_name
        
        # Store product with barcode information
        product_info = {
            'name': full_product_name,
            'barcode': barcode
        }
        
        category_data[category].append(product_info)
    
    # Create final result with counts
    result = {}
    for category, product_list in category_data.items():
        # Sort products alphabetically by name
        sorted_products = sorted(product_list, key=lambda x: x['name'])
        result[category] = {
            'count': len(product_list),
            'products': sorted_products
        }
    
    return result

def print_categories_and_products(category_data):
    """Print categories with product counts and product names"""
    print("="*80)
    print("CATEGORIES AND PRODUCTS ANALYSIS")
    print("="*80)
    
    # Sort categories by product count (descending)
    sorted_categories = sorted(category_data.items(), 
                              key=lambda x: x[1]['count'], reverse=True)
    
    total_categories = len(category_data)
    total_products = sum(data['count'] for data in category_data.values())
    
    print(f"\nSUMMARY:")
    print(f"Total Unique Categories: {total_categories}")
    print(f"Total Products: {total_products}")
    print("\n" + "="*80)
    
    for category, data in sorted_categories:
        print(f"\n📁 CATEGORY: {category}")
        print(f"   Number of Products: {data['count']}")
        print(f"   Products:")
        
        for i, product in enumerate(data['products'], 1):
            print(f"   {i:3d}. {product['name']} | Barcode: {product['barcode']}")
        
        print("-" * 80)

def save_results_to_csv(category_data, filename="category_products.csv"):
    """Save results to CSV file with proper structure including barcodes"""
    
    # Prepare data for CSV
    csv_data = []
    
    # Sort categories by product count (descending)
    sorted_categories = sorted(category_data.items(), 
                              key=lambda x: x[1]['count'], reverse=True)
    
    for category, data in sorted_categories:
        for i, product in enumerate(data['products'], 1):
            csv_data.append({
                'Category': category,
                'Product_Count_In_Category': data['count'],
                'Product_Number': i,
                'Product_Name': product['name'],
                'Barcode': product['barcode']
            })
    
    # Write to CSV
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Category', 'Product_Count_In_Category', 'Product_Number', 'Product_Name', 'Barcode']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(csv_data)
    
    print(f"Results saved to {filename}")

def save_summary_csv(category_data, filename="category_summary.csv"):
    """Save category summary to CSV file"""
    
    # Sort categories by product count (descending)
    sorted_categories = sorted(category_data.items(), 
                              key=lambda x: x[1]['count'], reverse=True)
    
    # Prepare summary data
    summary_data = []
    for category, data in sorted_categories:
        # Get first 3 products as sample with their barcodes
        sample_products = []
        for product in data['products'][:3]:
            sample_products.append(f"{product['name']} ({product['barcode']})")
        
        summary_data.append({
            'Category': category,
            'Product_Count': data['count'],
            'Sample_Products': ', '.join(sample_products)
        })
    
    # Write summary CSV
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Category', 'Product_Count', 'Sample_Products']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(summary_data)
    
    print(f"Category summary saved to {filename}")

def save_results_to_json(category_data, filename="category_products.json"):
    """Save results to JSON file"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(category_data, f, indent=2, ensure_ascii=False)
    print(f"Results saved to {filename}")



# Main function
def main():
    
    try:
        with open('output/output.json', 'r', encoding='utf-8') as f:
            products_data = json.load(f)
        print("Loaded data from json")
        # Get categories and products
        print("Processing product data...")
        category_data = get_categories_and_products(products_data)
        # Display results
        print_categories_and_products(category_data)
    
        # Save results
        save_results_to_json(category_data)
        save_results_to_csv(category_data)  # Added CSV export
        save_summary_csv(category_data)     # Added summary CSV export
    
        return category_data
    except FileNotFoundError:
        print("products.json not found. Using sample data.")
      
    
    
   

# Quick function for direct use
def analyze_my_products(products_data):
    """
    Quick function to analyze your product data directly
    
    Usage:
    result = analyze_my_products(your_product_list)
    """
    category_data = get_categories_and_products(products_data)
    print_categories_and_products(category_data)
    return category_data

if __name__ == "__main__":
    main()