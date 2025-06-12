import json
import csv
from collections import defaultdict

def get_productlines_and_products(data):
    """
    Extract unique productline with product counts and product names.
    
    Args:
        data: List of product dictionaries or single product dictionary
    
    Returns:
        Dictionary with productline, counts, and product lists
    """
    # Handle single product or list of products
    if isinstance(data, dict):
        products = [data]
    else:
        products = data
    
    # Dictionary to store products by ProductLine
    ProductLine_data = defaultdict(list)
    
    # Process each product
    for product in products:
        ProductLine = product.get('ProductLine', 'Unknown ProductLine')
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
        
        ProductLine_data[ProductLine].append(product_info)
    
    # Create final result with counts
    result = {}
    for ProductLine, product_list in ProductLine_data.items():
        # Sort products alphabetically by name
        sorted_products = sorted(product_list, key=lambda x: x['name'])
        result[ProductLine] = {
            'count': len(product_list),
            'products': sorted_products
        }
    
    return result

def print_productline_and_products(ProductLine_data):
    """Print productline with product counts and product names"""
    print("="*80)
    print("productline AND PRODUCTS ANALYSIS")
    print("="*80)
    
    # Sort productline by product count (descending)
    sorted_productline = sorted(ProductLine_data.items(), 
                              key=lambda x: x[1]['count'], reverse=True)
    
    total_productline = len(ProductLine_data)
    total_products = sum(data['count'] for data in ProductLine_data.values())
    
    print(f"\nSUMMARY:")
    print(f"Total Unique productline: {total_productline}")
    print(f"Total Products: {total_products}")
    print("\n" + "="*80)
    
    for ProductLine, data in sorted_productline:
        print(f"\n📁 ProductLine: {ProductLine}")
        print(f"   Number of Products: {data['count']}")
        print(f"   Products:")
        
        for i, product in enumerate(data['products'], 1):
            print(f"   {i:3d}. {product['name']} | Barcode: {product['barcode']}")
        
        print("-" * 80)

def save_results_to_csv(ProductLine_data, filename="ProductLine_products.csv"):
    """Save results to CSV file with proper structure including barcodes"""
    
    # Prepare data for CSV
    csv_data = []
    
    # Sort productline by product count (descending)
    sorted_productline = sorted(ProductLine_data.items(), 
                              key=lambda x: x[1]['count'], reverse=True)
    
    for ProductLine, data in sorted_productline:
        for i, product in enumerate(data['products'], 1):
            csv_data.append({
                'ProductLine': ProductLine,
                'Product_Count_In_ProductLine': data['count'],
                'Product_Number': i,
                'Product_Name': product['name'],
                'Barcode': product['barcode']
            })
    
    # Write to CSV
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['ProductLine', 'Product_Count_In_ProductLine', 'Product_Number', 'Product_Name', 'Barcode']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(csv_data)
    
    print(f"Results saved to {filename}")

def save_summary_csv(ProductLine_data, filename="ProductLine_summary.csv"):
    """Save ProductLine summary to CSV file"""
    
    # Sort productline by product count (descending)
    sorted_productline = sorted(ProductLine_data.items(), 
                              key=lambda x: x[1]['count'], reverse=True)
    
    # Prepare summary data
    summary_data = []
    for ProductLine, data in sorted_productline:
        # Get first 3 products as sample with their barcodes
        sample_products = []
        for product in data['products'][:3]:
            sample_products.append(f"{product['name']} ({product['barcode']})")
        
        summary_data.append({
            'ProductLine': ProductLine,
            'Product_Count': data['count'],
            'Sample_Products': ', '.join(sample_products)
        })
    
    # Write summary CSV
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['ProductLine', 'Product_Count', 'Sample_Products']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(summary_data)
    
    print(f"ProductLine summary saved to {filename}")

def save_results_to_json(ProductLine_data, filename="ProductLine_products.json"):
    """Save results to JSON file"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(ProductLine_data, f, indent=2, ensure_ascii=False)
    print(f"Results saved to {filename}")



# Main function
def main():
    
    try:
        with open('output/output.json', 'r', encoding='utf-8') as f:
            products_data = json.load(f)
        print("Loaded data from json")
        # Get productline and products
        print("Processing product data...")
        ProductLine_data = get_productlines_and_products(products_data)
        # Display results
        print_productline_and_products(ProductLine_data)
    
        # Save results
        save_results_to_json(ProductLine_data)
        save_results_to_csv(ProductLine_data)  # Added CSV export
        save_summary_csv(ProductLine_data)     # Added summary CSV export
    
        return ProductLine_data
    except FileNotFoundError:
        print("products.json not found. Using sample data.")
      
    
    
   

# Quick function for direct use
def analyze_my_products(products_data):
    """
    Quick function to analyze your product data directly
    
    Usage:
    result = analyze_my_products(your_product_list)
    """
    ProductLine_data = get_productline_and_products(products_data)
    print_productlines_and_products(ProductLine_data)
    return ProductLine_data

if __name__ == "__main__":
    main()