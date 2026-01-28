"""Test script for API endpoints with CLI interface."""

import requests
import json
import sys
import argparse
from pathlib import Path
from typing import Optional, Dict, Any


# API Configuration
API_BASE_URL = "http://localhost:8000"


def test_health_check() -> bool:
    """Test the health check endpoint.
    
    Returns:
        True if test passed, False otherwise
    """
    print("\n" + "=" * 80)
    print("TEST: Health Check")
    print("=" * 80)
    
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✓ Health check passed")
            return True
        else:
            print("✗ Health check failed")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ Connection failed - Is the API server running?")
        print("  Try running: python -m src.api.api")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_profiling_workflow(
    name: str,
    email: str,
    basic_info: Optional[str] = None,
    data_dir: Optional[str] = None,
    pdf_paths: Optional[list] = None,
) -> Optional[Dict[str, Any]]:
    """Test the profiling workflow endpoint.
    
    Args:
        name: User's name
        email: User's email
        basic_info: Optional basic information about the user
        data_dir: Optional path to directory containing PDFs
        pdf_paths: Optional list of PDF file paths
        
    Returns:
        Response JSON if successful, None otherwise
    """
    print("\n" + "=" * 80)
    print("TEST: Profiling Workflow")
    print("=" * 80)
    
    # Prepare request payload
    payload = {
        "name": name,
        "email": email,
    }
    
    if basic_info:
        payload["basic_info"] = basic_info
    
    if data_dir:
        payload["data_dir"] = str(data_dir)
    
    if pdf_paths:
        payload["pdf_paths"] = [str(p) for p in pdf_paths]
    
    print("Request Payload:")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/workflow/profiling",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 202:
            result = response.json()
            print("\nResponse:")
            print(f"  - Profile ID: {result.get('profile_id')}")
            print(f"  - Profile Name: {result.get('name')}")
            print(f"  - Profile Email: {result.get('email')}")
            print(f"  - Profile Length: {len(result.get('user_profile', ''))} chars")
            print(f"  - Has Errors: {len(result.get('errors', [])) > 0}")
            
            if result.get('errors'):
                print(f"  - Errors: {result['errors']}")
            
            print("✓ Profiling workflow completed")
            return result
        else:
            print("✗ Request failed")
            try:
                error_detail = response.json()
                print(f"Error Detail: {json.dumps(error_detail, indent=2)}")
            except (ValueError, KeyError):
                print(f"Error: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("✗ Connection failed - Is the API server running?")
        return None
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def test_job_search_workflow(
    query: str,
    location: str,
    profile_id: str,
    num_results: int = 10,
    max_screening: int = 5,
) -> Optional[Dict[str, Any]]:
    """Test the job search workflow endpoint.
    
    Args:
        query: Job search query
        location: Job search location
        profile_id: UUID of the profile to retrieve
        num_results: Number of job results to fetch
        max_screening: Maximum number of jobs to screen
        
    Returns:
        Response JSON if successful, None otherwise
    """
    print("\n" + "=" * 80)
    print("TEST: Job Search Workflow")
    print("=" * 80)
    
    # Prepare request payload
    payload = {
        "query": query,
        "location": location,
        "profile_id": profile_id,
        "num_results": num_results,
        "max_screening": max_screening,
    }
    
    print("Request Payload:")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/workflow/job-search",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 202:
            result = response.json()
            print("\nResponse Summary:")
            print(f"  - Jobs Found: {len(result.get('jobs', []))}")
            print(f"  - Jobs Screened: {len(result.get('all_screening_results', []))}")
            print(f"  - Matches Found: {len(result.get('matched_results', []))}")
            print(f"  - Profile Retrieved: {result.get('user_profile') is not None}")
            print(f"  - Has Errors: {len(result.get('errors', [])) > 0}")
            
            if result.get('errors'):
                print(f"  - Errors: {result['errors']}")
            
            print("✓ Job search workflow completed")
            return result
        else:
            print("✗ Request failed")
            try:
                error_detail = response.json()
                print(f"Error Detail: {json.dumps(error_detail, indent=2)}")
            except (ValueError, KeyError):
                print(f"Error: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("✗ Connection failed - Is the API server running?")
        return None
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def get_profiling_input() -> Dict[str, Any]:
    """Get profiling workflow input from user.
    
    Returns:
        Dictionary with profiling parameters
    """
    print("\n" + "-" * 80)
    print("Profiling Workflow Input")
    print("-" * 80)
    
    name = input("Enter name (required): ").strip()
    if not name:
        print("Name is required!")
        return None
    
    email = input("Enter email (required): ").strip()
    if not email:
        print("Email is required!")
        return None
    
    basic_info = input("Enter basic info (optional, press Enter to skip): ").strip()
    if not basic_info:
        basic_info = None
    
    print("\nPDF Input Options:")
    print("  1. Use data_dir (directory path)")
    print("  2. Use pdf_paths (comma-separated file paths)")
    print("  3. Use default data directory")
    
    pdf_choice = input("Choose option (1-3, default: 3): ").strip() or "3"
    
    data_dir = None
    pdf_paths = None
    
    if pdf_choice == "1":
        data_dir = input("Enter data directory path: ").strip()
        if not data_dir:
            data_dir = None
    elif pdf_choice == "2":
        pdf_input = input("Enter PDF paths (comma-separated): ").strip()
        if pdf_input:
            pdf_paths = [p.strip() for p in pdf_input.split(",")]
    else:
        # Use default data directory
        project_root = Path(__file__).parent.parent
        data_dir = str(project_root / "data")
    
    return {
        "name": name,
        "email": email,
        "basic_info": basic_info,
        "data_dir": data_dir,
        "pdf_paths": pdf_paths,
    }


def get_job_search_input() -> Dict[str, Any]:
    """Get job search workflow input from user.
    
    Returns:
        Dictionary with job search parameters
    """
    print("\n" + "-" * 80)
    print("Job Search Workflow Input")
    print("-" * 80)
    
    query = input("Enter job search query (required): ").strip()
    if not query:
        print("Query is required!")
        return None
    
    location = input("Enter location (required): ").strip()
    if not location:
        print("Location is required!")
        return None
    
    profile_id = input("Enter profile ID (UUID, required): ").strip()
    if not profile_id:
        print("Profile ID is required!")
        return None
    
    num_results_input = input("Enter number of results (default: 10): ").strip()
    num_results = int(num_results_input) if num_results_input else 10
    
    max_screening_input = input("Enter max screening (default: 5): ").strip()
    max_screening = int(max_screening_input) if max_screening_input else 5
    
    return {
        "query": query,
        "location": location,
        "profile_id": profile_id,
        "num_results": num_results,
        "max_screening": max_screening,
    }


def display_menu():
    """Display interactive menu for test selection."""
    print("\n" + "=" * 80)
    print("API ENDPOINT TESTING MENU")
    print("=" * 80)
    print(f"API Base URL: {API_BASE_URL}")
    print("\nSelect a test to run:")
    print()
    print("  1. Health Check - Test API health endpoint")
    print("  2. Profiling Workflow - Test profile creation")
    print("  3. Job Search Workflow - Test job search with profile")
    print("  4. Full Flow - Run profiling then job search")
    print()
    print("  0. Exit")
    print()


def interactive_main():
    """Interactive CLI for test selection."""
    global API_BASE_URL
    
    # Check API connection first
    if not test_health_check():
        print("\n⚠ API server is not running or not accessible.")
        print("  Start the server with: python -m src.api.api")
        print("  Or change API URL by editing API_BASE_URL in the script")
        
        change_url = input("\nDo you want to change the API URL? (y/n): ").strip().lower()
        if change_url == "y":
            new_url = input("Enter new API URL: ").strip()
            if new_url:
                API_BASE_URL = new_url
                print(f"API URL changed to: {API_BASE_URL}")
        else:
            return
    
    while True:
        display_menu()
        choice = input("Enter your choice (0-4): ").strip()

        if choice == "0":
            print("\nExiting...")
            break
        elif choice == "1":
            test_health_check()
        elif choice == "2":
            profiling_input = get_profiling_input()
            if profiling_input:
                test_profiling_workflow(**profiling_input)
        elif choice == "3":
            job_search_input = get_job_search_input()
            if job_search_input:
                test_job_search_workflow(**job_search_input)
        elif choice == "4":
            # Full flow: profiling then job search
            print("\n" + "=" * 80)
            print("FULL FLOW: Profiling → Job Search")
            print("=" * 80)
            
            # Step 1: Profiling
            profiling_input = get_profiling_input()
            if not profiling_input:
                print("Skipping full flow test due to invalid profiling input.")
                continue
            
            profiling_result = test_profiling_workflow(**profiling_input)
            
            if not profiling_result:
                print("\n⚠ Profiling workflow failed. Cannot proceed with job search.")
                continue
            
            # Step 2: Job Search using created profile
            profile_id = profiling_result.get("profile_id")
            
            if profile_id:
                print("\n" + "-" * 80)
                print("Using created profile for job search...")
                print(f"  Profile ID: {profile_id}")
                print("-" * 80)
                
                job_search_input = get_job_search_input()
                if job_search_input:
                    # Override with actual profile_id
                    job_search_input["profile_id"] = profile_id
                    test_job_search_workflow(**job_search_input)
            else:
                print("\n⚠ Could not extract profile_id from profiling result.")
        else:
            print("\n❌ Invalid choice. Please enter a number between 0-4.")
            continue

        # Ask if user wants to continue
        if choice != "0":
            print("\n" + "-" * 80)
            continue_choice = (
                input("Press Enter to return to menu, or 'q' to quit: ").strip().lower()
            )
            if continue_choice == "q":
                print("\nExiting...")
                break


def main():
    """Main test runner with both CLI and argument parsing support."""
    global API_BASE_URL
    
    # Allow custom API URL via command line argument
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        API_BASE_URL = sys.argv[1]
        print(f"Using custom API URL: {API_BASE_URL}")
        sys.argv = [sys.argv[0]] + sys.argv[2:]
    
    # If no arguments provided, show interactive menu
    if len(sys.argv) == 1:
        interactive_main()
        return

    # Otherwise, use argument parser for command-line mode
    parser = argparse.ArgumentParser(description="Test API endpoints")
    parser.add_argument(
        "--test",
        choices=["health", "profiling", "job-search", "all"],
        help="Which test to run (if not provided, shows interactive menu)",
    )
    parser.add_argument(
        "--url",
        type=str,
        help="API base URL (default: http://localhost:8000)",
    )

    args = parser.parse_args()
    
    if args.url:
        API_BASE_URL = args.url

    # If --test not provided, show interactive menu
    if not args.test:
        interactive_main()
    elif args.test == "health":
        test_health_check()
    elif args.test == "profiling":
        # Use default values for command-line mode
        project_root = Path(__file__).parent.parent
        data_dir = project_root / "data"
        test_profiling_workflow(
            name="Test User",
            email="test@example.com",
            basic_info="Software engineer with 5 years of experience",
            data_dir=str(data_dir) if data_dir.exists() else None,
        )
    elif args.test == "job-search":
        # Note: You need to provide a valid profile_id from a previous profiling workflow run
        print("⚠ Warning: job-search test requires a valid profile_id.")
        print("  Run profiling workflow first to get a profile_id, then use it here.")
        profile_id = input("Enter profile_id (or press Enter to skip): ").strip()
        if profile_id:
            test_job_search_workflow(
                query="software engineer",
                location="Hong Kong",
                profile_id=profile_id,
                num_results=5,
                max_screening=3,
            )
    elif args.test == "all":
        # Run all tests in sequence
        if not test_health_check():
            print("\n⚠ Health check failed. Please ensure the API server is running.")
            return
        
        project_root = Path(__file__).parent.parent
        data_dir = project_root / "data"
        
        profiling_result = test_profiling_workflow(
            name="Test User",
            email="test@example.com",
            basic_info="Software engineer with 5 years of experience",
            data_dir=str(data_dir) if data_dir.exists() else None,
        )
        
        if profiling_result:
            profile_id = profiling_result.get("profile_id")
            
            if profile_id:
                test_job_search_workflow(
                    query="software engineer",
                    location="Hong Kong",
                    profile_id=profile_id,
                    num_results=5,
                    max_screening=3,
                )


if __name__ == "__main__":
    main()
