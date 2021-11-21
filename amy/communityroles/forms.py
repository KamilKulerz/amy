from collections import defaultdict
from typing import Any

from django import forms
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from workshops.fields import HeavySelect2Widget, ModelSelect2Widget
from workshops.forms import SELECT2_SIDEBAR, BootstrapHelper, WidgetOverrideMixin

from .models import CommunityRole, CommunityRoleConfig


class CommunityRoleForm(WidgetOverrideMixin, forms.ModelForm):
    class Meta:
        model = CommunityRole
        fields = (
            "config",
            "person",
            "award",
            "start",
            "end",
            "inactivation",
            "membership",
            "url",
            "generic_relation_content_type",
            "generic_relation_pk",
        )
        widgets = {
            "config": HeavySelect2Widget(
                data_view="api:communityroleconfig-list", attrs=SELECT2_SIDEBAR
            ),
            "person": ModelSelect2Widget(
                data_view="person-lookup", attrs=SELECT2_SIDEBAR
            ),
            "award": ModelSelect2Widget(
                data_view="award-lookup", attrs=SELECT2_SIDEBAR
            ),
            "membership": ModelSelect2Widget(
                data_view="membership-lookup", attrs=SELECT2_SIDEBAR
            ),
            "generic_relation_pk": HeavySelect2Widget(
                data_view="generic-object-lookup", attrs=SELECT2_SIDEBAR
            ),
        }

    def __init__(self, *args, **kwargs):
        form_tag = kwargs.pop("form_tag", True)
        super().__init__(*args, **kwargs)
        bootstrap_kwargs = {
            "add_cancel_button": False,
            "form_tag": form_tag,
        }
        self.helper = BootstrapHelper(**bootstrap_kwargs)

    def clean(self) -> dict[str, Any]:
        """Validate form according to rules set up in related Community Role
        configuration."""
        cleaned_data = super().clean()
        errors: defaultdict[str, list[ValidationError]] = defaultdict(list)
        config: CommunityRoleConfig = cleaned_data["config"]

        # Award required?
        if config.link_to_award and not cleaned_data["award"]:
            errors["award"].append(
                ValidationError(f"Award is required with community role {config}")
            )

        # Specific award badge required?
        if (badge := config.award_badge_limit) and (award := cleaned_data["award"]):
            if award.badge != badge:
                errors["award"].append(
                    ValidationError(
                        f"Award badge must be {badge} for community role {config}"
                    )
                )

        # Membership required?
        if config.link_to_membership and not cleaned_data["membership"]:
            errors["membership"].append(
                ValidationError(f"Membership is required with community role {config}")
            )

        # Additional URL supported?
        if not config.additional_url and cleaned_data["url"]:
            errors["url"].append(
                ValidationError(f"URL is not supported for community role {config}")
            )

        # Generic relation must be the same as in configuration
        generic_relation_content_type = cleaned_data["generic_relation_content_type"]
        if config.generic_relation_content_type != generic_relation_content_type:
            errors["generic_relation_content_type"].append(
                ValidationError(
                    "Generic relation type should be "
                    f"{config.generic_relation_content_type} "
                    f"(not {generic_relation_content_type}) for community "
                    f"role {config}"
                )
            )

        # Generic relation object must exist
        if config.generic_relation_content_type and generic_relation_content_type:
            model_class = generic_relation_content_type.model_class()
            try:
                model_class._base_manager.get(pk=cleaned_data["generic_relation_pk"])
            except ObjectDoesNotExist:
                errors["generic_relation_pk"].append(
                    ValidationError(
                        f"Generic relation object of model {model_class.__name__} "
                        "doesn't exist"
                    )
                )

        if errors:
            raise ValidationError(errors)

        return cleaned_data
