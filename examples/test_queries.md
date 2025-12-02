# Test Queries for ContractGuard AI

This document contains test queries to validate the ContractGuard AI system's capabilities.

## Quick Start Testing

### 1. Basic Health Check
```bash
# Check system health
curl http://localhost:8000/health

# Expected: {"status": "healthy", "services": {...}}
```

### 2. Upload a Document
```bash
# Upload sample NDA
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@examples/contracts/sample_nda.pdf" \
  -F "collection_name=contracts"

# Expected: {"document_id": "uuid", "chunks": N, "message": "success"}
```

---

## Search Queries

### Basic Search
| Query | Expected Behavior |
|-------|-------------------|
| "What is the confidentiality period?" | Find term/survival clauses |
| "termination notice" | Find 30-day notice requirement |
| "liability cap" | Find $500,000 limitation |
| "intellectual property" | Find IP ownership clause |

### Semantic Search Examples
```bash
# Simple clause search
curl -X POST "http://localhost:8000/api/v1/search" \
  -F "query=termination clauses" \
  -F "top_k=5"

# Document-specific search
curl -X POST "http://localhost:8000/api/v1/search" \
  -F "query=payment terms" \
  -F "document_id=YOUR_DOC_ID"
```

---

## Agent Query Tests

### RAG Agent (Information Retrieval)
```json
{
  "question": "What constitutes Confidential Information under this NDA?"
}
```
**Expected:** List of items from Section 1.1 (trade secrets, business plans, etc.)

```json
{
  "question": "What are the obligations of the receiving party?"
}
```
**Expected:** Summary of Section 2 obligations

### Risk Agent (Risk Analysis)
```json
{
  "question": "What are the main risks in this NDA?"
}
```
**Expected:**
- Liability cap of $500,000
- 5-year survival period
- Injunctive relief clause
- Delaware jurisdiction

```json
{
  "question": "Analyze the liability exposure in this agreement"
}
```
**Expected:** Analysis of Section 6 with risk ratings

### Compare Agent (Contract Comparison)
```json
{
  "question": "Compare the termination clauses between document A and B"
}
```
**Expected:** Side-by-side comparison of termination terms

### Report Agent (Report Generation)
```json
{
  "question": "Generate an executive summary of this NDA"
}
```
**Expected:**
- Parties involved
- Key terms (3-year term, 5-year survival)
- Main obligations
- Risk highlights

---

## Advanced Queries

### Multi-Step Analysis
```json
{
  "question": "Find the termination clauses, analyze their risks, and provide recommendations"
}
```
**Expected:**
1. RAG finds termination clauses
2. Risk agent assesses exposure
3. Recommendations provided

### Complex Legal Queries
```json
{
  "question": "Are there any one-sided clauses that favor the disclosing party?"
}
```
**Expected:** Analysis of asymmetric provisions

```json
{
  "question": "What happens if I'm legally required to disclose confidential information?"
}
```
**Expected:** Reference to Section 2.3 Required Disclosure

---

## Long-Running Task Tests

### Create Analysis Task
```bash
# Create task
curl -X POST "http://localhost:8000/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "contract_analysis",
    "input_data": {
      "document_id": "YOUR_DOC_ID",
      "query": "Comprehensive risk analysis"
    }
  }'

# Execute task
curl -X POST "http://localhost:8000/api/v1/tasks/TASK_ID/execute"

# Check status
curl "http://localhost:8000/api/v1/tasks/TASK_ID"

# Pause task
curl -X POST "http://localhost:8000/api/v1/tasks/TASK_ID/pause"

# Resume task
curl -X POST "http://localhost:8000/api/v1/tasks/TASK_ID/resume"
```

---

## A2A Protocol Tests

### Discover Agent Card
```bash
curl http://localhost:8000/a2a/.well-known/agent.json
```

### Submit A2A Task
```bash
curl -X POST "http://localhost:8000/a2a/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "skillId": "contract_search",
    "input": {
      "query": "confidentiality terms",
      "top_k": 5
    }
  }'
```

---

## MCP Tool Tests

### List Available Tools
```bash
curl http://localhost:8000/mcp/tools
```

### Call MCP Tool
```bash
curl -X POST "http://localhost:8000/mcp/tools/search_contracts" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "payment obligations",
    "top_k": 3
  }'
```

---

## Evaluation Tests

### Run Quick Test Suite
```bash
curl -X POST "http://localhost:8000/api/v1/evaluation/suite" \
  -H "Content-Type: application/json" \
  -d '{"suite_name": "quick"}'
```

### Evaluate Single Prompt
```bash
curl -X POST "http://localhost:8000/api/v1/evaluation/evaluate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is the liability cap?",
    "expected_output": "$500,000"
  }'
```

### Get Aggregate Metrics
```bash
curl http://localhost:8000/api/v1/evaluation/metrics
```

---

## WebSocket Tests

### Connect to Document Progress
```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/document/DOC_ID');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`${data.message} (${data.progress}%)`);
};
```

### Connect to Task Updates
```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/task/TASK_ID');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`Status: ${data.status}, Progress: ${data.progress.percentage}%`);
};
```

---

## Edge Case Tests

### Off-Topic Query (Should Redirect)
```json
{
  "question": "What is the weather today?"
}
```
**Expected:** Redirect to contract-related queries

### Ambiguous Query
```json
{
  "question": "Tell me about the contract"
}
```
**Expected:** Ask for clarification or provide overview

### Missing Document
```bash
curl "http://localhost:8000/api/v1/documents/nonexistent-id"
```
**Expected:** 404 with appropriate error message

---

## Performance Benchmarks

| Operation | Target Latency | Acceptable |
|-----------|---------------|------------|
| Health check | < 50ms | < 200ms |
| Vector search | < 200ms | < 500ms |
| Agent query | < 5s | < 15s |
| Document upload (10 pages) | < 10s | < 30s |
| Full analysis | < 30s | < 60s |

---

## Checklist for Testing

- [ ] System health check passes
- [ ] Document upload works
- [ ] Basic search returns results
- [ ] RAG agent answers questions
- [ ] Risk analysis identifies issues
- [ ] Comparison works with multiple docs
- [ ] Reports generate correctly
- [ ] Long-running tasks pause/resume
- [ ] WebSocket receives updates
- [ ] A2A endpoints respond
- [ ] MCP tools are callable
- [ ] Evaluation suite passes
