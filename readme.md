# Barcode Product Data Processor

A robust enterprise-grade tool for scanning product barcodes and retrieving detailed information from multiple sources, with AI-powered data enhancement capabilities.

**Version:** 2.3.0  
**Last Updated:** 2025-05-30  
**Developed for:** DataCarts

## Overview

This comprehensive barcode processing solution enables businesses to efficiently gather, enhance, and standardize product information from multiple data sources. Built with enterprise reliability and scalability in mind, it integrates seamlessly with existing workflows and provides consistent, high-quality product data.

## Features

### Core Capabilities
- **Multi-Source Data Aggregation**: Intelligent querying across OpenFoodFacts, Google Search, and DigiTeyes API
- **AI-Powered Enhancement**: Advanced data enrichment using multiple AI services with automatic fallback
  - Google Gemini 1.5 Flash (Primary AI Engine)
  - OpenAI GPT-3.5 Turbo (Backup Service)
  - DeepSeek (Secondary Backup)
- **Enterprise-Grade Reliability**:
  - Intelligent local caching system for offline operation
  - Automatic retry mechanisms with exponential backoff
  - Graceful error handling and API failure recovery
  
### Smart Processing Features
- **Advanced Barcode Recognition**: Pattern recognition optimized for regional product codes
- **Intelligent Categorization**: Automatic category and subcategory inference
- **Data Standardization**: Auto-extraction and normalization of weight, volume, and specifications
- **Batch Processing**: Handle thousands of barcodes efficiently from Excel files
- **Resume Functionality**: Seamless continuation from interruption points

## System Requirements

- **Python Version**: 3.8 or higher
- **Dependencies**:
  - requests (HTTP client library)
  - pandas (Data manipulation and analysis)
  - openpyxl (Excel file processing)
  - python-dotenv (Environment variable management)
  - logging (Application logging)

## Installation Guide

### 1. Repository Setup
```bash
git clone <repository-url>
cd barcode-processor
```

### 2. Environment Configuration
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate     # Windows
```

### 3. Dependency Installation
```bash
pip install requests pandas openpyxl python-dotenv
```

### 4. Environment Variables Setup
```bash
cp env.example .env
# Configure your .env file with required API credentials
```

## Configuration

### API Configuration (.env file)

```env
# Google Custom Search API Configuration
GOOGLE_API_KEY=your_google_api_key
GOOGLE_SEARCH_CX=your_custom_search_engine_id

# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key

# Google Gemini API Configuration
GEMINI_API_KEY=your_gemini_api_key

# DeepSeek API Configuration
DEEPSEEK_API_KEY=your_deepseek_api_key

# DigiTeyes API Configuration
DIGITEYES_APP_KEY=your_digiteyes_app_key
DIGITEYES_SIGNATURE=your_digiteyes_signature

# Performance Configuration
API_REQUEST_DELAY=1.0
MAX_RETRIES=5
OPENFOODFACTS_URL=https://world.openfoodfacts.org/api/v0/product/
```

## Usage Instructions

### Standard Operation
Process barcodes from Excel file with default output:
```bash
python barcode_fetcher_extended.py input_barcodes.xls
```

### Custom Output Specification
```bash
python barcode_fetcher_extended.py input_barcodes.xls custom_output_name.json
```

### Batch Processing Management
The system supports safe interruption (Ctrl+C) and automatic resume functionality. Upon restart, it intelligently skips previously processed barcodes and continues from the interruption point.

## System Architecture

### Data Processing Pipeline

1. **Input Validation**
   - Excel file parsing and barcode extraction
   - Format validation (EAN-8, EAN-13, UPC-A, GTIN-14)
   - Duplicate detection and handling

2. **Multi-Source Data Retrieval**
   - Primary: OpenFoodFacts API (comprehensive food database)
   - Secondary: Google Custom Search API (broad product coverage)
   - Tertiary: DigiTeyes API (specialized product database)

3. **AI-Powered Data Enhancement**
   - Intelligent data enrichment and standardization
   - Multi-service fallback architecture
   - Consistent output formatting

4. **Quality Assurance & Output**
   - Data validation and error checking
   - Structured JSON output generation
   - Comprehensive logging and monitoring

### Error Handling & Resilience

- **Exponential Backoff**: Intelligent retry mechanisms for API rate limiting
- **Caching System**: Local storage for reducing redundant API calls
- **Pattern Matching**: Fallback product identification when APIs are unavailable
- **Graceful Degradation**: Partial data processing when services are limited

## Project Structure

```
barcode-processor/
├── barcode_fetcher_extended.py    # Main application logic
├── barcode.xls                    # Sample input file
├── output.json                    # Default output file
├── .env                          # Environment configuration
├── env.example                    # Configuration template
├── barcode_fetcher.log           # Application logs
├── output/                       # Output directory
│   └── cache/                    # API response cache
├── venv/                         # Python virtual environment
└── README.md                     # Project documentation
```

## Advanced Configuration

### Custom Pattern Recognition
Extend barcode recognition for specific product categories:

```python
self.barcode_category_patterns = {
    "2102163": {"category": "Household", "subcategory": "Cleaning"},
    "2102127": {"category": "Household", "subcategory": "Kitchen"},
    "2102160": {"category": "Food", "subcategory": "Oils"},
    # Add custom patterns as needed
}
```

### AI Prompt Customization
Tailor AI enhancement prompts for industry-specific requirements and data extraction needs.

## Performance Metrics

- **Processing Speed**: 3-10 seconds per barcode (API-dependent)
- **API Efficiency**: 1-3 API calls per barcode average
- **Scalability**: Optimized for datasets up to 10,000+ barcodes
- **Cache Hit Rate**: 85%+ for repeat processing

## Troubleshooting

### Common Issues

**API Authentication Errors**
- Verify all API keys in `.env` file
- Check API service status and quotas
- Ensure proper service account permissions

**Rate Limiting**
- Increase `API_REQUEST_DELAY` in configuration
- Monitor API usage against service limits
- Consider upgrading API plans for higher throughput

**Data Quality Issues**
- Validate barcode formats and checksums
- Clear cache for reprocessing specific items
- Review logs for specific error patterns

## Development Team

This project was developed as part of an internship program at **DataCarts** by:

- **Shanavasvb Asheer** 
  📧 shanavasvbasheer@gmail.com

- **Sumayya V N**  
  📧 suminoushad101@gmail.com

- **Aayisha OS** 
  📧 osaayisha314@gmail.com

## Company Information

**Developed for:** DataCarts  
**Project Type:** Internship Project  
**Development Period:** 2025  
**Version:** 2.3.0

## License

This project is proprietary software developed for DataCarts. All rights reserved.

## Support & Contact

For technical support, feature requests, or project inquiries, please contact the development team at the email addresses listed above.

---

*Engineered with precision for DataCarts • 2025*
