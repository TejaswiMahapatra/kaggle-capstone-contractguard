# ContractGuard AI - Frontend

A modern web interface for the ContractGuard AI contract intelligence platform.

## Overview

The frontend is a **single-page application** built with:
- **Alpine.js** - Reactive UI framework
- **Tailwind CSS** - Utility-first styling
- **Font Awesome** - Icons

No build step required - all dependencies loaded via CDN.

## Quick Start

The frontend is **automatically served** by the FastAPI backend:

```bash
# Start the server
make dev

# Open in browser
open http://localhost:8000/
```

That's it! The frontend is served at the root URL.

## Features

### 📤 Document Upload
- Drag & drop PDF files
- Click to browse
- Progress indication
- Success/error feedback

### 💬 Chat Interface
- Natural language Q&A
- Message history
- Typing indicators
- Markdown formatting

### ⚡ Quick Actions
| Button | Function |
|--------|----------|
| Analyze Risks | Identify potential legal/financial risks |
| Executive Summary | Generate a high-level overview |
| Termination Terms | Extract termination conditions |
| List Obligations | Enumerate party responsibilities |

### 📁 Document Management
- View uploaded documents
- Select documents for context
- See document status

### 🔗 Session Support
- Maintains conversation context
- Create new sessions
- Session ID display

## File Structure

```
frontend/
├── templates/
│   └── index.html    # Main application (single-page)
├── static/
│   └── .gitkeep      # For custom static assets
└── README.md         # This file
```

## API Integration

The frontend communicates with these backend endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Connection status |
| `/api/v1/sessions` | POST | Create session |
| `/api/v1/documents` | GET | List documents |
| `/api/v1/documents/upload` | POST | Upload PDF |
| `/api/v1/query` | POST | Ask questions |

## Customization

### Change API URL

For development with a separate backend, edit `index.html`:

```javascript
const API_BASE = 'http://localhost:8000';  // Your API URL
```

### Styling

Tailwind CSS classes can be modified directly in the HTML. For custom styles, add to the `<style>` section.

### Adding Features

The Alpine.js component `contractGuard()` contains all application logic. Key methods:

```javascript
// Upload a document
uploadDocument()

// Send a chat message
sendMessage()

// Load document list
loadDocuments()

// Create new session
createSession()
```

## Development

### Running Standalone (for development)

If you need to run the frontend separately:

```bash
# Using Python's built-in server
cd frontend
python -m http.server 3000

# Then set API_BASE in index.html:
const API_BASE = 'http://localhost:8000';

# Open http://localhost:3000/templates/index.html
```

### Using VS Code Live Server

1. Install "Live Server" extension
2. Right-click `index.html` → "Open with Live Server"
3. Update `API_BASE` to point to your API

## Browser Support

Works in all modern browsers:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Frontend Testing Guide

Complete end-to-end testing workflow using the Web UI:

### Prerequisites

```bash
# 1. Start infrastructure
make docker-up

# 2. Wait ~30 seconds for services to initialize

# 3. Run database migrations
make db-upgrade

# 4. Start the API server
make dev

# 5. Verify all services
make health
```

### Step-by-Step Testing

#### Step 1: Open the Web UI
Open http://localhost:8000/ in your browser. You should see:
- "Connected" status (green indicator)
- Upload area for documents
- Empty document list
- Chat interface

#### Step 2: Upload a Document
```bash
# First, create a sample PDF (if needed)
make upload-sample  # This creates examples/contracts/sample_nda.pdf
```

Then in the Web UI:
1. Drag & drop the PDF into the upload area (or click to browse)
2. Wait for "Document uploaded successfully!" message
3. The document should appear in the Documents list

#### Step 3: Test Queries

Try these questions in the chat:

| Query | Expected Response |
|-------|-------------------|
| "What is the confidentiality period?" | 5 years |
| "What is the liability cap?" | $500,000 |
| "Who are the parties?" | TechCorp Industries + Receiving Party |
| "What are the termination conditions?" | 30 days notice |

#### Step 4: Test Quick Actions

Click each Quick Action button:
- **Analyze Risks** - Should identify liability, jurisdiction issues
- **Executive Summary** - Should provide contract overview
- **Termination Terms** - Should extract termination clauses
- **List Obligations** - Should enumerate responsibilities

#### Step 5: Test Document Selection

1. Click on a document in the Documents list
2. The document should highlight
3. A message should appear with document details

### Browser DevTools Testing

Open Developer Tools (F12) and check:

**Console Tab:**
- No JavaScript errors
- API calls completing successfully

**Network Tab:**
- `/health` returning 200
- `/api/v1/documents` returning document list
- `/api/v1/query` returning responses

---

## Troubleshooting

### "Disconnected" Status
- Check if the API server is running (`make dev`)
- Verify http://localhost:8000/health returns OK

### Upload Fails
- Ensure file is a PDF
- Check file size (default limit: 10MB)
- Verify MinIO is running (`make health`)

### No Response from Chat
- Check API server logs for errors
- Verify GOOGLE_API_KEY is set in `.env`
- Try refreshing the page (creates new session)

### Documents Not Loading
- Check if any documents have been uploaded
- Verify Weaviate is running
- Check browser console for errors
