import json

# Load the JSON file
with open('output/output.json', 'r') as file:
    data = json.load(file)

# Count the number of documents
document_count = len(data)

print(f"Number of documents: {document_count}")