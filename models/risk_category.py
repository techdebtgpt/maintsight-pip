"""Risk categories for maintenance degradation classification."""

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class RiskCategory(Enum):
    """Risk categories based on degradation score thresholds."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    def __str__(self) -> str:
        return self.value

    @property
    def display_name(self) -> str:
        """Human-readable display name."""
        if self.value == "critical":
            return "Critical"
        elif self.value == "high":
            return "High"
        elif self.value == "medium":
            return "Medium"
        elif self.value == "low":
            return "Low"
        else:
            return self.value.title()

    @classmethod
    def from_score(cls, score: float) -> "RiskCategory":
        """Categorize a risk score into risk levels.

        Args:
            score: Risk score (between 0 and 10)

        Returns:
            RiskCategory based on score thresholds

        Thresholds based on training data distribution (0-10 scale):
        - < 5: Low (code quality improving)
        - 5-7: Medium (code quality stable)
        - 7-9: High (code quality declining)
        - >= 9: Critical (rapid quality decline)
        """
        if score < 5:
            return cls.LOW
        elif score < 7:
            return cls.MEDIUM
        elif score < 9:
            return cls.HIGH
        else:
            return cls.CRITICAL
