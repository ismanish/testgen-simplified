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

# Import the index mapping
from index_map import get_index_for_title, get_available_titles

# Configuration
class Config:
    PROJECT_NAME: str = "TestGen API - Simplified"
    
    # OpenSearch settings
    OPENSEARCH_HOST: str = "https://64asp87vin20xc5bhvbf.us-east-1.aoss.amazonaws.com"
    OPENSEARCH_REGION: str = "us-east-1"
    # OPENSEARCH_INDEX removed - now determined by title
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
    save_to_file: bool = Field(True, description="Whether to save the generated test bank to a JSON file")

# FastAPI app initialization
app = FastAPI(
    title=config.PROJECT_NAME,
    description="Simplified API for generating educational test banks using Claude and OpenSearch with dynamic index selection",
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
        self._current_index = None

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
    
    def set_index_for_title(self, title: str):
        """Set the OpenSearch index based on the book title."""
        try:
            self._current_index = get_index_for_title(title)
            print(f"Using OpenSearch index: {self._current_index} for title: {title}")
        except ValueError as e:
            raise ValueError(f"Unsupported book title: {e}")
    
    def find_title_index(self, chapter_key):
        """Find all available chapter titles using the specified chapter key."""
        if not self._current_index:
            raise ValueError("No index set. Call set_index_for_title() first.")
            
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
            index=self._current_index,
            body=query
        )
        
        chapter_buckets = response.get('aggregations', {}).get('chapter_names', {}).get('buckets', [])
        return chapter_buckets

    def determine_chapter_key(self):
        """Determine which metadata field contains chapter information."""
        if not self._current_index:
            raise ValueError("No index set. Call set_index_for_title() first.")
            
        if 'chapter' in "".join([val['key'].lower() for val in self.find_title_index('toc_level_2_title')]):
            self._chapter_key = 'toc_level_2_title'
        else:
            self._chapter_key = 'toc_level_1_title'
        
        return self._chapter_key
    
    def retrieve_chapter_content(self, chapter_name: str, max_chunks: int = 200, max_chars: int = 100000):
        """Retrieve chapter content from OpenSearch."""
        if not self._current_index:
            raise ValueError("No index set. Call set_index_for_title() first.")
            
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
                index=self._current_index,
                body=query_body
            )
        except Exception as e:
            raise Exception(f"Search error in index {self._current_index}: {e}")
        
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

# File Service
class FileService:
    @staticmethod
    def save_test_bank(title: str, chapter_name: str, test_bank: dict, save_directory: str = "./output") -> str:
        """
        Save the test bank to a JSON file.
        
        Args:
            title (str): The title of the book
            chapter_name (str): The chapter name
            test_bank (dict): The test bank data
            save_directory (str): Directory to save files in
            
        Returns:
            str: The filename of the saved file
        """
        # Create output directory if it doesn't exist
        os.makedirs(save_directory, exist_ok=True)
        
        # Clean title and chapter name for filename
        clean_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_chapter = "".join(c for c in chapter_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        
        # Replace spaces with underscores and make lowercase
        clean_title = clean_title.replace(' ', '_').lower()
        clean_chapter = clean_chapter.replace(' ', '_').lower()
        
        # Generate timestamp for uniqueness
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create filename
        filename = f"{clean_title}_{clean_chapter}_test_bank_{timestamp}.json"
        filepath = os.path.join(save_directory, filename)
        
        # Save the file
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(test_bank, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Test bank saved to: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"❌ Error saving test bank to file: {e}")
            raise Exception(f"Failed to save test bank: {e}")

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
file_service = FileService()

# API Endpoints
@app.get("/")
def read_root():
    return {"message": f"Welcome to {config.PROJECT_NAME}. Go to /docs for API documentation."}

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.datetime.utcnow().isoformat()}

@app.get("/api/v1/titles/")
async def list_available_titles():
    """
    List all available book titles and their corresponding indices.
    """
    try:
        titles = get_available_titles()
        title_info = []
        
        for title in titles:
            try:
                index = get_index_for_title(title)
                title_info.append({
                    "title": title,
                    "index": index
                })
            except ValueError:
                continue
        
        return {
            "available_titles": title_info,
            "total_titles": len(title_info),
            "message": "Use one of these titles in your test bank generation request"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving available titles: {str(e)}")

@app.post("/api/v1/test-bank/generate/", response_model=TestBankResponse)
async def generate_test_bank(request: TestBankRequest):
    """
    Generate a test bank for a given chapter from a specific book title.
    
    This endpoint retrieves chapter content from the appropriate OpenSearch index
    based on the book title, constructs a prompt with learning objectives, 
    and uses Claude to generate structured test questions with answers and rationales.
    """
    saved_file_path = None
    
    try:
        print(f"Generating test bank for title: {request.title}, chapter: {request.chapter_name}")
        
        # Step 1: Set the correct OpenSearch index based on title
        try:
            opensearch_service.set_index_for_title(request.title)
        except ValueError as e:
            available_titles = get_available_titles()
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported book title '{request.title}'. Available titles: {available_titles}"
            )
        
        # Step 2: Retrieve chapter content from OpenSearch
        chapter_content = opensearch_service.retrieve_chapter_content(
            chapter_name=request.chapter_name,
            max_chunks=request.max_chunks,
            max_chars=request.max_chars
        )
        
        if not chapter_content:
            raise ValueError(f"No content found for chapter '{request.chapter_name}' in '{request.title}'")
        
        print(f"Retrieved {len(chapter_content)} characters of content from index: {opensearch_service._current_index}")
        
        # Step 3: Format learning objectives
        lo_formatted = "Learning Objectives:\n"
        for lo_id, lo_text in request.learning_objectives.items():
            lo_formatted += f"- {lo_id}: {lo_text}\n"
        
        # Step 4: Create prompt
        prompt = TEST_BANK_PROMPT.format(
            chapter_content=chapter_content,
            learning_objectives=lo_formatted,
            num_total_qs=request.num_total_qs,
            num_mcq_qs=request.num_mcq_qs,
            num_tf_qs=request.num_tf_qs,
            num_args_qs=request.num_args_qs
        )
        
        # Step 5: Generate test bank using LLM
        print("Sending prompt to Claude for test bank generation...")
        test_bank = llm_service.generate_test_bank(prompt)
        
        print(f"Generated test bank with {len(test_bank.get('questions', []))} questions")
        
        # Step 6: Save to file if requested
        if request.save_to_file:
            try:
                saved_file_path = file_service.save_test_bank(
                    title=request.title,
                    chapter_name=request.chapter_name,
                    test_bank=test_bank
                )
                print(f"Test bank saved to: {saved_file_path}")
            except Exception as e:
                print(f"Warning: Could not save file: {e}")
                # Continue without failing the API call
        
        # Step 7: Return response
        response = TestBankResponse(
            title=test_bank.get('title', request.title),
            chapter=test_bank.get('chapter', request.chapter_name),
            questions=test_bank.get('questions', [])
        )
        
        # Add saved file info to response if file was saved
        response_dict = response.dict()
        response_dict['index_used'] = opensearch_service._current_index
        
        if saved_file_path:
            response_dict['saved_file'] = saved_file_path
            response_dict['file_saved'] = True
        else:
            response_dict['file_saved'] = False
        
        return response_dict
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error generating test bank: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.get("/api/v1/chapters/")
async def list_chapters(title: str = "An Invitation to Health"):
    """
    List available chapters in the OpenSearch index for a specific book title.
    """
    try:
        # Set the correct index based on title
        try:
            opensearch_service.set_index_for_title(title)
        except ValueError as e:
            available_titles = get_available_titles()
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported book title '{title}'. Available titles: {available_titles}"
            )
        
        opensearch_service.determine_chapter_key()
        chapters = opensearch_service.find_title_index(opensearch_service._chapter_key)
        
        chapter_list = [{
            "name": bucket['key'],
            "doc_count": bucket['doc_count']
        } for bucket in chapters]
        
        return {
            "title": title,
            "index_used": opensearch_service._current_index,
            "chapters": chapter_list,
            "total_chapters": len(chapter_list),
            "chapter_key_used": opensearch_service._chapter_key
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving chapters: {str(e)}")

@app.get("/api/v1/files/")
async def list_saved_files():
    """
    List all saved test bank files.
    """
    try:
        output_dir = "./output"
        if not os.path.exists(output_dir):
            return {"files": [], "total_files": 0, "message": "No output directory found"}
        
        files = []
        for filename in os.listdir(output_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(output_dir, filename)
                stat = os.stat(filepath)
                files.append({
                    "filename": filename,
                    "filepath": filepath,
                    "size_bytes": stat.st_size,
                    "created": datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        
        # Sort by creation time (newest first)
        files.sort(key=lambda x: x['created'], reverse=True)
        
        return {
            "files": files,
            "total_files": len(files),
            "output_directory": output_dir
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
