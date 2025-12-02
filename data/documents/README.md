# Contract Documents

This folder contains contract documents for ContractGuard AI analysis.

## Folder Structure

```
data/documents/
├── sample/              # Sample contracts for testing
│   ├── nda_sample.pdf
│   └── msa_sample.pdf
├── uploads/             # User uploaded documents (gitignored)
└── processed/           # Processed documents (gitignored)
```

## Sample Contracts Location

For testing, use contracts from:
- `examples/contracts/sample_nda.md` - Sample NDA
- `examples/contracts/sample_nda.pdf` - PDF version (generated)

## Upload Paths

When using the API, reference files relative to project root:

```bash
# Upload from examples folder
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@examples/contracts/sample_nda.pdf"

# Upload from data folder
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@data/documents/sample/your_contract.pdf"
```

## Supported Formats

- **PDF** (.pdf) - Primary format
- **Markdown** (.md) - For testing
- **Text** (.txt) - Plain text contracts

## Converting Markdown to PDF

```bash
# Install pandoc
brew install pandoc  # macOS
apt-get install pandoc  # Ubuntu

# Convert
pandoc examples/contracts/sample_nda.md -o data/documents/sample/sample_nda.pdf
```

## Notes

- `uploads/` and `processed/` folders are gitignored
- Documents uploaded via API are stored in MinIO
- Document metadata is stored in PostgreSQL
- Vector embeddings are stored in Weaviate
