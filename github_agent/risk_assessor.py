"""Risk assessor for evaluating change risk levels."""

from typing import List, Dict, Optional
from enum import Enum
from dataclasses import dataclass

from .git_utils import DiffResult
from .analyzer import Issue, IssueSeverity, IssueType
from .categorizer import ChangeCategory


class RiskLevel(Enum):
    """Risk assessment levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class RiskAssessment:
    """Result of risk assessment."""
    level: RiskLevel
    score: float
    factors: List[str]
    justification: str


class RiskAssessor:
    """Assesses the risk level of code changes."""
    
    def __init__(self):
        self.assessment: Optional[RiskAssessment] = None
    
    def assess(
        self,
        diff_result: DiffResult,
        issues: List[Issue],
        category: ChangeCategory
    ) -> RiskAssessment:
        """Assess the risk level of the changes."""
        score = 0.0
        factors = []
        
        # Base score from category
        category_scores = {
            ChangeCategory.FEATURE: 3.0,
            ChangeCategory.BUGFIX: 2.0,
            ChangeCategory.REFACTOR: 2.5,
            ChangeCategory.DOCUMENTATION: 0.5,
            ChangeCategory.TEST: 1.0,
            ChangeCategory.CHORE: 0.5,
            ChangeCategory.STYLE: 0.5,
            ChangeCategory.SECURITY: 4.0,
            ChangeCategory.PERFORMANCE: 3.0,
        }
        score += category_scores.get(category, 1.0)
        factors.append(f"Category: {category.value} (+{category_scores.get(category, 1.0)})")
        
        # Score from issues
        severity_weights = {
            IssueSeverity.ERROR: 3.0,
            IssueSeverity.WARNING: 1.5,
            IssueSeverity.INFO: 0.5,
        }
        
        issue_counts = {IssueSeverity.ERROR: 0, IssueSeverity.WARNING: 0, IssueSeverity.INFO: 0}
        for issue in issues:
            issue_counts[issue.severity] += 1
            score += severity_weights[issue.severity]
        
        if issue_counts[IssueSeverity.ERROR] > 0:
            factors.append(f"Found {issue_counts[IssueSeverity.ERROR]} error(s)")
        if issue_counts[IssueSeverity.WARNING] > 0:
            factors.append(f"Found {issue_counts[IssueSeverity.WARNING]} warning(s)")
        if issue_counts[IssueSeverity.INFO] > 0:
            factors.append(f"Found {issue_counts[IssueSeverity.INFO]} info(s)")
        
        # Security issues add significant risk
        security_issues = [i for i in issues if i.issue_type == IssueType.SECURITY]
        if security_issues:
            score += 5.0
            factors.append(f"Security issues detected: {len(security_issues)}")
        
        # Score from change size
        total_changes = diff_result.total_additions + diff_result.total_deletions
        if total_changes > 500:
            score += 2.0
            factors.append(f"Large change: {total_changes} lines modified")
        elif total_changes > 200:
            score += 1.0
            factors.append(f"Medium change: {total_changes} lines modified")
        
        # Score from number of files
        if diff_result.total_files > 20:
            score += 1.5
            factors.append(f"Many files changed: {diff_result.total_files}")
        elif diff_result.total_files > 10:
            score += 0.5
            factors.append(f"Multiple files changed: {diff_result.total_files}")
        
        # File type considerations
        high_risk_extensions = ['.py', '.js', '.ts', '.java', '.go', '.rb']
        critical_files = ['auth', 'security', 'payment', 'config', 'credential']
        
        for file_change in diff_result.files:
            # Check for critical files
            for critical in critical_files:
                if critical in file_change.path.lower():
                    score += 1.0
                    factors.append(f"Critical file modified: {file_change.path}")
                    break
        
        # Determine risk level
        if score >= 6.0:
            level = RiskLevel.HIGH
        elif score >= 3.0:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW
        
        # Generate justification
        justification = self._generate_justification(level, issues, category, diff_result)
        
        self.assessment = RiskAssessment(
            level=level,
            score=score,
            factors=factors,
            justification=justification
        )
        
        return self.assessment
    
    def _generate_justification(
        self,
        level: RiskLevel,
        issues: List[Issue],
        category: ChangeCategory,
        diff_result: DiffResult
    ) -> str:
        """Generate a justification for the risk level."""
        justifications = []
        
        # Primary reason
        if level == RiskLevel.HIGH:
            if any(i.issue_type == IssueType.SECURITY for i in issues):
                justifications.append("Security vulnerabilities detected")
            elif diff_result.total_files > 20:
                justifications.append("Large number of files modified")
            elif len([i for i in issues if i.severity == IssueSeverity.ERROR]) > 2:
                justifications.append("Multiple critical errors found")
            else:
                justifications.append(f"High-risk change type: {category.value}")
        elif level == RiskLevel.MEDIUM:
            if issues:
                issue_summary = f"Found {len(issues)} potential issue(s)"
                justifications.append(issue_summary)
            else:
                justifications.append(f"Moderate change: {category.value}")
        else:
            justifications.append(f"Low-risk change: {category.value}")
        
        # Add evidence
        if issues:
            critical_issues = [i for i in issues if i.severity == IssueSeverity.ERROR]
            if critical_issues:
                sample = critical_issues[0]
                justifications.append(
                    f"Evidence: {sample.message} in {sample.file_path}"
                )
        
        return "; ".join(justifications)
    
    def get_assessment_info(self) -> Dict[str, any]:
        """Get detailed assessment information."""
        if not self.assessment:
            return {}
        
        return {
            'level': self.assessment.level.value,
            'score': self.assessment.score,
            'factors': self.assessment.factors,
            'justification': self.assessment.justification,
        }
