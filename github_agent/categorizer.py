"""Change categorizer for classifying git changes."""

import re
from typing import List, Dict, Optional
from enum import Enum

from .git_utils import FileChange, DiffResult


class ChangeCategory(Enum):
    """Categories of code changes."""
    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    DOCUMENTATION = "documentation"
    TEST = "test"
    CHORE = "chore"
    STYLE = "style"
    SECURITY = "security"
    PERFORMANCE = "performance"


# File patterns for categorization
CATEGORY_PATTERNS = {
    ChangeCategory.FEATURE: [
        r'.*_feature\.py$',
        r'.*features/.*',
        r'.*/new/.*',
        r'.*add_.*\.py$',
        r'.*create_.*\.py$',
    ],
    ChangeCategory.BUGFIX: [
        r'.*_fix\.py$',
        r'.*bug.*\.py$',
        r'.*fix_.*\.py$',
        r'.*repair.*\.py$',
    ],
    ChangeCategory.REFACTOR: [
        r'.*_refactor\.py$',
        r'.*refactor.*',
    ],
    ChangeCategory.DOCUMENTATION: [
        r'.*\.md$',
        r'.*\.rst$',
        r'.*\.txt$',
        r'.*docs?/.*',
        r'.*/doc.*',
    ],
    ChangeCategory.TEST: [
        r'.*test.*\.py$',
        r'.*_test\.py$',
        r'.*tests?/.*',
        r'.*__tests__/.*',
        r'.*spec.*\.py$',
    ],
    ChangeCategory.CHORE: [
        r'.*config.*\.py$',
        r'.*setup\.py$',
        r'.*requirements.*\.txt$',
        r'.*\.env.*',
        r'.*\.gitignore',
    ],
    ChangeCategory.STYLE: [
        r'.*\.css$',
        r'.*\.scss$',
        r'.*\.less$',
        r'.*style.*',
    ],
    ChangeCategory.SECURITY: [
        r'.*security.*',
        r'.*auth.*\.py$',
        r'.*oauth.*',
        r'.*credential.*',
    ],
    ChangeCategory.PERFORMANCE: [
        r'.*performance.*',
        r'.*optim.*\.py$',
    ],
}


# Keywords for commit message-based categorization
CATEGORY_KEYWORDS = {
    ChangeCategory.FEATURE: ['add', 'new', 'feature', 'implement', 'create'],
    ChangeCategory.BUGFIX: ['fix', 'bug', 'repair', 'resolve', 'correct'],
    ChangeCategory.REFACTOR: ['refactor', 'restructure', 'clean', 'improve'],
    ChangeCategory.DOCUMENTATION: ['doc', 'readme', 'comment', 'update docs'],
    ChangeCategory.TEST: ['test', 'spec', 'coverage', 'unittest'],
    ChangeCategory.CHORE: ['chore', 'maintain', 'update deps', 'bump'],
    ChangeCategory.STYLE: ['style', 'format', 'lint', 'prettier'],
    ChangeCategory.SECURITY: ['security', 'auth', 'permission', 'access'],
    ChangeCategory.PERFORMANCE: ['perf', 'optimize', 'speed', 'performance'],
}


class ChangeCategorizer:
    """Categorizes git changes into logical categories."""
    
    def __init__(self):
        self.categories: List[ChangeCategory] = []
        self.primary_category: Optional[ChangeCategory] = None
    
    def categorize(self, diff_result: DiffResult, commit_messages: List[str] = None) -> ChangeCategory:
        """Determine the primary category for the changes."""
        category_scores = {cat: 0 for cat in ChangeCategory}
        
        # Score based on file patterns
        for file_change in diff_result.files:
            for category, patterns in CATEGORY_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, file_change.path, re.IGNORECASE):
                        category_scores[category] += 2
        
        # Score based on commit messages
        if commit_messages:
            all_messages = ' '.join(commit_messages).lower()
            for category, keywords in CATEGORY_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in all_messages:
                        category_scores[category] += 3
        
        # Score based on file status
        for file_change in diff_result.files:
            if file_change.status == 'added':
                category_scores[ChangeCategory.FEATURE] += 1
            elif file_change.status == 'deleted':
                category_scores[ChangeCategory.CHORE] += 1
        
        # Score based on change size
        if diff_result.total_files > 10:
            category_scores[ChangeCategory.CHORE] += 1
        
        # Find the category with highest score
        if category_scores:
            self.primary_category = max(category_scores, key=category_scores.get)
        else:
            self.primary_category = ChangeCategory.CHORE
        
        # Build list of detected categories (score > 0)
        self.categories = [
            cat for cat, score in category_scores.items() 
            if score > 0
        ]
        
        return self.primary_category
    
    def get_category_info(self) -> Dict[str, any]:
        """Get detailed category information."""
        return {
            'primary': self.primary_category.value if self.primary_category else 'unknown',
            'all_detected': [cat.value for cat in self.categories],
            'description': self._get_category_description(self.primary_category),
        }
    
    def _get_category_description(self, category: Optional[ChangeCategory]) -> str:
        """Get a human-readable description of the category."""
        descriptions = {
            ChangeCategory.FEATURE: "New functionality or feature additions",
            ChangeCategory.BUGFIX: "Bug fixes and error corrections",
            ChangeCategory.REFACTOR: "Code restructuring without behavior change",
            ChangeCategory.DOCUMENTATION: "Documentation updates",
            ChangeCategory.TEST: "Test additions or modifications",
            ChangeCategory.CHORE: "Maintenance tasks and dependencies",
            ChangeCategory.STYLE: "Code style and formatting changes",
            ChangeCategory.SECURITY: "Security-related changes",
            ChangeCategory.PERFORMANCE: "Performance optimizations",
        }
        return descriptions.get(category, "Unknown category")
