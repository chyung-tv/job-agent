"""
Delivery module for sending completed application packages to users.

Currently implements a placeholder that prints delivery information.
Future: Will send email with application packages.
"""

from typing import List, Dict
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from src.database.models import Run
from src.workflow.completion import get_completed_items_for_delivery


def trigger_delivery(session: Session, run_id: str) -> Dict[str, any]:
    """
    Trigger delivery for all successfully completed items in a run.
    
    This is a placeholder function that prints delivery information.
    Future implementation will send email with application packages.
    
    Args:
        session: SQLAlchemy database session
        run_id: UUID of the run (as string)
    
    Returns:
        Dictionary with delivery summary
    """
    print("\n" + "=" * 80)
    print("DELIVERING...")
    print("=" * 80)
    
    # Get completed items
    completed_items = get_completed_items_for_delivery(session, run_id)
    
    if not completed_items:
        print("\n⚠️  No completed items found for delivery")
        print("   → All items must have both research and fabrication completed")
        return {
            "run_id": run_id,
            "items_delivered": 0,
            "status": "no_items",
        }
    
    # Update run delivery status
    run = session.query(Run).filter_by(id=uuid.UUID(run_id)).first()
    if run:
        run.delivery_triggered = True
        run.delivery_triggered_at = datetime.utcnow()
        session.commit()
    
    # Print delivery summary
    print(f"\n📦 Preparing to deliver {len(completed_items)} application package(s):\n")
    
    for i, item in enumerate(completed_items, 1):
        print(f"{i}. {item['job_title']} at {item['company_name']}")
        print(f"   Location: {item['location']}")
        print(f"   Research: {'✓' if item['research']['results'] else '✗'}")
        print(f"   Cover Letter: {'✓' if item['cover_letter']['content'] else '✗'}")
        if item['cover_letter']['content']:
            subject = item['cover_letter']['content'].get('subject_line', 'N/A')
            print(f"   Subject: {subject}")
        print(f"   CV: {'✓' if item.get('cv', {}).get('pdf_url') else '✗'}")
        if item.get('cv', {}).get('pdf_url'):
            print(f"   CV PDF: {item['cv']['pdf_url']}")
        print()
    
    print("=" * 80)
    print("DELIVERY PLACEHOLDER")
    print("=" * 80)
    print("\n[PLACEHOLDER] In future implementation, this will:")
    print("  1. Package research report, cover letter, and CV")
    print("  2. Send email to user with application packages")
    print("  3. Track delivery status")
    print()
    
    return {
        "run_id": run_id,
        "items_delivered": len(completed_items),
        "status": "delivered",
        "items": completed_items,
    }
