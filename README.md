# TestGen API - Simplified

A streamlined FastAPI service for generating educational test banks using AWS Claude and OpenSearch with dynamic index selection based on book titles.

## Overview

This simplified version consolidates the original multi-file architecture into a single, easy-to-understand application. It generates test banks with multiple-choice questions, true/false questions, and essay questions based on chapter content retrieved from OpenSearch. The API now supports multiple books by dynamically selecting the correct OpenSearch index based on the book title.

## Features

- **Single File Architecture**: All functionality consolidated into `app.py`
- **Dynamic Index Selection**: Automatically selects the correct OpenSearch index based on book title
- **AWS Integration**: Uses AWS Bedrock (Claude) for LLM and OpenSearch for content retrieval
- **Multiple Book Support**: Supports different textbooks with separate indices
- **Flexible Question Generation**: Supports MCQ, True/False, and Essay questions
- **Learning Objectives Integration**: Maps questions to specific learning objectives
- **File Saving**: Automatically saves generated test banks as JSON files
- **RESTful API**: Clean FastAPI endpoints with automatic documentation

## Quick Start

### Prerequisites

- Python 3.8+
- AWS credentials configured for the "cengage" profile
- Access to AWS Bedrock and OpenSearch services

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/ismanish/testgen-simplified.git
   cd testgen-simplified
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python app.py
   ```

4. Test the functionality:
   ```bash
   python example_usage.py
   ```

### Docker Deployment

1. Build and run with Docker Compose:
   ```bash
   docker-compose up --build
   ```

2. The API will be available at `http://localhost:8000`

## Supported Books

The API currently supports the following books (configured in `index_map.py`):

| Book Title | OpenSearch Index |
|------------|------------------|
| "An Invitation to Health" | `chunk_357973585` |
| "Steps to writing well" | `chunk_1337899796` |

To add more books, simply update the `index_map` dictionary in `index_map.py`.

## API Endpoints

### List Available Titles
`GET /api/v1/titles/`

Get all available book titles and their corresponding indices.

**Response:**
```json
{
  "available_titles": [
    {
      "title": "An Invitation to Health",
      "index": "chunk_357973585"
    },
    {
      "title": "Steps to writing well", 
      "index": "chunk_1337899796"
    }
  ],
  "total_titles": 2
}
```

### Generate Test Bank
`POST /api/v1/test-bank/generate/`

Generate a test bank for a specific chapter from a specific book.

**Request Body:**
```json
{
  "title": "An Invitation to Health",
  "chapter_name": "Chapter 1 Taking Charge of Your Health",
  "learning_objectives": {
    "LO1": "Define health and wellness.",
    "LO2": "Outline the dimensions of health."
  },
  "num_total_qs": 20,
  "num_mcq_qs": 15,
  "num_tf_qs": 3,
  "num_args_qs": 2,
  "save_to_file": true
}
```

**Response:**
```json
{
  "title": "An Invitation to Health",
  "chapter": "Chapter 1 Taking Charge of Your Health",
  "questions": [...],
  "index_used": "chunk_357973585",
  "file_saved": true,
  "saved_file": "./output/an_invitation_to_health_chapter_1_test_bank_20241204_143052.json"
}
```

### List Chapters
`GET /api/v1/chapters/?title=An Invitation to Health`

Retrieve available chapters from the OpenSearch index for a specific book.

**Parameters:**
- `title` (query parameter): Book title (defaults to "An Invitation to Health")

**Response:**
```json
{
  "title": "An Invitation to Health",
  "index_used": "chunk_357973585",
  "chapters": [
    {
      "name": "Chapter 1 Taking Charge of Your Health",
      "doc_count": 45
    }
  ],
  "total_chapters": 1
}
```

### List Saved Files
`GET /api/v1/files/`

List all previously generated test bank files.

### Health Check
`GET /health`

Check service health status.

## Dynamic Index Selection

The API uses the `index_map.py` file to map book titles to their corresponding OpenSearch indices:

```python
# index_map.py
index_map = {
    "An Invitation to Health": "chunk_357973585",
    "Steps to writing well": "chunk_1337899796"
}
```

**How it works:**
1. API receives a request with a book title
2. System looks up the title in `index_map.py`
3. Correct OpenSearch index is selected automatically
4. Content is retrieved from the appropriate index
5. Test bank is generated using the correct content

## File Saving

The API automatically saves generated test banks as JSON files in the `./output` directory:

- **Default Location**: `./output/`
- **Filename Format**: `{title}_{chapter}_{timestamp}.json`
- **File Structure**: Complete test bank with questions, answers, and metadata

Example saved file: `an_invitation_to_health_chapter_1_test_bank_20241204_143052.json`

## Configuration

The application uses embedded configuration in `app.py`. Key settings:

- **OpenSearch**: Host, region (index determined dynamically by title)
- **AWS Bedrock**: Claude model ARN and token limits
- **AWS Profile**: Uses "cengage" profile for authentication
- **Index Mapping**: Configured in `index_map.py`

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Architecture

The simplified architecture includes:

1. **FastAPI Application**: Main web framework
2. **Index Mapping**: Dynamic index selection based on book titles
3. **OpenSearch Service**: Content retrieval from vector database
4. **LLM Service**: Claude integration for question generation
5. **File Service**: JSON file saving and management
6. **Pydantic Models**: Request/response validation

## Example Usage

### Programmatic Usage

```python
import requests

# List available book titles
titles_response = requests.get("http://localhost:8000/api/v1/titles/")
titles = titles_response.json()
print(f"Available titles: {[t['title'] for t in titles['available_titles']]}")

# Generate test bank for a specific book
response = requests.post(
    "http://localhost:8000/api/v1/test-bank/generate/",
    json={
        "title": "An Invitation to Health",
        "chapter_name": "Chapter 1 Taking Charge of Your Health",
        "num_total_qs": 10,
        "num_mcq_qs": 7,
        "num_tf_qs": 2,
        "num_args_qs": 1,
        "save_to_file": True
    }
)

test_bank = response.json()
print(f"Used index: {test_bank['index_used']}")
print(f"Generated {len(test_bank['questions'])} questions")
print(f"Saved to: {test_bank.get('saved_file', 'Not saved')}")

# List chapters for a specific book
chapters_response = requests.get(
    "http://localhost:8000/api/v1/chapters/",
    params={"title": "Steps to writing well"}
)
chapters = chapters_response.json()
print(f"Chapters in '{chapters['title']}': {len(chapters['chapters'])}")
```

### Using the Example Script

```bash
# Run the comprehensive example
python example_usage.py
```

This will:
1. Check API health
2. List available book titles
3. Test generating test banks for different books
4. Save files and list them

## Adding New Books

To add support for a new book:

1. **Update `index_map.py`**:
   ```python
   index_map = {
       "An Invitation to Health": "chunk_357973585",
       "Steps to writing well": "chunk_1337899796",
       "Your New Book Title": "chunk_newindex123"  # Add this line
   }
   ```

2. **Restart the API** - changes take effect immediately

3. **Test the new book**:
   ```bash
   curl -X GET "http://localhost:8000/api/v1/titles/"
   ```

## Error Handling

The API includes comprehensive error handling for:
- Unsupported book titles (returns available titles)
- Invalid chapter names for specific books
- OpenSearch connection issues
- LLM generation errors
- Request validation errors
- File saving errors (non-blocking)

## File Management

Generated files are stored in the `./output` directory with:
- **Unique timestamps** to prevent overwrites
- **Descriptive filenames** based on title and chapter
- **Complete test bank data** including metadata
- **UTF-8 encoding** for international characters

## Development

For development with auto-reload:
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

## Directory Structure

```
testgen-simplified/
├── app.py                 # Main application file
├── index_map.py           # Book title to index mapping
├── requirements.txt       # Python dependencies
├── example_usage.py       # Example usage script
├── Dockerfile            # Container configuration
├── docker-compose.yml    # Deployment orchestration
├── README.md             # This file
├── .gitignore           # Git ignore rules
└── output/              # Generated test bank files (created automatically)
    ├── test_bank_1.json
    ├── test_bank_2.json
    └── ...
```

## License

MIT License
