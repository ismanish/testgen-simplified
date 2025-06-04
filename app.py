import os
import re
import json
import uuid
import datetime
import boto3
from typing import Optional, Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from llama_index.llms.bedrock_converse import BedrockConverse
from llama_index.core import PromptTemplate

# Configuration
class Config:
    PROJECT_NAME: str = "TestGen API - Simplified"
    
    # OpenSearch settings
    OPENSEARCH_HOST: str = "https://64asp87vin20xc5bhvbf.us-east-1.aoss.amazonaws.com"
    OPENSEARCH_REGION: str = "us-east-1"
    OPENSEARCH_INDEX: str = "chunk_357973585"
    AWS_PROFILE_NAME: str = "cengage"
    
    # Chapter key (will be determined dynamically)
    CHAPTER_KEY: str = "toc_level_1_title"
    
    # Claude LLM settings
    LLM_MODEL: str = "arn:aws:bedrock:us-east-1:051826717360:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0"
    LLM_REGION: str = "us-east-1"
    LLM_MAX_TOKENS: int = 30000

config = Config()

# Pydantic Models
class TestBankOption(BaseModel):
    label: str
    text: str

class TestBankQuestion(BaseModel):
    id: str
    type: str
    learning_objective: Optional[str] = None
    question_text: str
    options: Optional[List[TestBankOption]] = None
    correct_answer: str
    rationale: str

class TestBankResponse(BaseModel):
    title: str
    chapter: str
    questions: List[TestBankQuestion]

# Default learning objectives
DEFAULT_LEARNING_OBJECTIVES = {
    "LO1": "Define health and wellness.",
    "LO2": "Outline the dimensions of health.",
    "LO3": "Assess the current health status of Americans",
    "LO4": "Discuss health disparities based on sex and race.",
    "LO5": "Evaluate the health behaviors of undergraduate students.",
    "LO6": "Describe the impact of habits formed in college on future health.",
    "LO7": "Evaluate health information for accuracy and reliability.",
    "LO8": "Explain the influences on behavior that support or impede healthy change.",
    "LO9": "Identify the stages of change.",
}

class TestBankRequest(BaseModel):
    title: str = Field(default="An Invitation to Health", description="The title of the book")
    chapter_name: str = Field(default="Chapter 1 Taking Charge of Your Health", description="The name of the chapter to generate questions for")
    learning_objectives: Dict[str, str] = Field(default=DEFAULT_LEARNING_OBJECTIVES, description="Dictionary of learning objectives")
    num_total_qs: int = Field(80, description="Total number of questions to generate")
    num_mcq_qs: int = Field(60, description="Number of multiple-choice questions to generate")
    num_tf_qs: int = Field(15, description="Number of true/false questions to generate")
    num_args_qs: int = Field(5, description="Number of argument questions to generate")
    max_chunks: int = Field(200, description="Maximum number of chunks to retrieve")
    max_chars: int = Field(100000, description="Maximum characters to include in content")

# FastAPI app initialization
app = FastAPI(
    title=config.PROJECT_NAME,
    description="Simplified API for generating educational test banks using Claude and OpenSearch",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenSearch Client
class OpenSearchService:
    def __init__(self):
        self._client = None
        self._chapter_key = config.CHAPTER_KEY

    @property
    def client(self):
        if not self._client:
            session = boto3.Session(profile_name=config.AWS_PROFILE_NAME)
            credentials = session.get_credentials()
            
            auth = AWSV4SignerAuth(credentials, config.OPENSEARCH_REGION, 'aoss')
            self._client = OpenSearch(
                hosts=[{'host': config.OPENSEARCH_HOST.replace('https://', ''), 'port': 443}],
                http_auth=auth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                pool_maxsize=20
            )
        return self._client
    
    def find_title_index(self, chapter_key):
        """Find all available chapter titles using the specified chapter key."""
        query = {
            "size": 0,
            "aggs": {
                "chapter_names": {
                    "terms": {
                        "field": f"metadata.source.metadata.{chapter_key}.keyword",
                        "size": 200
                    }
                }
            }
        }
        
        response = self.client.search(
            index=config.OPENSEARCH_INDEX,
            body=query
        )
        
        chapter_buckets = response.get('aggregations', {}).get('chapter_names', {}).get('buckets', [])
        return chapter_buckets

    def determine_chapter_key(self):
        """Determine which metadata field contains chapter information."""
        if 'chapter' in "".join([val['key'].lower() for val in self.find_title_index('toc_level_2_title')]):
            self._chapter_key = 'toc_level_2_title'
        else:
            self._chapter_key = 'toc_level_1_title'
        
        return self._chapter_key
    
    def retrieve_chapter_content(self, chapter_name: str, max_chunks: int = 200, max_chars: int = 100000):
        """Retrieve chapter content from OpenSearch."""
        if not chapter_name:
            raise ValueError("Chapter name must be provided.")
        
        # Determine the correct chapter key
        self.determine_chapter_key()
        
        # Create query
        query_body = {
            "query": {
                "term": {
                    f"metadata.source.metadata.{self._chapter_key}.keyword": chapter_name
                }
            },
            "sort": [
                { "metadata.source.metadata.pdf_page_number": "asc" },
                { "metadata.source.metadata.page_sequence": "asc" }
            ],
            "_source": {
                "excludes": ["embedding"]
            },
            "size": max_chunks
        }
        
        try:
            response = self.client.search(
                index=config.OPENSEARCH_INDEX,
                body=query_body
            )
        except Exception as e:
            raise Exception(f"Search error: {e}")
        
        hits = response['hits']['hits']
        total_hits = response['hits']['total']['value']
        
        if total_hits == 0:
            return ""
            
        chapter_text = ""
        for hit in hits:
            chapter_text += hit['_source']['value']
        
        # Limit content if it exceeds max_chars
        if len(chapter_text) > max_chars:
            chapter_text = chapter_text[:max_chars]
        
        return chapter_text

# LLM Service
class LLMService:
    def __init__(self):
        self._llm = None
        
    @property
    def llm(self):
        if not self._llm:
            self._llm = BedrockConverse(
                model=config.LLM_MODEL,
                profile_name=config.AWS_PROFILE_NAME,
                region_name=config.LLM_REGION,
                max_tokens=config.LLM_MAX_TOKENS,
            )
        return self._llm
    
    def strip_json_markers(self, json_string):
        """Strips triple backticks and 'json' from a JSON-formatted string."""
        pattern = r"```(?:json)?(.*?)```"
        matches = re.findall(pattern, json_string, re.DOTALL)
        
        if matches:
            return "".join(matches).strip()
        else:
            return json_string.strip()
    
    def generate_test_bank(self, prompt):
        """Generate a test bank using the LLM model."""
        try:
            response_deltas = []
            stream_response = self.llm.stream_complete(prompt)
            
            for r in stream_response:
                response_deltas.append(r.delta)
                
            full_response = "".join(response_deltas)
            clean_response = self.strip_json_markers(full_response)
            
            test_bank = json.loads(clean_response)
            return test_bank
            
        except Exception as e:
            raise Exception(f"Error during test bank generation: {e}")

# Prompt Template
TEST_BANK_PROMPT = """
You are an expert Test Bank Author creating high-quality educational assessment questions following Cengage publishing standards. Use only the provided source material to create questions that challenge students while maintaining academic rigor.

TASK OVERVIEW
Your task is to generate a comprehensive test bank that strictly adheres to the provided authoring guidelines and Cengage quality standards. You will not have access to any external resources, textbooks, or prior knowledge. All questions must be derived solely from the provided source material, which is a chapter from a textbook.
Create a total of {num_total_qs} questions, distributed as follows:
- {num_mcq_qs} Multiple-Choice Questions (MCQ)
- {num_tf_qs} True/False (T/F) Questions
- {num_args_qs} Argumentative Essay Questions

SOURCE MATERIAL
The source material for your questions is provided below. It contains the content of the chapter from which you will derive all questions. Do not reference any external materials or prior knowledge.
{chapter_content}

The learning objectives for this chapter are:
{learning_objectives}

Return ONLY the JSON in this exact format:
{{
    "title": "YOUR_TITLE_HERE",
    "chapter": "YOUR_CHAPTER_HERE",
    "questions": [
        {{
            "id": "1",
            "type": "multiple-choice",
            "learning_objective": "LO1",
            "question_text": "What is...",
            "options": [
                {{ "label": "A", "text": "Option text" }},
                {{ "label": "B", "text": "Option text" }},
                {{ "label": "C", "text": "Option text" }},
                {{ "label": "D", "text": "Option text" }}
            ],
            "correct_answer": "A",
            "rationale": "Explanation of why A is correct..."
        }},
        {{
            "id": "2",
            "type": "true-false",
            "learning_objective": "LO2",
            "question_text": "Statement to evaluate...",
            "correct_answer": "True",
            "rationale": "Explanation of why this is true..."
        }},
        {{
            "id": "3",
            "type": "argument",
            "learning_objective": "LO3",
            "question_text": "Analyze and evaluate...",
            "correct_answer": "The correct analysis...",
            "rationale": "Detailed explanation..."
        }}
    ]
}}

CRITICAL REQUIREMENTS:
1. All questions must be clear, unambiguous, and answerable from the provided content only
2. MCQs must have exactly 4 options with 1 correct answer
3. All question stems must end with a question mark
4. Provide rationale for each question explaining why the answer is correct
5. Map each question to appropriate learning objectives
6. Use inclusive, unbiased language
7. Create plausible distractors for MCQs that represent common misconceptions
"""

# Service Instances
opensearch_service = OpenSearchService()
llm_service = LLMService()

# API Endpoints
@app.get("/")
def read_root():
    return {"message": f"Welcome to {config.PROJECT_NAME}. Go to /docs for API documentation."}

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.datetime.utcnow().isoformat()}

@app.post("/api/v1/test-bank/generate/", response_model=TestBankResponse)
async def generate_test_bank(request: TestBankRequest):
    """
    Generate a test bank for a given chapter.
    
    This endpoint retrieves chapter content from OpenSearch, constructs a prompt
    with learning objectives, and uses Claude to generate structured test questions
    with answers and rationales.
    """
    try:
        print(f"Generating test bank for chapter: {request.chapter_name}")
        
        # Step 1: Retrieve chapter content from OpenSearch
        chapter_content = opensearch_service.retrieve_chapter_content(
            chapter_name=request.chapter_name,
            max_chunks=request.max_chunks,
            max_chars=request.max_chars
        )
        
        if not chapter_content:
            raise ValueError(f"No content found for chapter: {request.chapter_name}")
        
        print(f"Retrieved {len(chapter_content)} characters of content")
        
        # Step 2: Format learning objectives
        lo_formatted = "Learning Objectives:\n"
        for lo_id, lo_text in request.learning_objectives.items():
            lo_formatted += f"- {lo_id}: {lo_text}\n"
        
        # Step 3: Create prompt
        prompt = TEST_BANK_PROMPT.format(
            chapter_content=chapter_content,
            learning_objectives=lo_formatted,
            num_total_qs=request.num_total_qs,
            num_mcq_qs=request.num_mcq_qs,
            num_tf_qs=request.num_tf_qs,
            num_args_qs=request.num_args_qs
        )
        
        # Step 4: Generate test bank using LLM
        print("Sending prompt to Claude for test bank generation...")
        test_bank = llm_service.generate_test_bank(prompt)
        
        print(f"Generated test bank with {len(test_bank.get('questions', []))} questions")
        
        # Step 5: Return response
        return TestBankResponse(
            title=test_bank.get('title', request.title),
            chapter=test_bank.get('chapter', request.chapter_name),
            questions=test_bank.get('questions', [])
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error generating test bank: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.get("/api/v1/chapters/")
async def list_chapters():
    """
    List available chapters in the OpenSearch index.
    """
    try:
        opensearch_service.determine_chapter_key()
        chapters = opensearch_service.find_title_index(opensearch_service._chapter_key)
        
        chapter_list = [{
            "name": bucket['key'],
            "doc_count": bucket['doc_count']
        } for bucket in chapters]
        
        return {
            "chapters": chapter_list,
            "total_chapters": len(chapter_list),
            "chapter_key_used": opensearch_service._chapter_key
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving chapters: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
