# TestGen API - Simplified

A streamlined FastAPI service for generating educational test banks using AWS Claude and OpenSearch.

## Overview

This simplified version consolidates the original multi-file architecture into a single, easy-to-understand application. It generates test banks with multiple-choice questions, true/false questions, and essay questions based on chapter content retrieved from OpenSearch.

## Features

- **Single File Architecture**: All functionality consolidated into `app.py`
- **AWS Integration**: Uses AWS Bedrock (Claude) for LLM and OpenSearch for content retrieval
- **Flexible Question Generation**: Supports MCQ, True/False, and Essay questions
- **Learning Objectives Integration**: Maps questions to specific learning objectives
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

### Docker Deployment

1. Build and run with Docker Compose:
   ```bash
   docker-compose up --build
   ```

2. The API will be available at `http://localhost:8000`

## API Endpoints

### Generate Test Bank
`POST /api/v1/test-bank/generate/`

Generate a test bank for a specific chapter.

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
  "num_args_qs": 2
}
```

### List Chapters
`GET /api/v1/chapters/`

Retrieve available chapters from the OpenSearch index.

### Health Check
`GET /health`

Check service health status.

## Configuration

The application uses embedded configuration in `app.py`. Key settings:

- **OpenSearch**: Host, region, and index configuration
- **AWS Bedrock**: Claude model ARN and token limits
- **AWS Profile**: Uses "cengage" profile for authentication

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Architecture

The simplified architecture includes:

1. **FastAPI Application**: Main web framework
2. **OpenSearch Service**: Content retrieval from vector database
3. **LLM Service**: Claude integration for question generation
4. **Pydantic Models**: Request/response validation

## Example Usage

```python
import requests

# Generate test bank
response = requests.post(
    "http://localhost:8000/api/v1/test-bank/generate/",
    json={
        "chapter_name": "Chapter 1 Taking Charge of Your Health",
        "num_total_qs": 10,
        "num_mcq_qs": 7,
        "num_tf_qs": 2,
        "num_args_qs": 1
    }
)

test_bank = response.json()
print(f"Generated {len(test_bank['questions'])} questions")
```

## Error Handling

The API includes comprehensive error handling for:
- Invalid chapter names
- OpenSearch connection issues
- LLM generation errors
- Request validation errors

## Development

For development with auto-reload:
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

## License

MIT License
