from annotator.validation.base import ValidationIssue, ValidationRule


class EmptyImageRule(ValidationRule):
    name = "EmptyImage"

    def check(self, project, all_annotations):
        issues = []
        for img in project.images:
            if not all_annotations.get(img.path):
                issues.append(ValidationIssue(
                    rule_name=self.name,
                    severity="warning",
                    image_path=img.path,
                    ann_id="",
                    message="No annotations",
                ))
        return issues
