#!/usr/bin/env python3
"""
Example usage of the TestGen API

This script demonstrates how to interact with the TestGen API
to generate test banks programmatically.
"""

import requests
import json

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

def list_chapters():
    """List available chapters"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/chapters/")
        if response.status_code == 200:
            data = response.json()
            print(f"📚 Found {data['total_chapters']} chapters:")
            for chapter in data['chapters'][:10]:  # Show first 10
                print(f"  - {chapter['name']} ({chapter['doc_count']} documents)")
            if len(data['chapters']) > 10:
                print(f"  ... and {len(data['chapters']) - 10} more")
            return data['chapters']
        else:
            print("❌ Failed to list chapters:", response.status_code)
            return []
    except Exception as e:
        print(f"❌ Error listing chapters: {e}")
        return []

def generate_test_bank(chapter_name="Chapter 1 Taking Charge of Your Health", num_questions=10):
    """Generate a test bank for a specific chapter"""
    
    # Test bank request
    request_data = {
        "title": "An Invitation to Health",
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
        "max_chars": 50000
    }
    
    print(f"🚀 Generating test bank for: {chapter_name}")
    print(f"   Questions: {num_questions} total ({request_data['num_mcq_qs']} MCQ, {request_data['num_tf_qs']} T/F, {request_data['num_args_qs']} Essay)")
    
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
            print(f"   Generated {len(test_bank['questions'])} questions")
            
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
            
            # Save to file
            filename = f"test_bank_{chapter_name.replace(' ', '_').lower()}.json"
            with open(filename, 'w') as f:
                json.dump(test_bank, f, indent=2)
            print(f"💾 Test bank saved to: {filename}")
            
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

def main():
    """Main function to demonstrate API usage"""
    print("🧪 TestGen API Example Usage")
    print("=" * 40)
    
    # Test API health
    if not test_health():
        print("\nPlease start the API first:")
        print("  python app.py")
        return
    
    print()
    
    # List available chapters
    chapters = list_chapters()
    
    print()
    
    # Generate a small test bank
    if chapters:
        # Use the first available chapter or default
        chapter_name = chapters[0]['name'] if chapters else "Chapter 1 Taking Charge of Your Health"
    else:
        chapter_name = "Chapter 1 Taking Charge of Your Health"
    
    test_bank = generate_test_bank(chapter_name, num_questions=5)
    
    if test_bank:
        print("\n🎉 Example completed successfully!")
        print("Visit http://localhost:8000/docs for interactive API documentation")
    else:
        print("\n⚠️  Example completed with errors")

if __name__ == "__main__":
    main()
