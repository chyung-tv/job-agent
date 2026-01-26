"""Test script for the workflow - matches first 3 discovered jobs only."""

from src.workflow import run


def test_workflow():
    """Test the complete workflow with limited job screening."""
    print("=" * 80)
    print("WORKFLOW TEST - First 3 Jobs Only")
    print("=" * 80)

    # Test with different job queries
    test_queries = [
        "nextjs developer",
        # "ai engineer",
        # "註冊中醫師",
    ]

    for query in test_queries:
        print(f"\n{'#' * 80}")
        print(f"Testing query: '{query}'")
        print(f"{'#' * 80}\n")

        try:
            matched_jobs = run(
                query=query,
                location="Hong Kong",
                num_results=10,  # Fetch 10 jobs
                max_screening=3,  # Only screen first 3 jobs for testing
            )

            print(f"\n[TEST RESULT] Found {len(matched_jobs)} matches for '{query}'")

        except Exception as e:
            print(f"\n[TEST ERROR] Failed for query '{query}': {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    test_workflow()
