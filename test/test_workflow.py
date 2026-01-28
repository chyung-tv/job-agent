"""Test script for the new workflow architecture and individual nodes."""

import sys
import asyncio
from pathlib import Path

# Add project root to Python path if running directly
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.workflow.job_search_workflow import JobSearchWorkflow
from src.workflow.base_context import JobSearchWorkflowContext
from src.workflow.nodes.discovery_node import DiscoveryNode
from src.workflow.nodes.profiling_node import ProfilingNode
from src.workflow.nodes.matching_node import MatchingNode
from src.workflow.nodes.research_node import ResearchNode
from src.workflow.nodes.fabrication_node import FabricationNode
from src.workflow.nodes.completion_node import CompletionNode
from src.workflow.nodes.delivery_node import DeliveryNode
from src.database import (
    db_session,
    Run,
    MatchedJob,
    CompanyResearch,
    JobPosting,
    WorkflowExecution,
    Artifact,
)


# ============================================================================
# Individual Node Tests
# ============================================================================


async def test_discovery_node():
    """Test DiscoveryNode separately."""
    print("=" * 80)
    print("TEST: DiscoveryNode")
    print("=" * 80)

    context = JobSearchWorkflowContext(
        query="software engineer",
        location="Hong Kong",
        num_results=5,
    )

    node = DiscoveryNode()
    result = await node.run(context)

    print(f"\n[RESULT]")
    print(f"  - Jobs found: {len(result.jobs)}")
    print(f"  - Job search ID: {result.job_search_id}")
    print(f"  - Errors: {result.errors}")

    if result.jobs:
        print(f"\n[FIRST JOB]")
        job = result.jobs[0]
        print(f"  - Title: {job.title}")
        print(f"  - Company: {job.company_name}")
        print(f"  - Location: {job.location}")

    return result


async def test_profiling_node():
    """Test ProfilingNode separately."""
    print("\n" + "=" * 80)
    print("TEST: ProfilingNode")
    print("=" * 80)

    # Use default data directory or provide pdf_paths
    context = JobSearchWorkflowContext(
        query="test",
        location="test",
        data_dir=Path(__file__).parent.parent / "data",
    )

    node = ProfilingNode()
    result = await node.run(context)

    print(f"\n[RESULT]")
    print(f"  - Profile cached: {result.profile_was_cached}")
    print(f"  - Profile name: {result.profile_name}")
    print(f"  - Profile email: {result.profile_email}")
    print(
        f"  - Profile length: {len(result.user_profile) if result.user_profile else 0} chars"
    )
    print(f"  - Errors: {result.errors}")

    return result


async def test_matching_node():
    """Test MatchingNode separately."""
    print("\n" + "=" * 80)
    print("TEST: MatchingNode")
    print("=" * 80)

    # First need jobs and profile - can use discovery and profiling nodes
    print("[SETUP] Running discovery and profiling nodes first...")
    discovery_context = JobSearchWorkflowContext(
        query="software engineer",
        location="Hong Kong",
        num_results=3,
    )
    discovery_node = DiscoveryNode()
    discovery_result = await discovery_node.run(discovery_context)

    profiling_context = JobSearchWorkflowContext(
        query="test",
        location="test",
        data_dir=Path(__file__).parent.parent / "data",
    )
    profiling_node = ProfilingNode()
    profiling_result = await profiling_node.run(profiling_context)

    # Now test matching
    context = JobSearchWorkflowContext(
        query="software engineer",
        location="Hong Kong",
        jobs=discovery_result.jobs,
        job_search_id=discovery_result.job_search_id,
        user_profile=profiling_result.user_profile,
        max_screening=2,
    )

    node = MatchingNode()
    result = await node.run(context)

    print(f"\n[RESULT]")
    print(f"  - Jobs screened: {len(result.all_screening_results)}")
    print(f"  - Matches found: {len(result.matched_results)}")
    print(f"  - Errors: {result.errors}")

    if result.matched_results:
        print(f"\n[MATCHES]")
        for i, match in enumerate(result.matched_results, 1):
            print(f"  {i}. {match.job_title} at {match.job_company}")
            print(f"     - Match: {match.is_match}")
            print(f"     - Reason: {match.reason[:100]}...")

    return result


async def test_research_node():
    """Test ResearchNode separately."""
    print("\n" + "=" * 80)
    print("TEST: ResearchNode")
    print("=" * 80)

    # Need a run_id with matched jobs
    print("[SETUP] Creating run with matched jobs...")
    session = next(db_session())
    try:
        # Create a test run
        run = Run(status="processing")
        session.add(run)
        session.commit()
        session.refresh(run)

        # Get or create a matched job for testing
        matched_jobs = session.query(MatchedJob).filter_by(run_id=run.id).limit(1).all()

        if not matched_jobs:
            print("  ⚠️  No matched jobs found. Run matching node first.")
            return None

        context = JobSearchWorkflowContext(
            query="test",
            location="test",
            run_id=run.id,
        )

        node = ResearchNode()
        result = await node.run(context)

        print(f"\n[RESULT]")
        print(f"  - Run ID: {result.run_id}")
        print(f"  - Errors: {result.errors}")

        return result
    finally:
        try:
            next(db_session(), None)
        except StopIteration:
            pass
        session.close()


async def test_fabrication_node():
    """Test FabricationNode separately."""
    print("\n" + "=" * 80)
    print("TEST: FabricationNode")
    print("=" * 80)

    # Need a run_id with matched jobs that have completed research
    print("[SETUP] Need run_id with matched jobs that have completed research...")
    session = next(db_session())
    try:
        # Find a run with matched jobs that have completed research
        matched_jobs = (
            session.query(MatchedJob)
            .filter_by(research_status="completed")
            .limit(1)
            .all()
        )

        if not matched_jobs:
            print("  ⚠️  No matched jobs with completed research found.")
            print("     Run research node first.")
            return None

        run_id = matched_jobs[0].run_id
        context = JobSearchWorkflowContext(
            query="test",
            location="test",
            run_id=run_id,
        )

        node = FabricationNode()
        result = await node.run(context)

        print(f"\n[RESULT]")
        print(f"  - Run ID: {result.run_id}")
        print(f"  - Errors: {result.errors}")

        return result
    finally:
        try:
            next(db_session(), None)
        except StopIteration:
            pass
        session.close()


async def test_completion_node():
    """Test CompletionNode separately."""
    print("\n" + "=" * 80)
    print("TEST: CompletionNode")
    print("=" * 80)

    # Need a run_id
    print("[SETUP] Finding a run to test...")
    session = next(db_session())
    try:
        run = session.query(Run).first()
        if not run:
            print("  ⚠️  No runs found in database.")
            return None

        context = JobSearchWorkflowContext(
            query="test",
            location="test",
            run_id=run.id,
        )

        node = CompletionNode()
        result = await node.run(context)

        print(f"\n[RESULT]")
        print(f"  - Run ID: {result.run_id}")
        print(f"  - Errors: {result.errors}")

        return result
    finally:
        try:
            next(db_session(), None)
        except StopIteration:
            pass
        session.close()


async def test_delivery_node():
    """Test DeliveryNode separately - sends actual email."""
    print("\n" + "=" * 80)
    print("TEST: DeliveryNode")
    print("=" * 80)
    print("\n⚠️  WARNING: This test will send an actual email!")
    print("   Make sure NYLAS_API_KEY and NYLAS_GRANT_ID are set in your .env file")

    # Need a run_id with completed items
    print("\n[SETUP] Finding a run with completed items...")
    session = next(db_session())
    try:
        from src.workflow.nodes.completion_node import check_run_completion
        from src.workflow.nodes.delivery_node import get_completed_items_for_delivery

        # Find runs with completed items
        runs = session.query(Run).all()
        completed_runs = []
        for run in runs:
            if check_run_completion(session, str(run.id)):
                completed_items = get_completed_items_for_delivery(session, str(run.id))
                if completed_items:
                    completed_runs.append((run, len(completed_items)))

        if not completed_runs:
            print("  ⚠️  No completed runs with items ready for delivery found.")
            print(
                "     Complete a workflow first (research + fabrication must be done)."
            )
            return None

        # Let user choose which run to test
        if len(completed_runs) > 1:
            print(f"\n[SELECT RUN] Found {len(completed_runs)} completed run(s):")
            for i, (run, item_count) in enumerate(completed_runs, 1):
                print(
                    f"  {i}. Run {str(run.id)[:8]}... ({item_count} item(s), created: {run.created_at})"
                )

            while True:
                try:
                    choice = input(
                        f"\nSelect run (1-{len(completed_runs)}) or 'q' to quit: "
                    ).strip()
                    if choice.lower() == "q":
                        return None
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(completed_runs):
                        selected_run, item_count = completed_runs[choice_num - 1]
                        break
                    else:
                        print(
                            f"Please enter a number between 1 and {len(completed_runs)}"
                        )
                except ValueError:
                    print("Please enter a valid number or 'q' to quit")
        else:
            selected_run, item_count = completed_runs[0]
            print(
                f"\n[SELECTED] Using run {str(selected_run.id)[:8]}... with {item_count} item(s)"
            )

        # Show what will be sent
        completed_items = get_completed_items_for_delivery(
            session, str(selected_run.id)
        )
        print(f"\n[EMAIL PREVIEW]")
        print(f"  - Total items: {len(completed_items)}")
        print(f"  - Jobs to include:")
        for i, item in enumerate(completed_items, 1):
            print(f"    {i}. {item['job_title']} at {item['company_name']}")
            print(
                f"       - Cover letter: {'✓' if item.get('cover_letter', {}).get('content') else '✗'}"
            )
            print(
                f"       - CV PDF: {'✓' if item.get('cv', {}).get('pdf_url') else '✗'}"
            )

        # Confirm before sending
        print("\n" + "=" * 80)
        confirm = input("Send email? (yes/no): ").strip().lower()
        if confirm not in ["yes", "y"]:
            print("Email sending cancelled.")
            return None

        context = JobSearchWorkflowContext(
            query="test",
            location="test",
            run_id=selected_run.id,
        )

        node = DeliveryNode()
        result = await node.run(context)

        print(f"\n[RESULT]")
        print(f"  - Run ID: {result.run_id}")
        if result.errors:
            print(f"  - Errors: {result.errors}")
        else:
            print(f"  - ✓ Delivery node completed successfully")
            print(f"  - Check your email inbox for the application packages!")

        return result
    finally:
        try:
            next(db_session(), None)
        except StopIteration:
            pass
        session.close()


# ============================================================================
# Complete Workflow Test
# ============================================================================


async def test_complete_workflow():
    """Test the complete JobSearchWorkflow."""
    print("\n" + "=" * 80)
    print("TEST: Complete JobSearchWorkflow")
    print("=" * 80)

    # Test with different job queries
    test_queries = [
        "startup ai engineer",
        # "nextjs developer",
        # "ai engineer",
    ]

    for query in test_queries:
        print(f"\n{'#' * 80}")
        print(f"Testing query: '{query}'")
        print(f"{'#' * 80}\n")

        try:
            context = JobSearchWorkflow.Context(
                query=query,
                location="Hong Kong",
                num_results=10,
                max_screening=3,
                data_dir=Path(__file__).parent.parent / "data",
            )

            workflow = JobSearchWorkflow()
            result = await workflow.run(context)

            # Get summary from context
            summary = result.get_summary()

            print(f"\n[TEST RESULT] Summary for '{query}':")
            print(f"  - Jobs found: {summary['jobs_found']}")
            print(f"  - Jobs screened: {summary['jobs_screened']}")
            print(f"  - Matches found: {summary['matches_found']}")
            print(f"  - Profile cached: {summary['profile_cached']}")
            print(f"  - Has errors: {summary['has_errors']}")
            print(f"  - Run ID: {result.run_id}")

            print("\n[WORKFLOW STEPS COMPLETED]")
            print("  ✓ Step 1: Run created")
            print("  ✓ Step 2: Discovery")
            print("  ✓ Step 3: Profiling")
            print("  ✓ Step 4: Matching")
            if result.run_id and result.matched_results:
                print("  ✓ Step 5: Research")
                print("  ✓ Step 6: Fabrication")
                print("  ✓ Step 7: Completion detection")
                print("  ✓ Step 8: Delivery")

            if result.has_errors():
                print("\n[WARNINGS] Errors encountered:")
                for error in result.errors:
                    print(f"  - {error}")

            # Verify Run was created and check its status
            if result.run_id:
                print("\n[VERIFICATION] Checking Run status in database...")
                session = next(db_session())
                try:
                    run_record = session.query(Run).filter_by(id=result.run_id).first()
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

                        # Check WorkflowExecution record
                        execution = (
                            session.query(WorkflowExecution)
                            .filter_by(run_id=result.run_id)
                            .first()
                        )
                        if execution:
                            print(f"\n  ✓ WorkflowExecution found:")
                            print(f"    - Status: {execution.status}")
                            print(f"    - Current node: {execution.current_node}")
                            print(f"    - Started at: {execution.started_at}")
                            print(f"    - Completed at: {execution.completed_at}")

                        # Check matched jobs status
                        matched_jobs = (
                            session.query(MatchedJob)
                            .filter_by(run_id=result.run_id)
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

                                # Check for artifact (cover letter)
                                # Artifact already imported from top-level
                                artifact = (
                                    session.query(Artifact)
                                    .filter_by(matched_job_id=mj.id)
                                    .first()
                                )
                                print(
                                    f"       - Has cover letter: {'✓' if (artifact and artifact.cover_letter) else '✗'}"
                                )

                        # Verify completion
                        from src.workflow.nodes.completion_node import (
                            check_run_completion,
                        )
                        from src.workflow.nodes.delivery_node import (
                            get_completed_items_for_delivery,
                        )

                        is_complete = check_run_completion(session, str(result.run_id))
                        print("\n  [COMPLETION CHECK]")
                        print(f"    - Run is complete: {'✓' if is_complete else '✗'}")

                        if is_complete:
                            completed_items = get_completed_items_for_delivery(
                                session, str(result.run_id)
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
                        print(f"  ❌ Run {result.run_id} not found in database")
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


# ============================================================================
# Main Test Runner
# ============================================================================


async def run_all_node_tests():
    """Run all individual node tests."""
    print("\n" + "=" * 80)
    print("RUNNING ALL NODE TESTS")
    print("=" * 80)

    await test_discovery_node()
    await test_profiling_node()
    await test_matching_node()
    # Note: Research, Fabrication, Completion, and Delivery nodes
    # require previous steps to be completed, so they may skip if no data exists


def display_menu():
    """Display interactive menu for test selection."""
    print("\n" + "=" * 80)
    print("WORKFLOW & NODE TESTING MENU")
    print("=" * 80)
    print("\nSelect a test to run:")
    print()
    print("  1. Discovery Node - Test job discovery")
    print("  2. Profiling Node - Test user profile extraction")
    print("  3. Matching Node - Test job matching")
    print("  4. Research Node - Test company research")
    print("  5. Fabrication Node - Test cover letter/CV generation")
    print("  6. Completion Node - Test completion detection")
    print("  7. Delivery Node - Test email delivery (sends actual email!)")
    print("  8. Complete Workflow - Test full workflow end-to-end")
    print("  9. Run All Node Tests - Run discovery, profiling, matching")
    print()
    print("  0. Exit")
    print()


async def interactive_main():
    """Interactive CLI for test selection."""
    while True:
        display_menu()
        choice = input("Enter your choice (0-9): ").strip()

        if choice == "0":
            print("\nExiting...")
            break
        elif choice == "1":
            await test_discovery_node()
        elif choice == "2":
            await test_profiling_node()
        elif choice == "3":
            await test_matching_node()
        elif choice == "4":
            await test_research_node()
        elif choice == "5":
            await test_fabrication_node()
        elif choice == "6":
            await test_completion_node()
        elif choice == "7":
            await test_delivery_node()
        elif choice == "8":
            await test_complete_workflow()
        elif choice == "9":
            await run_all_node_tests()
        else:
            print("\n❌ Invalid choice. Please enter a number between 0-9.")
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


async def main():
    """Main test runner with both CLI and argument parsing support."""
    import sys
    import argparse

    # If no arguments provided, show interactive menu
    if len(sys.argv) == 1:
        await interactive_main()
        return

    # Otherwise, use argument parser for command-line mode
    parser = argparse.ArgumentParser(description="Test workflow and nodes")
    parser.add_argument(
        "--test",
        choices=[
            "all",
            "workflow",
            "nodes",
            "discovery",
            "profiling",
            "matching",
            "research",
            "fabrication",
            "completion",
            "delivery",
        ],
        help="Which test to run (if not provided, shows interactive menu)",
    )

    args = parser.parse_args()

    # If --test not provided, show interactive menu
    if not args.test:
        await interactive_main()
    elif args.test == "all":
        await run_all_node_tests()
        await test_complete_workflow()
    elif args.test == "workflow":
        await test_complete_workflow()
    elif args.test == "nodes":
        await run_all_node_tests()
    elif args.test == "discovery":
        await test_discovery_node()
    elif args.test == "profiling":
        await test_profiling_node()
    elif args.test == "matching":
        await test_matching_node()
    elif args.test == "research":
        await test_research_node()
    elif args.test == "fabrication":
        await test_fabrication_node()
    elif args.test == "completion":
        await test_completion_node()
    elif args.test == "delivery":
        await test_delivery_node()


if __name__ == "__main__":
    asyncio.run(main())
