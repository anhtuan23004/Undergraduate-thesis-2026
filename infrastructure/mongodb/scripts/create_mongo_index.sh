# sudo apt-get install -y mongodb-mongosh
# brew install mongosh

# Connect
mongosh "mongodb://user:pass@localhost:27017?directConnection=true"


# Create medicine index
use document_qa

# Vector search index
db.medicine.createSearchIndex(
  "hybrid-vector-search",          // index name
  "vectorSearch",                  // index type
  {
    fields: [
      {
        type: "vector",
        path: "search_vector",
        numDimensions: 1024,       // must match your embedding size
        similarity: "dotProduct"   // or "cosine" / "euclidean"
      }
    ]
  }
);

# Full-text search index
db.medicine.createSearchIndex(
  "hybrid-full-text-search",   // index name
  {
    mappings: {
      dynamic: false,          // or true, if you want dynamic fields too
      fields: {
        name: {
          type: "string"
        }
      }
    }
  }
);

# Show B-tree indexes
db.medicine.getIndexes()

# Show search indexes
db.medicine.getSearchIndexes()

# Add stopwords to the full-text search index
db.medicine.updateSearchIndex(
  "hybrid-full-text-search",
  {
    "mappings": {
      "dynamic": false,
      "fields": {
        "name": {
          "type": "string",
          "analyzer": "medicine_analyzer"
        }
      }
    },
    "analyzers": [
      {
        "name": "medicine_analyzer",
        "charFilters": [],
        "tokenizer": {
          "type": "standard"
        },
        "tokenFilters": [
          {
            "type": "lowercase"
          },
          {
            "type": "stopword",
            "tokens": [
              "thuốc", "viên", "dịch", "nén", "dung", "uống", "tiêm", "bôi", 
              "nhỏ", "da", "mắt", "kem", "bột", "nang", "pha", "siro", 
              "hỗn", "cứng", "gel", "mỡ", "mũi", "plus", "đặt", "truyền", 
              "xịt", "sủi", "âm", "vitamin", "đạo", "ngoài", "-", "cốm", "Spray", 
              "Capsule", "Tablet", "Syrup", "Injection", "Cream", "Powder", 
              "Ointment", "Nasal", "Suppository", "Infusion",
            ]
          }
        ]
      }
    ]
  }
);

## Check
db.medicine.aggregate([
  {
    "$listSearchIndexes": {
      "name": "hybrid-full-text-search"
    }
  }
])