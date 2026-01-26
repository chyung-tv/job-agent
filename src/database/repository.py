"""Generic repository pattern for database operations."""

from typing import Generic, TypeVar, Type, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

T = TypeVar("T")


class GenericRepository(Generic[T]):
    """Generic repository for database operations.
    
    Provides common CRUD operations for any SQLAlchemy model.
    
    Example:
        ```python
        session = next(db_session())
        job_repo = GenericRepository(session, JobSearch)
        
        # Create
        new_job = JobSearch(...)
        job_repo.create(new_job)
        
        # Read
        job = job_repo.get(job_id)
        all_jobs = job_repo.get_all()
        
        # Update
        job.field = "new_value"
        job_repo.update(job)
        
        # Delete
        job_repo.delete(job_id)
        ```
    """
    
    def __init__(self, session: Session, model: Type[T]):
        """Initialize repository.
        
        Args:
            session: SQLAlchemy session instance
            model: SQLAlchemy model class
        """
        self.session = session
        self.model = model
    
    def create(self, obj: T) -> T:
        """Create a new record.
        
        Args:
            obj: Model instance to create
            
        Returns:
            Created model instance with ID populated
        """
        self.session.add(obj)      # Stage the object
        self.session.commit()       # Save to database
        self.session.refresh(obj)   # Refresh to get database-generated values
        return obj
    
    def get(self, id: str) -> Optional[T]:
        """Get a record by ID.
        
        Args:
            id: Primary key ID
            
        Returns:
            Model instance or None if not found
        """
        return self.session.query(self.model).filter(
            self.model.id == id
        ).first()
    
    def get_all(self) -> List[T]:
        """Get all records.
        
        Returns:
            List of all model instances
        """
        return self.session.query(self.model).all()
    
    def update(self, obj: T) -> T:
        """Update an existing record.
        
        Args:
            obj: Model instance with updated values
            
        Returns:
            Updated model instance
        """
        self.session.merge(obj)    # Merge changes
        self.session.commit()
        self.session.refresh(obj)
        return obj
    
    def delete(self, id: str) -> None:
        """Delete a record by ID.
        
        Args:
            id: Primary key ID
        """
        obj = self.get(id)
        if obj:
            self.session.delete(obj)
            self.session.commit()
    
    def get_latest(self, n: int = 1) -> List[T]:
        """Get the latest N records ordered by ID.
        
        Args:
            n: Number of records to retrieve
            
        Returns:
            List of latest model instances
        """
        return (
            self.session.query(self.model)
            .order_by(desc(self.model.id))
            .limit(n)
            .all()
        )
    
    def count(self) -> int:
        """Count all records.
        
        Returns:
            Total number of records
        """
        return self.session.query(self.model).count()
    
    def filter_by(self, **kwargs) -> List[T]:
        """Filter records by keyword arguments.
        
        Args:
            **kwargs: Field name and value pairs to filter by
            
        Returns:
            List of matching model instances
            
        Example:
            ```python
            jobs = repo.filter_by(location="Hong Kong", is_match=True)
            ```
        """
        return self.session.query(self.model).filter_by(**kwargs).all()
    
    def find_one(self, **kwargs) -> Optional[T]:
        """Find a single record matching the criteria.
        
        Args:
            **kwargs: Field name and value pairs to filter by
            
        Returns:
            First matching model instance or None
        """
        return self.session.query(self.model).filter_by(**kwargs).first()
