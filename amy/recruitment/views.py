from typing import Optional

from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Case, Count, IntegerField, Prefetch, Value, When

from recruitment.filters import InstructorRecruitmentFilter
from recruitment.forms import InstructorRecruitmentCreateForm
from workshops.base_views import (
    AMYCreateView,
    AMYDetailView,
    AMYListView,
    ConditionallyEnabledMixin,
    RedirectSupportMixin,
)
from workshops.models import Event, Person, Task
from workshops.util import OnlyForAdminsMixin, human_daterange

from .models import InstructorRecruitment, InstructorRecruitmentSignup

# ------------------------------------------------------------
# InstructorRecruitment related views


class RecruitmentEnabledMixin:
    def get_view_enabled(self) -> bool:
        return settings.INSTRUCTOR_RECRUITMENT_ENABLED is True


class InstructorRecruitmentList(
    OnlyForAdminsMixin, RecruitmentEnabledMixin, ConditionallyEnabledMixin, AMYListView
):
    permission_required = "recruitment.view_instructorrecruitment"
    title = "Recruitment processes"
    filter_class = InstructorRecruitmentFilter

    queryset = (
        InstructorRecruitment.objects.select_related("event")
        .prefetch_related(
            Prefetch(
                "instructorrecruitmentsignup_set",
                queryset=(
                    InstructorRecruitmentSignup.objects.select_related(
                        "recruitment", "person"
                    ).annotate(
                        num_instructor=Count(
                            Case(
                                When(
                                    person__task__role__name="instructor", then=Value(1)
                                ),
                                output_field=IntegerField(),
                            )
                        ),
                        num_supporting=Count(
                            Case(
                                When(
                                    person__task__role__name="supporting-instructor",
                                    then=Value(1),
                                ),
                                output_field=IntegerField(),
                            )
                        ),
                        num_helper=Count(
                            Case(
                                When(person__task__role__name="helper", then=Value(1)),
                                output_field=IntegerField(),
                            )
                        ),
                    )
                ),
            )
        )
        .order_by("-created_at")
    )
    template_name = "recruitment/instructorrecruitment_list.html"

    def get_filter_data(self):
        """If no filter value present for `assigned_to`, set default to current user.

        This means that by default the filter will be set to currently logged-in user;
        it's still possible to clear that filter value, in which case the query param
        will become `?assigned_to=` (empty)."""
        data = super().get_filter_data().copy()
        data.setdefault("assigned_to", self.request.user.pk)
        return data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["personal_conflicts"] = (
            Person.objects.filter(
                instructorrecruitmentsignup__recruitment__in=self.get_queryset()
            )
            .distinct()
            .prefetch_related(
                Prefetch(
                    "task_set",
                    Task.objects.select_related("event", "role").filter(
                        role__name="instructor"
                    ),
                )
            )
        )
        return context


class InstructorRecruitmentCreate(
    OnlyForAdminsMixin,
    PermissionRequiredMixin,
    RedirectSupportMixin,
    RecruitmentEnabledMixin,
    ConditionallyEnabledMixin,
    AMYCreateView,
):
    permission_required = "recruitment.add_instructorrecruitment"
    model = InstructorRecruitment
    template_name = "recruitment/instructorrecruitment_add.html"
    form_class = InstructorRecruitmentCreateForm

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.event: Optional[Event] = None

    def get_other_object(self) -> Event:
        event_id = self.kwargs.get("event_id")
        return Event.objects.select_related("administrator").get(pk=event_id)

    def get(self, request, *args, **kwargs):
        """Load other object upon GET request. Save the request."""
        self.request = request
        self.event = self.get_other_object()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Load other object upon POST request. Save the request."""
        self.request = request
        self.event = self.get_other_object()
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self) -> dict:
        kwargs = super().get_form_kwargs()
        kwargs.update({"prefix": "instructorrecruitment"})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Begin Instructor Selection Process for {self.event}"
        context["event"] = self.event
        context["event_dates"] = human_daterange(
            self.event.start, self.event.end, common_month_left=r"%B %d", range_char="-"
        )
        return context

    def get_initial(self) -> dict:
        try:
            workshop_request = self.event.workshoprequest
            return {
                "notes": (
                    f"{workshop_request.audience_description}\n\n"
                    f"{workshop_request.user_notes}"
                )
            }
        except Event.workshoprequest.RelatedObjectDoesNotExist:
            return {}

    def form_valid(self, form):
        self.object: InstructorRecruitment = form.save(commit=False)
        self.object.assigned_to = self.request.user
        self.object.event = self.event
        self.object.save()
        return super().form_valid(form)


class InstructorRecruitmentDetails(
    OnlyForAdminsMixin,
    RecruitmentEnabledMixin,
    ConditionallyEnabledMixin,
    AMYDetailView,
):
    permission_required = "recruitment.view_instructorrecruitment"
    queryset = InstructorRecruitment.objects.prefetch_related(
        Prefetch(
            "instructorrecruitmentsignup_set",
            queryset=(
                InstructorRecruitmentSignup.objects.select_related(
                    "recruitment", "person"
                ).annotate(
                    num_instructor=Count(
                        Case(
                            When(person__task__role__name="instructor", then=Value(1)),
                            output_field=IntegerField(),
                        )
                    ),
                    num_supporting=Count(
                        Case(
                            When(
                                person__task__role__name="supporting-instructor",
                                then=Value(1),
                            ),
                            output_field=IntegerField(),
                        )
                    ),
                    num_helper=Count(
                        Case(
                            When(person__task__role__name="helper", then=Value(1)),
                            output_field=IntegerField(),
                        )
                    ),
                )
            ),
        )
    )
    template_name = "recruitment/instructorrecruitment_details.html"

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context["title"] = str(self.object)
        return context
