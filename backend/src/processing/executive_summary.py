"""Executive summary extraction from assessment reports."""

import logging
import math
from typing import Dict, Any, List, Optional

from ..models.outputs import AnalyzedFacts, SIPerformance, SavingsPlan, ReservedInstance, ExecutiveSummaryData
from .excel_processor import ExcelProcessor

logger = logging.getLogger(__name__)


class ExecutiveSummaryExtractor:
    """
    Extract and structure executive summary data from assessment reports.

    Combines data from multiple sheets:
    - Analyzed Facts
    - SI Performance
    - savings_plans.csv
    - reserved_instances.csv
    """

    def __init__(self, excel_processor: ExcelProcessor):
        """
        Initialize executive summary extractor.

        Args:
            excel_processor: ExcelProcessor instance for the report
        """
        self.processor = excel_processor

    def extract(self) -> ExecutiveSummaryData:
        """
        Extract executive summary data from all relevant sheets.

        Returns:
            ExecutiveSummaryData object
        """
        # Extract formatted executive summary sections
        executive_summary_sections = self._extract_executive_summary_sections()

        # Extract analyzed facts
        analyzed_facts = self._prune_analyzed_facts(self._extract_analyzed_facts())

        # Extract SI performance
        si_performance = self._extract_si_performance()

        # Extract current commitments
        current_commitments = self._prune_current_commitments(self._extract_current_commitments())

        # Extract key recommendations
        key_recommendations = self._prune_key_recommendations(self._extract_key_recommendations())

        return ExecutiveSummaryData(
            executive_summary_sections=executive_summary_sections,
            analyzed_facts=analyzed_facts,
            si_performance=si_performance,
            current_commitments=current_commitments,
            key_recommendations=key_recommendations,
        )

    def _extract_executive_summary_sections(self) -> Dict[str, Any]:
        """
        Extract structured sections from the formatted Executive Summary sheet.
        
        Returns a well-structured dictionary with semantic keys organized by section.
        Each section contains logically grouped metrics with descriptive names.
        
        Structure:
        {
            "summary": {
                "current_metrics": {...},
                "edp_discounts": {...},
                "coverage_metrics": {...},
                "workload_analysis": {...}
            },
            "spot": {
                "discount_metrics": {...},
                "commitment_analysis": {...},
                "flexibility_metrics": {...}
            },
            ...
        }
        """
        sheet_name = "Executive Summary"
        if sheet_name not in self.processor.get_sheet_names():
            return {}

        try:
            workbook = self.processor.workbook
            if workbook is None:
                return {}
            sheet = workbook[sheet_name]
            
            # First pass: collect raw data organized by sections
            raw_sections: Dict[str, List[Dict[str, Any]]] = {}
            current_section = "summary"

            for row in sheet.iter_rows(values_only=True):
                values = [self._normalize_cell_value(cell) for cell in row]
                non_empty_values = [value for value in values if value not in (None, "", 0.0)]

                if not non_empty_values:
                    continue

                # Detect section headers (single string value in row)
                if len(non_empty_values) == 1 and isinstance(non_empty_values[0], str):
                    heading = non_empty_values[0].strip()
                    if heading:
                        current_section = self._normalize_section_name(heading)
                        raw_sections.setdefault(current_section, [])
                    continue

                # Extract label and values from row
                label = None
                metrics: List[Any] = []

                for value in non_empty_values:
                    if label is None and isinstance(value, str):
                        label = value.strip()
                    else:
                        metrics.append(value)

                if label is None:
                    continue  # Skip rows without labels

                cleaned_metrics = [metric for metric in metrics if metric not in (None, "", 0.0)]
                
                raw_sections.setdefault(current_section, []).append({
                    "label": label,
                    "values": cleaned_metrics
                })

            # Second pass: structure the data semantically
            structured_sections = {}
            for section_name, items in raw_sections.items():
                if not items:
                    continue
                structured_sections[section_name] = self._structure_section_data(section_name, items)

            return structured_sections
        except Exception as e:
            logger.exception("Error extracting formatted Executive Summary sheet '%s': %s", sheet_name, e)
            return {}

    def _normalize_section_name(self, heading: str) -> str:
        """Normalize section heading to a consistent key format."""
        # Convert to lowercase and replace spaces with underscores
        normalized = heading.lower().strip()
        normalized = normalized.replace(" ", "_")
        normalized = normalized.replace("-", "_")
        # Remove special characters except underscores
        normalized = "".join(c for c in normalized if c.isalnum() or c == "_")
        return normalized or "unknown_section"

    def _structure_section_data(self, section_name: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Structure raw section data into semantic groups with descriptive keys.
        
        Args:
            section_name: The section identifier (e.g., "summary", "spot")
            items: List of label-value pairs from the Excel sheet
            
        Returns:
            Structured dictionary with semantic groupings
        """
        structured: Dict[str, Any] = {}
        
        # Group items by semantic categories based on their labels
        for item in items:
            label = item["label"]
            values = item["values"]
            
            # Convert label to a semantic key
            key = self._label_to_key(label)
            
            # Determine the appropriate grouping and structure
            group_name, metric_name = self._categorize_metric(section_name, label, key)
            
            # Initialize group if needed
            if group_name not in structured:
                structured[group_name] = {}
            
            # Store the value(s) appropriately
            if len(values) == 0:
                structured[group_name][metric_name] = None
            elif len(values) == 1:
                structured[group_name][metric_name] = values[0]
            else:
                # Multiple values - store as a structured object if possible
                structured[group_name][metric_name] = self._structure_multiple_values(label, values)
        
        return structured

    def _label_to_key(self, label: str) -> str:
        """Convert a label to a semantic key."""
        # Convert to lowercase and replace spaces/special chars with underscores
        key = label.lower().strip()
        key = key.replace(" ", "_")
        key = key.replace("-", "_")
        key = key.replace("(", "")
        key = key.replace(")", "")
        key = key.replace("%", "percent")
        key = key.replace("/", "_per_")
        key = key.replace("$", "")
        # Remove special characters except underscores
        key = "".join(c for c in key if c.isalnum() or c == "_")
        # Remove consecutive underscores
        while "__" in key:
            key = key.replace("__", "_")
        return key.strip("_")

    def _categorize_metric(self, section_name: str, label: str, key: str) -> tuple[str, str]:
        """
        Categorize a metric into a logical group and assign a descriptive name.
        
        Args:
            section_name: The section this metric belongs to
            label: Original label from Excel
            key: Normalized key version of the label
            
        Returns:
            Tuple of (group_name, metric_name)
        """
        label_lower = label.lower()
        
        # Define categorization rules based on keywords in labels
        if any(word in label_lower for word in ["unused", "contract", "region", "pricing", "cost", "hourly"]):
            return ("current_metrics", key)
        
        elif any(word in label_lower for word in ["edp", "discount", "ri fees", "sp fees", "ec2 sp"]):
            return ("edp_discounts", key)
        
        elif any(word in label_lower for word in ["coverage", "max savings", "average"]):
            return ("coverage_metrics", key)
        
        elif any(word in label_lower for word in ["stable", "fluctuation", "workload", "pattern"]):
            return ("workload_analysis", key)
        
        elif any(word in label_lower for word in ["commitment", "additional", "per hour", "per month"]):
            return ("commitment_analysis", key)
        
        elif any(word in label_lower for word in ["flexibility", "cash flow"]):
            return ("flexibility_metrics", key)
        
        elif any(word in label_lower for word in ["net effective", "projected"]):
            return ("discount_metrics", key)
        
        elif any(word in label_lower for word in ["savings", "opportunity"]):
            return ("savings_metrics", key)
        
        # Default grouping
        return ("other_metrics", key)

    def _structure_multiple_values(self, label: str, values: List[Any]) -> Any:
        """
        Structure multiple values intelligently based on context.
        
        Args:
            label: The metric label
            values: List of values to structure
            
        Returns:
            Structured representation of the values
        """
        # If all values are numeric, return as array
        if all(isinstance(v, (int, float)) for v in values):
            return values
        
        # If mixed types, try to create a structured object
        # Look for patterns like [name, value, name, value]
        if len(values) % 2 == 0:
            structured = {}
            for i in range(0, len(values), 2):
                if isinstance(values[i], str):
                    key = self._label_to_key(values[i])
                    structured[key] = values[i + 1]
            if structured:
                return structured
        
        # Otherwise return as array with type preservation
        return values

    def _extract_analyzed_facts(self) -> AnalyzedFacts:
        """Extract key facts from Analyzed Facts sheet."""
        try:
            facts_dict = self.processor.extract_key_value_pairs(
                sheet_name="Analyzed Facts", key_column=0, value_column=1
            )

            # Map to AnalyzedFacts model
            return AnalyzedFacts(
                total_public_pricing_cost=self._get_float(facts_dict, "total_public_pricing_cost"),
                current_coverage=self._get_float(facts_dict, "current_coverage"),
                savings_model_1=self._get_float(facts_dict, "savings_model_1"),
                net_effective_discount_model_1=self._get_float(facts_dict, "net_effective_discount_model_1"),
                stable_workload_percentage=self._get_float(facts_dict, "stable_workload_percentage"),
                additional_savings=self._get_float(facts_dict, "additional_savings"),
                non_ec2_savings_1yr_ris=self._get_float(facts_dict, "non_ec2_savings_1yr_ris"),
                non_ec2_savings_3yr_ris=self._get_float(facts_dict, "non_ec2_savings_3yr_ris"),
                current_coverage_percentage=self._get_float(facts_dict, "current_coverage_percentage"),
                dh_coverage=self._get_float(facts_dict, "dh_coverage"),
                net_effective_discount_current_state=self._get_float(
                    facts_dict, "net_effective_discount_current_state"
                ),
                fluctuation_workload_percentage=self._get_float(facts_dict, "fluctuation_workload_percentage"),
            )
        except Exception as e:
            logger.exception("Error extracting analyzed facts from sheet 'Analyzed Facts': %s", e)
            return AnalyzedFacts()

    def _extract_si_performance(self) -> List[SIPerformance]:
        """Extract SI Performance metrics."""
        try:
            data = self.processor.sheet_to_json("SI Performance", include_headers=True)

            si_list = []
            for row in data:
                try:
                    covered_cost = self._get_required_float(row, "covered cost")
                    actual_cost = self._get_required_float(row, "actual cost")
                    discount = self._get_required_float(row, "discount")
                    utilization = self._get_required_float(row, "utilization")
                    coverage = self._get_required_float(row, "coverage")

                    if not any(value != 0.0 for value in [covered_cost, actual_cost, discount, utilization, coverage]):
                        continue

                    si = SIPerformance(
                        type=str(row.get("type", "")),
                        **{"class": str(row.get("class", ""))},
                        term=str(row.get("term", "")),
                        covered_cost=covered_cost,
                        actual_cost=actual_cost,
                        discount=discount,
                        utilization=utilization,
                        coverage=coverage,
                    )
                    si_list.append(si)
                except Exception as e:
                    logger.exception("Error parsing SI Performance row %r: %s", row, e)
                    continue

            return si_list
        except Exception as e:
            logger.exception("Error extracting SI Performance from sheet 'SI Performance': %s", e)
            return []

    def _extract_current_commitments(self) -> Dict[str, Any]:
        """Extract current commitments (SPs and RIs)."""
        commitments = {
            "savings_plans": [],
            "reserved_instances": [],
            "reserved_instances_count": 0,
            "total_monthly_ri_fee": 0.0,
            "total_monthly_sp_commitment": 0.0,
        }

        # Extract Savings Plans
        try:
            sp_data = self.processor.sheet_to_json("savings_plans.csv", include_headers=True)

            for row in sp_data:
                try:
                    monthly_commitment = self._get_required_float(row, "monthly_commitment")
                    hourly_commitment = self._get_optional_float(row, "hourly_commitment")
                    amortized_fee = self._get_optional_float(row, "amortized_fee")

                    if monthly_commitment == 0.0 and not any(
                        value not in (None, 0.0) for value in [hourly_commitment, amortized_fee]
                    ):
                        continue

                    sp = SavingsPlan(
                        offering_type=str(row.get("offering_type", "")),
                        payment_option=str(row.get("payment_option", "")),
                        term=str(row.get("term", "")),
                        end_date=str(row.get("end_date", "")),
                        monthly_commitment=monthly_commitment,
                        hourly_commitment=hourly_commitment,
                        amortized_fee=amortized_fee,
                    )
                    commitments["savings_plans"].append(sp.dict(exclude_none=True))
                    commitments["total_monthly_sp_commitment"] += sp.monthly_commitment
                except Exception as e:
                    logger.exception("Error parsing Savings Plan row %r: %s", row, e)
                    continue
        except Exception as e:
            logger.exception("Error extracting Savings Plans from sheet 'savings_plans.csv': %s", e)

        # Extract Reserved Instances
        try:
            ri_data = self.processor.sheet_to_json("reserved_instances.csv", include_headers=True)

            for row in ri_data:
                try:
                    instance_count = self._get_optional_int(row, "instance_count")
                    hourly_fee = self._get_optional_float(row, "hourly_fee")
                    monthly_fee = self._get_required_float(row, "monthly_fee")

                    if monthly_fee == 0.0 and instance_count in (None, 0) and hourly_fee in (None, 0.0):
                        continue

                    ri = ReservedInstance(
                        product_region=str(row.get("product_region", "")),
                        offering_type=str(row.get("offering_type", "")),
                        purchase_option=str(row.get("purchase_option", "")),
                        term=str(row.get("term", "")),
                        end_date=str(row.get("end_date", "")),
                        instance_type=str(row.get("instance_type", "")),
                        instance_count=instance_count,
                        hourly_fee=hourly_fee,
                        monthly_fee=monthly_fee,
                    )
                    commitments["reserved_instances"].append(ri.dict(exclude_none=True))
                    commitments["reserved_instances_count"] += 1
                    commitments["total_monthly_ri_fee"] += ri.monthly_fee
                except Exception as e:
                    logger.exception("Error parsing Reserved Instance row %r: %s", row, e)
                    continue
        except Exception as e:
            logger.exception("Error extracting Reserved Instances from sheet 'reserved_instances.csv': %s", e)

        return commitments

    def _extract_key_recommendations(self) -> Dict[str, Any]:
        """Extract key recommendations from various sheets."""
        recommendations = {}

        # Try to get Day 1 optimizations
        try:
            day1_data = self.processor.extract_key_value_pairs(
                sheet_name="Day 1 - Optimizations", key_column=0, value_column=1
            )
            recommendations["day_1_optimizations"] = day1_data
        except Exception:
            pass

        # Try to get non-EC2 analysis
        try:
            non_ec2_data = self.processor.extract_key_value_pairs(
                sheet_name="non_ec2_analysis", key_column=0, value_column=1
            )
            recommendations["non_ec2_analysis"] = non_ec2_data
        except Exception:
            pass

        return recommendations

    def _prune_analyzed_facts(self, analyzed_facts: AnalyzedFacts) -> AnalyzedFacts:
        """Remove zero/empty analyzed facts so only useful metrics remain."""
        filtered_values = {
            key: value
            for key, value in analyzed_facts.dict().items()
            if value is not None and value != 0.0
        }
        return AnalyzedFacts(**filtered_values)

    def _prune_current_commitments(self, commitments: Dict[str, Any]) -> Dict[str, Any]:
        """Remove empty commitment sections and zero-value aggregates."""
        pruned_commitments: Dict[str, Any] = {}

        if commitments.get("savings_plans"):
            pruned_commitments["savings_plans"] = commitments["savings_plans"]

        if commitments.get("reserved_instances"):
            pruned_commitments["reserved_instances"] = commitments["reserved_instances"]

        if commitments.get("reserved_instances_count", 0) > 0:
            pruned_commitments["reserved_instances_count"] = commitments["reserved_instances_count"]

        if commitments.get("total_monthly_ri_fee", 0.0) != 0.0:
            pruned_commitments["total_monthly_ri_fee"] = commitments["total_monthly_ri_fee"]

        if commitments.get("total_monthly_sp_commitment", 0.0) != 0.0:
            pruned_commitments["total_monthly_sp_commitment"] = commitments["total_monthly_sp_commitment"]

        return pruned_commitments

    def _prune_key_recommendations(self, recommendations: Dict[str, Any]) -> Dict[str, Any]:
        """Remove empty or zero-only recommendation sections."""
        pruned_recommendations: Dict[str, Any] = {}

        for section_name, section_data in recommendations.items():
            if not isinstance(section_data, dict):
                continue

            filtered_section = {
                key: value
                for key, value in section_data.items()
                if value is not None and value != 0.0 and value != ""
            }
            if filtered_section:
                pruned_recommendations[section_name] = filtered_section

        return pruned_recommendations

    def _get_float(self, data: Dict[str, Any], key: str) -> Optional[float]:
        """Safely get optional finite float value from dictionary."""
        return self._coerce_optional_float(data.get(key))

    def _get_required_float(self, data: Dict[str, Any], key: str) -> float:
        """Safely get required finite float value from dictionary."""
        value = self._coerce_optional_float(data.get(key))
        return value if value is not None else 0.0

    def _get_optional_float(self, data: Dict[str, Any], key: str) -> Optional[float]:
        """Safely get optional finite float value from dictionary."""
        return self._coerce_optional_float(data.get(key))

    def _get_optional_int(self, data: Dict[str, Any], key: str) -> Optional[int]:
        """Safely get optional finite integer value from dictionary."""
        value = data.get(key)
        if value is None:
            return None
        try:
            numeric_value = float(value)
            if not math.isfinite(numeric_value):
                return None
            return int(numeric_value)
        except (ValueError, TypeError):
            return None

    def _coerce_optional_float(self, value: Any) -> Optional[float]:
        """Convert a value to a finite float, returning None for NaN/inf/invalid values."""
        if value is None:
            return None
        try:
            numeric_value = float(value)
            if not math.isfinite(numeric_value):
                return None
            return numeric_value
        except (ValueError, TypeError):
            return None

    def _normalize_cell_value(self, value: Any) -> Any:
        """Normalize worksheet cell values for structured summary extraction."""
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        if isinstance(value, (int, float)):
            try:
                numeric_value = float(value)
                if not math.isfinite(numeric_value):
                    return None
                return numeric_value
            except (ValueError, TypeError):
                return None
        return str(value).strip() or None

    def get_sheets_included(self) -> List[str]:
        """
        Get list of sheets that were included in the extraction.

        Returns:
            List of sheet names
        """
        sheets = []

        for sheet_name in [
            "Executive Summary",
            "Analyzed Facts",
            "SI Performance",
            "savings_plans.csv",
            "reserved_instances.csv",
            "Day 1 - Optimizations",
            "non_ec2_analysis",
        ]:
            if sheet_name in self.processor.get_sheet_names():
                sheets.append(sheet_name)

        return sheets


# Made with Bob
