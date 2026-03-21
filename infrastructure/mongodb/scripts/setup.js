// Medicine database setup with vector search indexes
// Run with: mongosh "mongodb://user:pass@localhost:27017?directConnection=true" < setup.js

// Switch to document_qa database
db = db.getSiblingDB('document_qa');

// Vector search index for hybrid search
db.medicine.createSearchIndex(
  "hybrid-vector-search",
  "vectorSearch",
  {
    fields: [
      {
        type: "vector",
        path: "search_vector",
        numDimensions: 1024,
        similarity: "dotProduct"
      }
    ]
  }
);

// Full-text search index
db.medicine.createSearchIndex(
  "hybrid-full-text-search",
  {
    mappings: {
      dynamic: false,
      fields: {
        name: {
          type: "string"
        }
      }
    }
  }
);

// Add custom analyzer with stopwords
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
              "Ointment", "Nasal", "Suppository", "Infusion"
            ]
          }
        ]
      }
    ]
  }
);

print('Medicine search indexes created successfully');

// Verify indexes
print('\nB-tree indexes:');
printjson(db.medicine.getIndexes());

print('\nSearch indexes:');
printjson(db.medicine.getSearchIndexes());
