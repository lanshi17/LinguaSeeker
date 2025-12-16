# parse base class
from abc import ABC, abstractmethod
class BaseParse(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> str:
        """Parse the file and return its content as a string."""
        pass
    @abstractmethod
    def validate(self, content: str) -> bool:
        """Validate the parsed content."""
        pass
    @abstractmethod
    def save(self, content: str, destination: str) -> None:
        """Save the content to the specified destination."""
        pass
# --- IGNORE ---

