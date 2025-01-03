"""Arborist - A focused git branch cleanup tool.

A simple tool for cleaning up git branches that are merged or gone.
Features:
- List branch status (merged, unmerged, gone)
- Clean up merged and gone branches
- Protect branches using glob patterns
- Interactive mode with confirmation prompts
- Dry run option to preview changes
"""

from arborist.git import GitRepo, GitError, BranchStatus

__all__ = ["GitRepo", "GitError", "BranchStatus"]
