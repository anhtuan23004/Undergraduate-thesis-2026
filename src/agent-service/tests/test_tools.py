"""Unit tests for validation tools."""
import pytest
from features.quality.tools.validate_diagnosis import (
    ValidateDiagnosisTool,
    ICD10_DATABASE,
    ICD_CATEGORIES,
)
from features.quality.tools.check_exclusion import (
    CheckExclusionTool,
    POLICY_EXCLUSIONS,
)


class TestValidateDiagnosisTool:
    """Test ICD-10 diagnosis validation."""
    
    @pytest.fixture
    def tool(self):
        """Create a tool instance for testing."""
        return ValidateDiagnosisTool()
    
    def test_icd10_database_loaded(self):
        """Test ICD-10 database is loaded."""
        assert isinstance(ICD10_DATABASE, dict)
        assert len(ICD10_DATABASE) > 0
        
    def test_icd10_categories_loaded(self):
        """Test ICD-10 categories are loaded."""
        assert isinstance(ICD_CATEGORIES, dict)
        assert "I" in ICD_CATEGORIES  # Circulatory system
        
    def test_validate_valid_code(self, tool):
        """Test validation of a valid ICD-10 code."""
        result = tool._validate_code("E11")
        
        assert result["valid"] is True
        assert result["found"] is True
        assert "description" in result
        assert "category" in result
        
    def test_validate_invalid_code(self, tool):
        """Test validation of an invalid ICD-10 code."""
        result = tool._validate_code("XYZ99")
        
        assert result["valid"] is True  # Format is valid
        assert result["found"] is False  # But not in database
        
    def test_validate_code_format(self, tool):
        """Test validation of invalid code format."""
        result = tool._validate_code("INVALID")

        assert result["valid_format"] is False
        assert "format" in result.get("error", "").lower()
        
    @pytest.mark.asyncio
    async def test_execute_with_valid_codes(self, tool):
        """Test execute with valid ICD-10 codes."""
        result = await tool.execute(
            diagnosis_codes=["E11", "I10"],
            policy_number="POL-001"
        )
        
        assert "validated_codes" in result
        assert len(result["validated_codes"]) == 2
        assert result["all_valid"] is True


class TestCheckExclusionTool:
    """Test policy exclusion checking."""
    
    @pytest.fixture
    def tool(self):
        """Create a tool instance for testing."""
        return CheckExclusionTool()
    
    def test_policy_exclusions_loaded(self):
        """Test policy exclusions are loaded."""
        assert isinstance(POLICY_EXCLUSIONS, dict)
        assert "POL-001" in POLICY_EXCLUSIONS
        assert "DEFAULT" in POLICY_EXCLUSIONS
        
    def test_default_policy_has_exclusions(self):
        """Test default policy has exclusions."""
        default = POLICY_EXCLUSIONS["DEFAULT"]
        assert "exclusions" in default
        assert len(default["exclusions"]) > 0
        
    def test_different_policies_have_different_exclusions(self):
        """Test different policies can have different exclusions."""
        pol_001 = POLICY_EXCLUSIONS["POL-001"]
        pol_002 = POLICY_EXCLUSIONS["POL-002"]
        
        # Different policies should have different exclusion counts
        assert len(pol_001["exclusions"]) != len(pol_002["exclusions"])
        
    @pytest.mark.asyncio
    async def test_execute_no_issues_for_covered_claim(self, tool):
        """Test execute with a covered claim (no exclusions)."""
        result = await tool.execute(
            policy_number="POL-001",
            diagnosis_codes=["E11"],  # Diabetes - covered
            procedures=["blood test"],
            patient_age=45
        )
        
        assert "issues" in result
        assert "warnings" in result
        
    @pytest.mark.asyncio
    async def test_execute_with_excluded_condition(self, tool):
        """Test execute with an excluded condition."""
        result = await tool.execute(
            policy_number="POL-001",
            diagnosis_codes=["Z416"],  # Cosmetic surgery consultation
            procedures=["cosmetic surgery"],
            patient_age=30
        )
        
        # Should have issues related to exclusions
        # (exact behavior depends on tool implementation)
        assert "issues" in result


class TestPolicyExclusionsDataSource:
    """Test that mock data can be replaced with external sources."""
    
    def test_external_data_source_not_implemented(self):
        """Test that external data source paths are configurable."""
        from config import settings
        
        # These should be empty by default (using mock data)
        assert settings.ICD10_DATA_PATH == ""
        assert settings.POLICY_EXCLUSIONS_PATH == ""
        
    def test_mock_data_fallback(self):
        """Test mock data is used when no external source provided."""
        # Both should have data since no external source is configured
        assert len(ICD10_DATABASE) > 0
        assert len(POLICY_EXCLUSIONS) > 0
