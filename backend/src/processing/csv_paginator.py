"""CSV pagination for large data sheets."""

import io
from typing import Tuple

from ..models.outputs import PaginationMetadata


class CSVPaginator:
    """
    Paginate CSV data efficiently.

    Handles line-based pagination with headers included in every page.
    """

    def __init__(self, csv_data: str, page_size: int = 1000):
        """
        Initialize CSV paginator.

        Args:
            csv_data: Full CSV data as string
            page_size: Number of rows per page (excluding headers)
        """
        self.csv_data = csv_data
        self.page_size = page_size
        self.lines = csv_data.strip().split("\n")

        # Assume first line is headers
        self.has_headers = len(self.lines) > 0
        self.header_line = self.lines[0] if self.has_headers else ""
        self.data_lines = self.lines[1:] if self.has_headers else self.lines

        self.total_rows = len(self.data_lines)
        self.total_pages = (self.total_rows + page_size - 1) // page_size if self.total_rows > 0 else 1

    def get_page(self, page: int) -> Tuple[str, PaginationMetadata]:
        """
        Get a specific page of CSV data.

        Args:
            page: Page number (1-based)

        Returns:
            Tuple of (CSV string for page, PaginationMetadata)

        Raises:
            ValueError: If page number is invalid
        """
        if page < 1:
            raise ValueError("Page number must be at least 1")

        if page > self.total_pages:
            raise ValueError(f"Page {page} exceeds total pages {self.total_pages}")

        # Calculate row range
        start_idx = (page - 1) * self.page_size
        end_idx = min(start_idx + self.page_size, self.total_rows)

        # Get data lines for this page
        page_data_lines = self.data_lines[start_idx:end_idx]

        # Build CSV with headers
        csv_lines = []
        if self.has_headers:
            csv_lines.append(self.header_line)
        csv_lines.extend(page_data_lines)

        csv_page = "\n".join(csv_lines)

        # Create pagination metadata
        metadata = PaginationMetadata(
            page=page,
            page_size=self.page_size,
            total_pages=self.total_pages,
            has_next_page=page < self.total_pages,
            has_previous_page=page > 1,
        )

        return csv_page, metadata

    def get_all_pages(self) -> list:
        """
        Get all pages as a list.

        Returns:
            List of (CSV string, PaginationMetadata) tuples
        """
        pages = []
        for page_num in range(1, self.total_pages + 1):
            pages.append(self.get_page(page_num))
        return pages

    @staticmethod
    def paginate_csv(csv_data: str, page: int = 1, page_size: int = 1000) -> Tuple[str, PaginationMetadata]:
        """
        Convenience method to paginate CSV data.

        Args:
            csv_data: Full CSV data as string
            page: Page number (1-based)
            page_size: Number of rows per page

        Returns:
            Tuple of (CSV string for page, PaginationMetadata)
        """
        paginator = CSVPaginator(csv_data, page_size)
        return paginator.get_page(page)

    def get_stats(self) -> dict:
        """
        Get pagination statistics.

        Returns:
            Dictionary with pagination stats
        """
        return {
            "total_rows": self.total_rows,
            "total_pages": self.total_pages,
            "page_size": self.page_size,
            "has_headers": self.has_headers,
            "rows_per_page": [
                min(self.page_size, self.total_rows - (i * self.page_size)) for i in range(self.total_pages)
            ],
        }


# Made with Bob
