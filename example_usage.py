#!/usr/bin/env python3
"""
Example usage of the TestGen API with dynamic index selection

This script demonstrates how to interact with the TestGen API
to generate test banks programmatically with different book titles.
"""

import requests
import json
import os

# Configuration
API_BASE_URL = "http://localhost:8000"

def test_health():
    """Test if the API is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            print("✅ API is healthy:", response.json())
            return True
        else:
            print("❌ API health check failed:", response.status_code)
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API. Make sure it's running on port 8000")
        return False

def list_available_titles():
    """List available book titles and their indices"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/titles/")
        if response.status_code == 200:
            data = response.json()
            print(f"📚 Found {data['total_titles']} available book titles:")
            for title_info in data['available_titles']:
                print(f"  - '{title_info['title']}' → Index: {title_info['index']}")
            return data['available_titles']
        else:
            print("❌ Failed to list titles:", response.status_code)
            return []
    except Exception as e:
        print(f"❌ Error listing titles: {e}")
        return []

def list_chapters(title="An Invitation to Health"):
    """List available chapters for a specific book title"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/chapters/", params={"title": title})
        if response.status_code == 200:
            data = response.json()
            print(f"📖 Found {data['total_chapters']} chapters for '{data['title']}':")
            print(f"   Using index: {data['index_used']}")
            for chapter in data['chapters'][:10]:  # Show first 10
                print(f"  - {chapter['name']} ({chapter['doc_count']} documents)")
            if len(data['chapters']) > 10:
                print(f"  ... and {len(data['chapters']) - 10} more")
            return data['chapters']
        else:
            print("❌ Failed to list chapters:", response.status_code)
            try:
                error_detail = response.json()
                print(f"   Error: {error_detail.get('detail', 'Unknown error')}")
            except:
                pass
            return []
    except Exception as e:
        print(f"❌ Error listing chapters: {e}")
        return []

def list_saved_files():
    """List saved test bank files"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/files/")
        if response.status_code == 200:
            data = response.json()
            print(f"📁 Found {data['total_files']} saved test bank files:")
            for file_info in data['files'][:5]:  # Show first 5
                print(f"  - {file_info['filename']} ({file_info['size_bytes']} bytes)")
                print(f"    Created: {file_info['created']}")
            if len(data['files']) > 5:
                print(f"  ... and {len(data['files']) - 5} more")
            return data['files']
        else:
            print("❌ Failed to list files:", response.status_code)
            return []
    except Exception as e:
        print(f"❌ Error listing files: {e}")
        return []

def generate_test_bank(title="An Invitation to Health", chapter_name="Chapter 1 Taking Charge of Your Health", num_questions=10, save_to_file=True):
    """Generate a test bank for a specific chapter from a specific book"""
    
    # Test bank request
    request_data = {
        "title": title,
        "chapter_name": chapter_name,
        "learning_objectives": {
            "LO1": "Define health and wellness.",
            "LO2": "Outline the dimensions of health.",
            "LO3": "Assess the current health status of Americans"
        },
        "num_total_qs": num_questions,
        "num_mcq_qs": int(num_questions * 0.7),  # 70% MCQ
        "num_tf_qs": int(num_questions * 0.2),   # 20% T/F
        "num_args_qs": int(num_questions * 0.1), # 10% Essay
        "max_chunks": 100,
        "max_chars": 50000,
        "save_to_file": save_to_file
    }
    
    print(f"🚀 Generating test bank for:")
    print(f"   Title: {title}")
    print(f"   Chapter: {chapter_name}")
    print(f"   Questions: {num_questions} total ({request_data['num_mcq_qs']} MCQ, {request_data['num_tf_qs']} T/F, {request_data['num_args_qs']} Essay)")
    print(f"   Save to file: {save_to_file}")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/test-bank/generate/",
            json=request_data,
            timeout=300  # 5 minute timeout
        )
        
        if response.status_code == 200:
            test_bank = response.json()
            print(f"✅ Successfully generated test bank!")
            print(f"   Title: {test_bank['title']}")
            print(f"   Chapter: {test_bank['chapter']}")
            print(f"   Index used: {test_bank.get('index_used', 'Unknown')}")
            print(f"   Generated {len(test_bank['questions'])} questions")
            
            # Check if file was saved
            if test_bank.get('file_saved'):
                print(f"💾 Test bank saved to: {test_bank.get('saved_file', 'output file')}")
            else:
                print("⚠️  Test bank was not saved to file")
            
            # Show first few questions
            for i, question in enumerate(test_bank['questions'][:3]):
                print(f"\n📝 Question {i+1} ({question['type']}):")
                print(f"   {question['question_text']}")
                if question.get('options'):
                    for option in question['options']:
                        print(f"     {option['label']}: {option['text']}")
                print(f"   ✓ Answer: {question['correct_answer']}")
            
            if len(test_bank['questions']) > 3:
                print(f"\n... and {len(test_bank['questions']) - 3} more questions")
            
            return test_bank
            
        else:
            print(f"❌ Failed to generate test bank: {response.status_code}")
            try:
                error_detail = response.json()
                print(f"   Error: {error_detail.get('detail', 'Unknown error')}")
            except:
                print(f"   Response: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out. Test bank generation takes time with large content.")
        return None
    except Exception as e:
        print(f"❌ Error generating test bank: {e}")
        return None

def test_multiple_titles():
    """Test generating test banks for different book titles"""
    print("\n🔄 Testing multiple book titles...")
    
    # List available titles
    titles = list_available_titles()
    
    if not titles:
        print("❌ No titles available for testing")
        return
    
    for title_info in titles:
        title = title_info['title']
        print(f"\n📚 Testing title: {title}")
        
        # List chapters for this title
        chapters = list_chapters(title)
        
        if chapters:
            # Use the first available chapter
            chapter_name = chapters[0]['name']
            print(f"🧪 Generating small test bank for: {chapter_name}")
            
            # Generate a small test bank
            test_bank = generate_test_bank(
                title=title,
                chapter_name=chapter_name,
                num_questions=3,
                save_to_file=True
            )
            
            if test_bank:
                print(f"✅ Successfully generated test bank for {title}")
            else:
                print(f"❌ Failed to generate test bank for {title}")
        else:
            print(f"❌ No chapters found for {title}")

def main():
    """Main function to demonstrate API usage with dynamic index selection"""
    print("🧪 TestGen API Example Usage - Dynamic Index Selection")
    print("=" * 60)
    
    # Test API health
    if not test_health():
        print("\nPlease start the API first:")
        print("  python app.py")
        return
    
    print()
    
    # List available book titles
    print("📚 Step 1: Listing available book titles...")
    titles = list_available_titles()
    
    print()
    
    # List existing saved files
    print("📁 Step 2: Checking existing saved files...")
    list_saved_files()
    
    print()
    
    # Test with default title
    print("🔄 Step 3: Generating test bank with default title...")
    if titles:
        default_title = titles[0]['title']  # Use first available title
        print(f"Using title: {default_title}")
        
        # List chapters for default title
        chapters = list_chapters(default_title)
        
        if chapters:
            chapter_name = chapters[0]['name']
            print(f"Using chapter: {chapter_name}")
            
            test_bank = generate_test_bank(
                title=default_title,
                chapter_name=chapter_name,
                num_questions=5,
                save_to_file=True
            )
            
            if test_bank:
                print("\n📁 Checking for new saved files...")
                list_saved_files()
        else:
            print(f"❌ No chapters found for {default_title}")
    
    print()
    
    # Test multiple titles if available
    if len(titles) > 1:
        print("🔄 Step 4: Testing multiple book titles...")
        test_multiple_titles()
    
    print("\n🎉 Example completed successfully!")
    print("Visit http://localhost:8000/docs for interactive API documentation")
    
    # Check if output directory exists
    if os.path.exists("./output"):
        print(f"\n📂 Check the './output' directory for saved test bank files")
    else:
        print("\n⚠️  Output directory not found. Files may not have been saved.")

if __name__ == "__main__":
    main()
