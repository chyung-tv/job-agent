"""Test script for the complete workflow including Run, research, fabrication, and delivery."""

import sys
from pathlib import Path

# Add project root to Python path if running directly
# This allows the script to work both as a module and when run directly
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.workflow import run
from src.database import db_session
from src.database.models import (
    Run,
    MatchedJob,
    CompanyResearch,
    CoverLetter,
    JobPosting,
)
from src.workflow.completion import (
    check_run_completion,
    get_completed_items_for_delivery,
)


def test_workflow():
    """Test the complete workflow with Run tracking, research, fabrication, and delivery."""
    print("=" * 80)
    print("WORKFLOW TEST - Complete Pipeline (Run + Research + Fabrication + Delivery)")
    print("=" * 80)

    # Test with different job queries
    test_queries = [
        # "nextjs developer",
        # "ai engineer",
        # "註冊中醫師",
        "startup ai engineer",
    ]

    for query in test_queries:
        print(f"\n{'#' * 80}")
        print(f"Testing query: '{query}'")
        print(f"{'#' * 80}\n")

        try:
            context = run(
                query=query,
                location="Hong Kong",
                num_results=10,  # Fetch 10 jobs
                max_screening=3,  # Only screen first 3 jobs for testing
            )

            # Get summary from context
            summary = context.get_summary()

            print(f"\n[TEST RESULT] Summary for '{query}':")
            print(f"  - Jobs found: {summary['jobs_found']}")
            print(f"  - Jobs screened: {summary['jobs_screened']}")
            print(f"  - Matches found: {summary['matches_found']}")
            print(f"  - Profile cached: {summary['profile_cached']}")
            print(f"  - Has errors: {summary['has_errors']}")
            print(f"  - Run ID: {context.run_id}")

            print("\n[WORKFLOW STEPS COMPLETED]")
            print("  ✓ Step 1: Run created")
            print("  ✓ Step 2: Discovery")
            print("  ✓ Step 3: Profiling")
            print("  ✓ Step 4: Matching")
            if context.run_id and context.matched_results:
                print("  ✓ Step 5: Research")
                print("  ✓ Step 6: Fabrication")
                print("  ✓ Step 7: Completion detection & Delivery")

            if context.has_errors():
                print("\n[WARNINGS] Errors encountered:")
                for error in context.errors:
                    print(f"  - {error}")

            # Verify Run was created and check its status
            if context.run_id:
                print("\n[VERIFICATION] Checking Run status in database...")
                session = next(db_session())
                try:
                    run_record = session.query(Run).filter_by(id=context.run_id).first()
                    if run_record:
                        print("  ✓ Run found:")
                        print(f"    - Status: {run_record.status}")
                        print(
                            f"    - Total matched jobs: {run_record.total_matched_jobs}"
                        )
                        print(
                            f"    - Research completed: {run_record.research_completed_count}"
                        )
                        print(
                            f"    - Research failed: {run_record.research_failed_count}"
                        )
                        print(
                            f"    - Fabrication completed: {run_record.fabrication_completed_count}"
                        )
                        print(
                            f"    - Fabrication failed: {run_record.fabrication_failed_count}"
                        )
                        print(
                            f"    - Delivery triggered: {run_record.delivery_triggered}"
                        )

                        # Check matched jobs status
                        matched_jobs = (
                            session.query(MatchedJob)
                            .filter_by(run_id=context.run_id)
                            .all()
                        )

                        if matched_jobs:
                            print("\n  [MATCHED JOBS STATUS]")
                            for i, mj in enumerate(matched_jobs, 1):
                                job_posting = (
                                    session.query(JobPosting)
                                    .filter_by(id=mj.job_posting_id)
                                    .first()
                                )
                                company_research = (
                                    session.query(CompanyResearch)
                                    .filter_by(job_posting_id=mj.job_posting_id)
                                    .first()
                                )
                                cover_letter = (
                                    session.query(CoverLetter)
                                    .filter_by(matched_job_id=mj.id)
                                    .first()
                                )

                                job_title = job_posting.title if job_posting else "N/A"
                                print(
                                    f"    {i}. {job_title} (Matched Job {str(mj.id)[:8]}...)"
                                )
                                print(
                                    f"       - Research: {mj.research_status} ({mj.research_attempts} attempts)"
                                )
                                print(
                                    f"       - Fabrication: {mj.fabrication_status} ({mj.fabrication_attempts} attempts)"
                                )
                                print(
                                    f"       - Has research: {'✓' if company_research else '✗'}"
                                )
                                print(
                                    f"       - Has cover letter: {'✓' if cover_letter else '✗'}"
                                )

                        # Verify completion
                        is_complete = check_run_completion(session, str(context.run_id))
                        print("\n  [COMPLETION CHECK]")
                        print(f"    - Run is complete: {'✓' if is_complete else '✗'}")

                        if is_complete:
                            completed_items = get_completed_items_for_delivery(
                                session, str(context.run_id)
                            )
                            print(
                                f"    - Items ready for delivery: {len(completed_items)}"
                            )
                            if completed_items:
                                print("    - Delivery items:")
                                for item in completed_items:
                                    print(
                                        f"      • {item['job_title']} at {item['company_name']}"
                                    )
                    else:
                        print(f"  ❌ Run {context.run_id} not found in database")
                except Exception as e:
                    print(f"  ❌ Error checking run status: {e}")
                    import traceback

                    traceback.print_exc()
                finally:
                    session.close()
            else:
                print(
                    "\n[WARNING] No run_id in context - Run may not have been created"
                )

        except Exception as e:
            print(f"\n[TEST ERROR] Failed for query '{query}': {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    test_workflow()
