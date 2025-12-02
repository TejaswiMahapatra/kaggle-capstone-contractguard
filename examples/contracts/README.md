# Sample Contracts

This directory contains sample contracts for testing ContractGuard AI.

## Available Samples

### 1. sample_nda.md
A standard Non-Disclosure Agreement (NDA) with typical clauses including:
- Confidentiality definitions
- Disclosure restrictions
- Term and termination
- Return of materials

### 2. sample_msa.md
A Master Service Agreement (MSA) covering:
- Service descriptions
- Payment terms
- Intellectual property
- Liability limitations
- Termination conditions

### 3. sample_sow.md
A Statement of Work (SOW) with:
- Project scope
- Deliverables
- Timeline
- Acceptance criteria

## Using Sample Contracts

1. **Upload via API:**
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@sample_nda.pdf" \
  -F "collection_name=contracts"
```

2. **Convert markdown to PDF:**
```bash
# Using pandoc
pandoc sample_nda.md -o sample_nda.pdf
```

3. **Query the uploaded contract:**
```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the confidentiality period?"}'
```

## Creating Your Own Test Contracts

For best results, use contracts that include:
- Clear section headings (helps clause-aware chunking)
- Standard legal clauses
- Defined terms section
- Various clause types for comprehensive testing
