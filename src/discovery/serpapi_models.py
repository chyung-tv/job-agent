"""Pydantic models for SerpAPI Google Jobs response structure."""

from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class SearchMetadata(BaseModel):
    """Metadata about the search request and response."""
    
    model_config = ConfigDict(extra="ignore")
    
    id: str
    status: str
    json_endpoint: str
    created_at: str
    processed_at: str
    google_jobs_url: str
    raw_html_file: str
    total_time_taken: float


class SearchParameters(BaseModel):
    """Parameters used for the search."""
    
    model_config = ConfigDict(extra="ignore")
    
    q: str
    engine: str
    google_domain: str
    location: Optional[str] = None
    hl: Optional[str] = None
    gl: Optional[str] = None


class FilterOption(BaseModel):
    """A single filter option."""
    
    model_config = ConfigDict(extra="ignore")
    
    name: str
    link: Optional[str] = None
    serpapi_link: Optional[str] = None
    uds: Optional[str] = None
    q: Optional[str] = None


class Filter(BaseModel):
    """A filter category with options."""
    
    model_config = ConfigDict(extra="ignore")
    
    name: str
    link: Optional[str] = None
    serpapi_link: Optional[str] = None
    uds: Optional[str] = None
    q: Optional[str] = None
    options: Optional[List[FilterOption]] = None


class DetectedExtensions(BaseModel):
    """Detected extensions from job posting."""
    
    model_config = ConfigDict(extra="ignore")
    
    paid_time_off: Optional[bool] = None
    health_insurance: Optional[bool] = None
    dental_coverage: Optional[bool] = None
    posted_at: Optional[str] = None
    schedule_type: Optional[str] = None


class JobHighlight(BaseModel):
    """A highlighted section of the job posting."""
    
    model_config = ConfigDict(extra="ignore")
    
    title: str
    items: List[str]


class ApplyOption(BaseModel):
    """An option for applying to the job."""
    
    model_config = ConfigDict(extra="ignore")
    
    title: str
    link: str


class JobResult(BaseModel):
    """A single job posting result."""
    
    model_config = ConfigDict(extra="ignore")
    
    # Made optional because API sometimes doesn't provide these fields
    title: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    via: Optional[str] = None
    share_link: Optional[str] = None
    thumbnail: Optional[str] = None
    extensions: List[str] = Field(default_factory=list)
    detected_extensions: Optional[DetectedExtensions] = None
    description: Optional[str] = None
    job_highlights: Optional[List[JobHighlight]] = Field(default_factory=list)
    apply_options: List[ApplyOption] = Field(default_factory=list)
    job_id: Optional[str] = None


class SerpApiPagination(BaseModel):
    """Pagination information for SerpAPI results."""
    
    model_config = ConfigDict(extra="ignore")
    
    next_page_token: Optional[str] = None
    next: Optional[str] = None


class SerpApiJobsResponse(BaseModel):
    """Complete SerpAPI Google Jobs API response."""
    
    model_config = ConfigDict(extra="ignore")
    
    search_metadata: SearchMetadata
    search_parameters: SearchParameters
    filters: Optional[List[Filter]] = Field(default_factory=list)
    jobs_results: List[JobResult] = Field(default_factory=list)
    serpapi_pagination: Optional[SerpApiPagination] = None
    
    @classmethod
    def from_serpapi_results(cls, results: dict) -> "SerpApiJobsResponse":
        """Create a SerpApiJobsResponse from SerpAPI results dictionary.
        
        This method includes error handling to ensure the model is always
        properly initialized, even if some fields are missing or malformed.
        
        Args:
            results: The dictionary returned from client.search()
            
        Returns:
            A validated SerpApiJobsResponse instance
            
        Raises:
            ValidationError: If critical required fields are missing
        """
        try:
            # Ensure serpapi_pagination is always present in the dict, even if None
            # This prevents attribute errors when accessing response.serpapi_pagination
            if 'serpapi_pagination' not in results:
                results['serpapi_pagination'] = None
            
            return cls(**results)
        except Exception as e:
            # Log validation errors with context for debugging
            error_msg = f"Failed to create SerpApiJobsResponse: {e}"
            available_keys = list(results.keys()) if isinstance(results, dict) else "N/A"
            error_msg += f"\nAvailable keys in response: {available_keys}"
            
            # Re-raise with more context
            raise ValueError(error_msg) from e
