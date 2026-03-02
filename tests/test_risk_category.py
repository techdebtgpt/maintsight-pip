"""Tests for RiskCategory enum."""

from models.risk_category import RiskCategory


class TestRiskCategory:
    """Test cases for RiskCategory enum."""

    def test_enum_values(self):
        """Test enum values are correct."""
        assert RiskCategory.CRITICAL.value == "critical"
        assert RiskCategory.HIGH.value == "high"
        assert RiskCategory.MEDIUM.value == "medium"
        assert RiskCategory.LOW.value == "low"

    def test_display_names(self):
        """Test display names are formatted correctly."""
        assert RiskCategory.CRITICAL.display_name == "Critical"
        assert RiskCategory.HIGH.display_name == "High"
        assert RiskCategory.MEDIUM.display_name == "Medium"
        assert RiskCategory.LOW.display_name == "Low"

    def test_from_score_critical(self):
        """Test critical categorization (>= 9)."""
        assert RiskCategory.from_score(9.0) == RiskCategory.CRITICAL
        assert RiskCategory.from_score(9.5) == RiskCategory.CRITICAL
        assert RiskCategory.from_score(10.0) == RiskCategory.CRITICAL

    def test_from_score_high(self):
        """Test high categorization (7 <= score < 9)."""
        assert RiskCategory.from_score(7.0) == RiskCategory.HIGH
        assert RiskCategory.from_score(8.0) == RiskCategory.HIGH
        assert RiskCategory.from_score(8.9) == RiskCategory.HIGH

    def test_from_score_medium(self):
        """Test medium categorization (5 <= score < 7)."""
        assert RiskCategory.from_score(5.0) == RiskCategory.MEDIUM
        assert RiskCategory.from_score(6.0) == RiskCategory.MEDIUM
        assert RiskCategory.from_score(6.9) == RiskCategory.MEDIUM

    def test_from_score_low(self):
        """Test low categorization (< 5)."""
        assert RiskCategory.from_score(0.0) == RiskCategory.LOW
        assert RiskCategory.from_score(2.5) == RiskCategory.LOW
        assert RiskCategory.from_score(4.9) == RiskCategory.LOW

    def test_string_representation(self):
        """Test string conversion."""
        assert str(RiskCategory.LOW) == "low"
        assert str(RiskCategory.MEDIUM) == "medium"
        assert str(RiskCategory.HIGH) == "high"
        assert str(RiskCategory.CRITICAL) == "critical"
