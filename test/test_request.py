"""Test script for API endpoints with CLI interface.

Local testing: ensure the API is running (e.g. via ./start.sh) and .env points to
local Postgres. When running on the host (pytest or this script), use POSTGRES_HOST=localhost
so you connect to the Postgres container exposed by Docker Compose (port 5432).
Inside Docker Compose, services use POSTGRES_HOST=postgres (the service name).
"""

import os
import requests
import json
import sys
import argparse
from pathlib import Path
from typing import Optional, Dict, Any

from dotenv import load_dotenv

# Load .env from project root so API_KEY is available
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# API Configuration (local default; override with --url when running as script)
API_BASE_URL = "http://127.0.0.1:8000"


def _headers(include_auth: bool = True) -> dict:
    """Headers for requests. When include_auth is True, add API key from env (X-API-Key)."""
    h = {"Content-Type": "application/json"}
    if include_auth:
        api_key = (os.environ.get("JOB_LAND_API_KEY") or "").strip()
        if api_key:
            h["X-API-Key"] = api_key
    return h


def run_health_check() -> bool:
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


def run_profiling_workflow(
    name: str,
    email: str,
    location: str,
    cv_urls: list[str],
    basic_info: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Test the profiling workflow endpoint.

    Args:
        name: User's name
        email: User's email
        cv_urls: List of URLs to CV/PDF documents (required)
        basic_info: Optional basic information about the user

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
        "location": location,
        "cv_urls": [u.strip() for u in cv_urls if (u or "").strip()],
    }

    if basic_info:
        payload["basic_info"] = basic_info

    print("Request Payload:")
    print(json.dumps(payload, indent=2))

    try:
        response = requests.post(
            f"{API_BASE_URL}/workflow/profiling",
            json=payload,
            headers=_headers(),
        )

        print(f"\nStatus Code: {response.status_code}")

        if response.status_code == 401:
            print(
                "✗ API key missing or invalid. Set API_KEY in .env (or in your environment)."
            )
            return None

        if response.status_code == 202:
            result = response.json()
            print("\n✓ Profiling workflow task enqueued successfully!")
            print("\nTask Metadata:")
            print(f"  - Run ID: {result.get('run_id')}")
            print(f"  - Task ID: {result.get('task_id')}")
            print(f"  - Status: {result.get('status')}")
            print(
                f"  - Estimated Completion: {result.get('estimated_completion_time')}"
            )
            print(f"  - Status URL: {result.get('status_url')}")

            print("\n" + "=" * 80)
            print("📋 MONITORING CELERY WORKER STATUS")
            print("=" * 80)
            print("\nThe workflow is now running asynchronously via Celery.")
            print("\nTo monitor the task status, you can:")
            print("\n1. View Celery Worker Logs (Recommended):")
            print("   docker compose logs -f celery-worker")
            print("   # Or: docker logs -f job-agent-celery-worker")
            print("\n2. Check Database Status:")
            print("   Query the 'runs' table:")
            print(
                f"   SELECT * FROM runs WHERE id = '{result.get('run_id')}';"
            )
            print("\n3. Check Task Status via API (if status endpoint exists):")
            print(f"   GET {API_BASE_URL}{result.get('status_url')}")
            print("\n4. Check Redis Queue:")
            print("   docker exec -it job-agent-redis redis-cli")
            print("   LLEN celery")
            print("\n" + "-" * 80)

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


def run_job_search_workflow(
    query: str,
    location: str,
    user_id: str,
    num_results: int = 10,
    max_screening: int = 5,
) -> Optional[Dict[str, Any]]:
    """Test the job search workflow endpoint.

    Args:
        query: Job search query
        location: Job search location
        user_id: UUID of the user (from profiling or DB)
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
        "user_id": user_id,
        "num_results": num_results,
        "max_screening": max_screening,
    }

    print("Request Payload:")
    print(json.dumps(payload, indent=2))

    try:
        response = requests.post(
            f"{API_BASE_URL}/workflow/job-search",
            json=payload,
            headers=_headers(),
        )

        print(f"\nStatus Code: {response.status_code}")

        if response.status_code == 401:
            print(
                "✗ API key missing or invalid. Set API_KEY in .env (or in your environment)."
            )
            return None

        if response.status_code == 202:
            result = response.json()
            print("\n✓ Job search workflow task enqueued successfully!")
            print("\nTask Metadata:")
            print(f"  - Run ID: {result.get('run_id')}")
            print(f"  - Task ID: {result.get('task_id')}")
            print(f"  - Status: {result.get('status')}")
            print(
                f"  - Estimated Completion: {result.get('estimated_completion_time')}"
            )
            print(f"  - Status URL: {result.get('status_url')}")

            print("\n" + "=" * 80)
            print("📋 MONITORING CELERY WORKER STATUS")
            print("=" * 80)
            print("\nThe workflow is now running asynchronously via Celery.")
            print("\nTo monitor the task status, you can:")
            print("\n1. View Celery Worker Logs (Recommended):")
            print("   docker compose logs -f celery-worker")
            print("   # Or: docker logs -f job-agent-celery-worker")
            print("\n2. Check Database Status:")
            print("   Query the 'runs' table:")
            print(
                f"   SELECT * FROM runs WHERE id = '{result.get('run_id')}';"
            )
            print("\n3. Check Task Status via API (if status endpoint exists):")
            print(f"   GET {API_BASE_URL}{result.get('status_url')}")
            print("\n4. Check Redis Queue:")
            print("   docker exec -it job-agent-redis redis-cli")
            print("   LLEN celery")
            print("\n" + "-" * 80)

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


def get_profiling_input() -> Optional[Dict[str, Any]]:
    """Get profiling workflow input from user.

    Returns:
        Dictionary with profiling parameters, or None if invalid
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

    location = input("Enter location (required, e.g. 'Hong Kong'): ").strip()
    if not location:
        print("Location is required!")
        return None

    basic_info = input("Enter basic info (optional, press Enter to skip): ").strip()
    if not basic_info:
        basic_info = None

    url_input = input(
        "Enter CV/PDF URLs (comma-separated, e.g. https://example.com/cv.pdf): "
    ).strip()
    cv_urls = [u.strip() for u in url_input.split(",") if u.strip()]

    if not cv_urls:
        print("At least one CV URL is required!")
        return None

    return {
        "name": name,
        "email": email,
        "location": location,
        "basic_info": basic_info,
        "cv_urls": cv_urls,
    }


def run_job_search_from_profile(
    user_id: str,
    num_results: int = 10,
    max_screening: int = 3,
) -> Optional[Dict[str, Any]]:
    """Test the job search from profile endpoint.

    Args:
        user_id: UUID of the user (from profiling or DB)
        num_results: Number of job results to fetch per search (default: 10)
        max_screening: Maximum number of jobs to screen per search (default: 3)

    Returns:
        Response JSON if successful, None otherwise
    """
    print("\n" + "=" * 80)
    print("TEST: Job Search from Profile")
    print("=" * 80)

    # Prepare request payload
    payload = {
        "user_id": user_id,
        "num_results": num_results,
        "max_screening": max_screening,
    }

    print("Request Payload:")
    print(json.dumps(payload, indent=2))

    try:
        response = requests.post(
            f"{API_BASE_URL}/workflow/job-search/from-profile",
            json=payload,
            headers=_headers(),
        )

        print(f"\nStatus Code: {response.status_code}")

        if response.status_code == 401:
            print(
                "✗ API key missing or invalid. Set API_KEY in .env (or in your environment)."
            )
            return None

        if response.status_code == 202:
            result = response.json()
            print("\nResponse:")
            print(f"  - Message: {result.get('message')}")
            print(f"  - User ID: {result.get('user_id')}")
            print(f"  - Location: {result.get('location')}")
            print(f"  - Job Titles Count: {result.get('job_titles_count')}")
            print(f"  - Job Titles: {result.get('job_titles')}")

            print("\n✓ Job searches initiated via Celery!")
            print(f"\n  - {result.get('job_titles_count')} job searches enqueued")
            print("  - Each search runs as an independent Celery task")
            print("\n" + "=" * 80)
            print("📋 MONITORING CELERY WORKER STATUS")
            print("=" * 80)
            print("\nAll job searches are now running asynchronously via Celery.")
            print("\nTo monitor the tasks, you can:")
            print("\n1. View Celery Worker Logs (Recommended):")
            print("   docker compose logs -f celery-worker")
            print("   # Or: docker logs -f job-agent-celery-worker")
            print("\n2. Check Database Status:")
            print(
                "   Query the 'runs' table for job_search workflows:"
            )
            print(
                "   SELECT * FROM runs ORDER BY created_at DESC;"
            )
            print("\n3. Check Redis Queue:")
            print("   docker exec -it job-agent-redis redis-cli")
            print("   LLEN celery")
            print("\n" + "-" * 80)
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
        "user_id": profile_id,
        "num_results": num_results,
        "max_screening": max_screening,
    }


def check_workflow_status(run_id: str) -> Optional[Dict[str, Any]]:
    """Check workflow execution status.

    Args:
        run_id: UUID of the run to check

    Returns:
        Status information if available, None otherwise
    """
    print("\n" + "=" * 80)
    print(f"Checking Workflow Status for Run ID: {run_id}")
    print("=" * 80)

    try:
        # Try to get status from API endpoint if it exists
        status_url = f"{API_BASE_URL}/workflow/status/{run_id}"
        response = requests.get(status_url, headers=_headers())

        if response.status_code == 401:
            print(
                "\n✗ API key missing or invalid. Set API_KEY in .env (or in your environment)."
            )
            return None

        if response.status_code == 200:
            result = response.json()
            print("\n✓ Status Retrieved:")
            print(f"  - Run ID: {result.get('run_id')}")
            print(f"  - Task ID: {result.get('task_id')}")
            print(f"  - Workflow Type: {result.get('workflow_type')}")
            print(f"  - Status: {result.get('status')}")
            print(f"  - Current Node: {result.get('current_node', 'N/A')}")
            print(f"  - Progress: {result.get('progress_percent', 'N/A')}%")
            print(f"  - Started At: {result.get('started_at', 'N/A')}")
            print(f"  - Completed At: {result.get('completed_at', 'N/A')}")

            if result.get("error_message"):
                print(f"  - Error: {result.get('error_message')}")

            return result
        elif response.status_code == 404:
            print(f"\n⚠ Status endpoint not found or run_id not found: {run_id}")
            print("\nYou can check status via:")
            print(
                "1. Database: SELECT * FROM runs WHERE id = '...';"
            )
            print("2. Celery logs: docker compose logs -f celery-worker")
            return None
        else:
            print(f"\n⚠ Unexpected status code: {response.status_code}")
            return None
    except requests.exceptions.ConnectionError:
        print("\n✗ Connection failed - Is the API server running?")
        return None
    except Exception as e:
        print(f"\n✗ Error checking status: {e}")
        print("\nYou can check status via:")
        print("1. Database: SELECT * FROM runs WHERE id = '...';")
        print("2. Celery logs: docker compose logs -f celery-worker")
        return None


def get_job_search_from_profile_input() -> Optional[Dict[str, Any]]:
    """Get job search from profile input from user.

    Returns:
        Dictionary with job search from profile parameters, or None if invalid
    """
    print("\n" + "-" * 80)
    print("Job Search from Profile Input")
    print("-" * 80)

    profile_id = input("Enter profile ID (UUID, required): ").strip()
    if not profile_id:
        print("Profile ID is required!")
        return None

    num_results_input = input(
        "Enter number of results per search (default: 10): "
    ).strip()
    num_results = int(num_results_input) if num_results_input else 10

    max_screening_input = input("Enter max screening per search (default: 3): ").strip()
    max_screening = int(max_screening_input) if max_screening_input else 3

    return {
        "user_id": profile_id,
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
    print(
        "  4. Job Search from Profile - Test batch job search from profile's suggested titles"
    )
    print("  5. Full Flow - Run profiling then job search")
    print("  6. Check Workflow Status - Check status of a workflow run")
    print()
    print("  0. Exit")
    print()


def interactive_main():
    """Interactive CLI for test selection."""
    global API_BASE_URL

    # Check API connection first
    if not run_health_check():
        print("\n⚠ API server is not running or not accessible.")
        print("  Start the server with: python -m src.api.api")
        print("  Or change API URL by editing API_BASE_URL in the script")

        change_url = (
            input("\nDo you want to change the API URL? (y/n): ").strip().lower()
        )
        if change_url == "y":
            new_url = input("Enter new API URL: ").strip()
            if new_url:
                API_BASE_URL = new_url
                print(f"API URL changed to: {API_BASE_URL}")
        else:
            return

    while True:
        display_menu()
        choice = input("Enter your choice (0-6): ").strip()

        if choice == "0":
            print("\nExiting...")
            break
        elif choice == "1":
            run_health_check()
        elif choice == "2":
            profiling_input = get_profiling_input()
            if profiling_input:
                run_profiling_workflow(**profiling_input)
        elif choice == "3":
            job_search_input = get_job_search_input()
            if job_search_input:
                run_job_search_workflow(**job_search_input)
        elif choice == "4":
            job_search_from_profile_input = get_job_search_from_profile_input()
            if job_search_from_profile_input:
                run_job_search_from_profile(**job_search_from_profile_input)
        elif choice == "5":
            # Full flow: profiling then job search
            print("\n" + "=" * 80)
            print("FULL FLOW: Profiling → Job Search")
            print("=" * 80)
            print("\n⚠ Note: This flow now uses async Celery tasks.")
            print("  The profiling workflow will be enqueued, and you'll need to")
            print("  wait for it to complete before running job search.")
            print("  Check Celery logs or database to see when profiling completes.\n")

            # Step 1: Profiling
            profiling_input = get_profiling_input()
            if not profiling_input:
                print("Skipping full flow test due to invalid profiling input.")
                continue

            profiling_result = run_profiling_workflow(**profiling_input)

            if not profiling_result:
                print(
                    "\n⚠ Profiling workflow failed to enqueue. Cannot proceed with job search."
                )
                continue

            # Note: Since workflows are async, we can't extract profile_id immediately
            # The user needs to wait for profiling to complete and get profile_id from database
            print("\n" + "-" * 80)
            print("⚠ IMPORTANT: Profiling workflow is running asynchronously")
            print("-" * 80)
            print("\nTo proceed with job search:")
            print("1. Wait for profiling workflow to complete (check Celery logs)")
            print("2. Query database to get the profile_id:")
            print("   SELECT id FROM user_profiles ORDER BY created_at DESC LIMIT 1;")
            print("3. Use that profile_id to run job search workflow")
            print("\nAlternatively, you can:")
            print("- Use an existing profile_id if you have one")
            print("- Run job search workflow separately after profiling completes")

            use_existing = (
                input("\nDo you have a profile_id to use for job search? (y/n): ")
                .strip()
                .lower()
            )
            if use_existing == "y":
                profile_id = input("Enter profile_id (UUID): ").strip()
                if profile_id:
                    print("\n" + "-" * 80)
                    print("Using provided profile for job search...")
                    print(f"  Profile ID: {profile_id}")
                    print("-" * 80)

                    job_search_input = get_job_search_input()
                    if job_search_input:
                        # Override with provided user_id (from profiling or DB)
                        job_search_input["user_id"] = profile_id
                        run_job_search_workflow(**job_search_input)
        elif choice == "6":
            run_id = input("\nEnter Run ID (UUID) to check status: ").strip()
            if run_id:
                check_workflow_status(run_id)
            else:
                print("⚠ Run ID is required")
        else:
            print("\n❌ Invalid choice. Please enter a number between 0-6.")
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


# --- Pytest-collectible tests (no fixture-like params) for local API testing ---


def test_health_check():
    """Pytest entry: call health check against local API (requires API running)."""
    assert run_health_check(), "Health check failed; ensure API is running (e.g. ./start.sh)"


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
        choices=["health", "profiling", "job-search", "job-search-from-profile", "all"],
        help="Which test to run (if not provided, shows interactive menu)",
    )
    parser.add_argument(
        "--url",
        type=str,
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--cv-urls",
        type=str,
        help="Comma-separated CV/PDF URLs (required for --test profiling and --test all)",
    )

    args = parser.parse_args()

    if args.url:
        API_BASE_URL = args.url

    # If --test not provided, show interactive menu
    if not args.test:
        interactive_main()
    elif args.test == "health":
        run_health_check()
    elif args.test == "profiling":
        cv_urls = [u.strip() for u in (args.cv_urls or "").split(",") if u.strip()]
        if not cv_urls:
            print("⚠ --test profiling requires --cv-urls (comma-separated URLs).")
            print("  Example: --test profiling --cv-urls 'https://example.com/cv.pdf'")
            print("  Or run without --test to use the interactive menu.")
        else:
            run_profiling_workflow(
                name="Test User",
                email="test@example.com",
                location="Hong Kong",
                cv_urls=cv_urls,
                basic_info="Software engineer with 5 years of experience",
            )
    elif args.test == "job-search":
        # Note: You need to provide a valid profile_id from a previous profiling workflow run
        print("⚠ Warning: job-search test requires a valid profile_id.")
        print("  Run profiling workflow first to get a profile_id, then use it here.")
        profile_id = input("Enter profile_id (or press Enter to skip): ").strip()
        if profile_id:
            run_job_search_workflow(
                query="software engineer",
                location="Hong Kong",
                user_id=profile_id,
                num_results=5,
                max_screening=3,
            )
    elif args.test == "job-search-from-profile":
        # Note: You need to provide a valid profile_id from a previous profiling workflow run
        print("⚠ Warning: job-search-from-profile test requires a valid profile_id.")
        print("  Run profiling workflow first to get a profile_id, then use it here.")
        profile_id = input("Enter profile_id (or press Enter to skip): ").strip()
        if profile_id:
            run_job_search_from_profile(
                user_id=profile_id,
                num_results=10,
                max_screening=3,
            )
    elif args.test == "all":
        # Run all tests in sequence
        if not run_health_check():
            print("\n⚠ Health check failed. Please ensure the API server is running.")
            return

        cv_urls = [u.strip() for u in (args.cv_urls or "").split(",") if u.strip()]
        if not cv_urls:
            print("⚠ --test all requires --cv-urls (comma-separated CV/PDF URLs).")
            print("  Example: --test all --cv-urls 'https://example.com/cv.pdf'")
            return

        profiling_result = run_profiling_workflow(
            name="Test User",
            email="test@example.com",
            location="Hong Kong",
            cv_urls=cv_urls,
            basic_info="Software engineer with 5 years of experience",
        )

        if profiling_result:
            user_id_from_profiling = profiling_result.get("user_id")

            if user_id_from_profiling:
                run_job_search_workflow(
                    query="software engineer",
                    location="Hong Kong",
                    user_id=user_id_from_profiling,
                    num_results=5,
                    max_screening=3,
                )


if __name__ == "__main__":
    main()
