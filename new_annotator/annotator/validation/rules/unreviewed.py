from annotator.domain.review import is_unreviewed
from annotator.validation.base import ValidationIssue, ValidationRule


class UnreviewedRule(ValidationRule):
    """Images that still hold model annotations nobody has reviewed (Phase 8-A)."""
    name = "Unreviewed"

    def check(self, project, all_annotations):
        issues = []
        for img in project.images:
            pending = [a for a in all_annotations.get(img.path, []) if is_unreviewed(a)]
            if pending:
                issues.append(ValidationIssue(
                    rule_name=self.name,
                    severity="info",
                    image_path=img.path,
                    ann_id=pending[0].id,
                    message=f"{len(pending)} unreviewed model annotation(s)",
                ))
        return issues
