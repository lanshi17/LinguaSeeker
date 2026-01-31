"""Source Coordinates value object.

Immutable value object representing evidence location in source document.
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class BoundingBox:
    """Immutable bounding box coordinates in PDF space."""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        """Validate bounding box."""
        if self.x < 0 or self.y < 0:
            raise ValueError(
                f"Bounding box coordinates ({self.x}, {self.y}) must be non-negative"
            )

        if self.width <= 0 or self.height <= 0:
            raise ValueError(
                f"Bounding box dimensions ({self.width}x{self.height}) must be positive"
            )

    def area(self) -> float:
        """Calculate bounding box area."""
        return self.width * self.height

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for serialization."""
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BoundingBox":
        """Create from dictionary."""
        return cls(
            x=float(data["x"]),
            y=float(data["y"]),
            width=float(data["width"]),
            height=float(data["height"]),
        )

    def overlaps(self, other: "BoundingBox") -> bool:
        """Check if this bounding box overlaps with another."""
        return not (
            self.x + self.width < other.x
            or other.x + other.width < self.x
            or self.y + self.height < other.y
            or other.y + other.height < self.y
        )

    def contains_point(self, x: float, y: float) -> bool:
        """Check if bounding box contains a point."""
        return (
            self.x <= x <= self.x + self.width
            and self.y <= y <= self.y + self.height
        )

    def __repr__(self) -> str:
        """Developer representation."""
        return f"BoundingBox(x={self.x}, y={self.y}, width={self.width}, height={self.height})"


@dataclass(frozen=True)
class SourceCoordinates:
    """Immutable source location coordinates.

    Represents the precise location of evidence in a source document,
    including page number, bounding box, and content hash for traceability.
    """

    page: int
    bounding_box: BoundingBox
    content_hash: str

    def __post_init__(self) -> None:
        """Validate source coordinates."""
        if self.page < 1:
            raise ValueError(f"Page number {self.page} must be positive")

        if len(self.content_hash) != 64:
            raise ValueError(
                f"Content hash must be SHA256 (64 characters), got {len(self.content_hash)}"
            )

    @classmethod
    def create(
        cls,
        page: int,
        x: float,
        y: float,
        width: float,
        height: float,
        content_hash: str,
    ) -> "SourceCoordinates":
        """Create source coordinates with bounding box."""
        bbox = BoundingBox(x=x, y=y, width=width, height=height)
        return cls(page=page, bounding_box=bbox, content_hash=content_hash)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "page": self.page,
            "bounding_box": self.bounding_box.to_dict(),
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceCoordinates":
        """Create from dictionary."""
        bbox = BoundingBox.from_dict(data["bounding_box"])
        return cls(
            page=int(data["page"]),
            bounding_box=bbox,
            content_hash=str(data["content_hash"]),
        )

    def is_on_same_page(self, other: "SourceCoordinates") -> bool:
        """Check if coordinates are on the same page."""
        return self.page == other.page

    def is_from_same_document(self, other: "SourceCoordinates") -> bool:
        """Check if coordinates are from the same document."""
        return self.content_hash == other.content_hash

    def is_nearby(self, other: "SourceCoordinates", max_distance: float = 50.0) -> bool:
        """Check if coordinates are nearby on the same page."""
        if not self.is_on_same_page(other):
            return False

        # Calculate center points
        self_center_x = self.bounding_box.x + self.bounding_box.width / 2
        self_center_y = self.bounding_box.y + self.bounding_box.height / 2
        other_center_x = other.bounding_box.x + other.bounding_box.width / 2
        other_center_y = other.bounding_box.y + other.bounding_box.height / 2

        # Euclidean distance
        distance = (
            (self_center_x - other_center_x) ** 2
            + (self_center_y - other_center_y) ** 2
        ) ** 0.5

        return distance <= max_distance

    def __repr__(self) -> str:
        """Developer representation."""
        return (
            f"SourceCoordinates(page={self.page}, "
            f"bbox={self.bounding_box}, "
            f"hash={self.content_hash[:8]}...)"
        )

    def __str__(self) -> str:
        """String representation."""
        return f"Page {self.page} at ({self.bounding_box.x}, {self.bounding_box.y})"
