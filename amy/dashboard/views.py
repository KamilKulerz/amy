import re
from typing import Dict, Optional

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Case, Count, IntegerField, Prefetch, Q, Value, When
from django.forms.widgets import HiddenInput
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.views.decorators.http import require_GET
from django_comments.models import Comment

from communityroles.models import CommunityRole
from consents.forms import TermBySlugsForm
from consents.models import Consent, TermOption
from dashboard.filters import UpcomingTeachingOpportunitiesFilter
from dashboard.forms import (
    AssignmentForm,
    AutoUpdateProfileForm,
    SearchForm,
    SendHomeworkForm,
)
from fiscal.models import MembershipTask
from recruitment.models import InstructorRecruitment
from recruitment.views import RecruitmentEnabledMixin
from workshops.base_views import AMYListView, ConditionallyEnabledMixin
from workshops.models import (
    Airport,
    Badge,
    Event,
    Membership,
    Organization,
    Person,
    Qualification,
    Tag,
    Task,
    TrainingProgress,
    TrainingRequest,
)
from workshops.util import admin_required, login_required

# Terms shown on the instructor dashboard and can be updated by the user.
TERM_SLUGS = ["may-contact", "public-profile", "may-publish-name"]


@login_required
def dispatch(request):
    """If user is admin, then show them admin dashboard; otherwise redirect
    them to instructor dashboard."""
    if request.user.is_admin:
        return redirect(reverse("admin-dashboard"))
    else:
        return redirect(reverse("instructor-dashboard"))


@admin_required
def admin_dashboard(request):
    """Home page for admins."""
    data = request.GET.copy()
    if "assigned_to" not in data:
        data["assigned_to"] = request.user.id
    assignment_form = AssignmentForm(data)
    assigned_to: Optional[Person] = None
    if assignment_form.is_valid():
        assigned_to = assignment_form.cleaned_data["assigned_to"]

    current_events = Event.objects.current_events().prefetch_related("tags")

    # This annotation may produce wrong number of instructors when
    # `unpublished_events` filters out events that contain a specific tag.
    # The bug was fixed in #1130.
    unpublished_events = (
        Event.objects.active()
        .unpublished_events()
        .select_related("host")
        .annotate(
            num_instructors=Count(
                Case(
                    When(task__role__name="instructor", then=Value(1)),
                    output_field=IntegerField(),
                )
            ),
        )
        .order_by("-start")
    )

    # assigned events that have unaccepted changes
    updated_metadata = Event.objects.active().filter(metadata_changed=True)

    current_events = current_events.filter(assigned_to=assigned_to)
    unpublished_events = unpublished_events.filter(assigned_to=assigned_to)
    updated_metadata = updated_metadata.filter(assigned_to=assigned_to)

    context = {
        "title": None,
        "assignment_form": assignment_form,
        "assigned_to": assigned_to,
        "current_events": current_events,
        "unpublished_events": unpublished_events,
        "updated_metadata": updated_metadata.count(),
        "main_tags": Tag.objects.main_tags(),
    }
    return render(request, "dashboard/admin_dashboard.html", context)


# ------------------------------------------------------------
# Views for instructors and trainees


@login_required
def instructor_dashboard(request):
    qs = Person.objects.select_related("airport").prefetch_related(
        "badges",
        "lessons",
        "domains",
        "languages",
        Prefetch(
            "task_set",
            queryset=Task.objects.select_related("event", "role"),
        ),
        Prefetch(
            "membershiptask_set",
            queryset=MembershipTask.objects.select_related("membership", "role"),
        ),
    )
    user = get_object_or_404(qs, id=request.user.id)

    consents = (
        Consent.objects.active()
        .filter(
            term__slug__in=TERM_SLUGS,
            person=user,
        )
        .select_related("term", "term_option")
    )
    consent_by_term_slug_label: Dict[str, TermOption] = {}
    for consent in consents:
        label = consent.term.slug.replace("-", "_")
        consent_by_term_slug_label[label] = consent.term_option

    context = {"title": "Your profile", "user": user, **consent_by_term_slug_label}
    return render(request, "dashboard/instructor_dashboard.html", context)


@login_required
def autoupdate_profile(request):
    person = request.user
    consent_form_kwargs = {
        "initial": {"person": person},
        "widgets": {"person": HiddenInput()},
        "form_tag": False,
        "prefix": "consents",
    }
    form = AutoUpdateProfileForm(
        instance=person, form_tag=False, add_submit_button=False
    )
    consent_form = TermBySlugsForm(term_slugs=TERM_SLUGS, **consent_form_kwargs)

    if request.method == "POST":
        form = AutoUpdateProfileForm(request.POST, instance=person)
        consent_form = TermBySlugsForm(
            request.POST, term_slugs=TERM_SLUGS, **consent_form_kwargs
        )
        if form.is_valid() and form.instance == person and consent_form.is_valid():
            # save lessons
            person.lessons.clear()
            for lesson in form.cleaned_data["lessons"]:
                q = Qualification(lesson=lesson, person=person)
                q.save()

            # don't save related lessons
            del form.cleaned_data["lessons"]

            person = form.save()

            # save consents
            consent_form.save()

            messages.success(request, "Your profile was updated.")

            return redirect(reverse("instructor-dashboard"))
        else:
            messages.error(request, "Fix errors below.")

    context = {
        "title": "Update Your Profile",
        "form": form,
        "consents_form": consent_form,
    }
    return render(request, "dashboard/autoupdate_profile.html", context)


@login_required
def training_progress(request):
    homework_form = SendHomeworkForm()

    # Add information about instructor training progress to request.user.
    request.user = (
        Person.objects.annotate_with_instructor_eligibility()
        .prefetch_related(
            Prefetch(
                "badges",
                to_attr="instructor_badges",
                queryset=Badge.objects.instructor_badges(),
            ),
        )
        .get(pk=request.user.pk)
    )

    progresses = request.user.trainingprogress_set.filter(discarded=False)
    last_swc_homework = (
        progresses.filter(requirement__name="SWC Homework")
        .order_by("-created_at")
        .first()
    )
    request.user.swc_homework_in_evaluation = (
        last_swc_homework is not None and last_swc_homework.state == "n"
    )
    last_dc_homework = (
        progresses.filter(requirement__name="DC Homework")
        .order_by("-created_at")
        .first()
    )
    request.user.dc_homework_in_evaluation = (
        last_dc_homework is not None and last_dc_homework.state == "n"
    )
    last_lc_homework = (
        progresses.filter(requirement__name="LC Homework")
        .order_by("-created_at")
        .first()
    )
    request.user.lc_homework_in_evaluation = (
        last_lc_homework is not None and last_lc_homework.state == "n"
    )

    if request.method == "POST":
        homework_form = SendHomeworkForm(data=request.POST)
        if homework_form.is_valid():
            # read homework type from POST
            hw_type = homework_form.cleaned_data["requirement"]

            # create "empty" progress object and fill out
            progress = TrainingProgress(
                trainee=request.user,
                state="n",  # not evaluated yet
                requirement=hw_type,
            )

            # create virtual form to validate and save
            form = SendHomeworkForm(data=request.POST, instance=progress)
            if form.is_valid():
                form.save()
                messages.success(
                    request, "Your homework submission will be " "evaluated soon."
                )
                return redirect(reverse("training-progress"))

    context = {
        "title": "Your training progress",
        "homework_form": homework_form,
    }
    return render(request, "dashboard/training_progress.html", context)


# ------------------------------------------------------------
# Views for instructors - upcoming teaching opportunities


class UpcomingTeachingOpportunitiesList(
    LoginRequiredMixin, RecruitmentEnabledMixin, ConditionallyEnabledMixin, AMYListView
):
    permission_required = "recruitment.view_instructorrecruitment"
    title = "Upcoming Teaching Opportunities"
    queryset = InstructorRecruitment.objects.select_related("event").prefetch_related(
        "event__curricula"
    )
    template_name = "dashboard/upcoming_teaching_opportunities.html"
    filter_class = UpcomingTeachingOpportunitiesFilter

    def get_view_enabled(self) -> bool:
        try:
            role = CommunityRole.objects.get(
                person=self.request.user, config__name="instructor"
            )
            return role.is_active() and super().get_view_enabled()
        except CommunityRole.DoesNotExist:
            return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # person details with tasks counted
        context["person"] = (
            Person.objects.annotate(
                num_taught=Count(
                    Case(
                        When(task__role__name="instructor", then=Value(1)),
                        output_field=IntegerField(),
                    )
                ),
                num_supporting=Count(
                    Case(
                        When(task__role__name="supporting-instructor", then=Value(1)),
                        output_field=IntegerField(),
                    )
                ),
                num_helper=Count(
                    Case(
                        When(task__role__name="helper", then=Value(1)),
                        output_field=IntegerField(),
                    )
                ),
            )
            .select_related("airport")
            .get(pk=self.request.user.pk)
        )
        return context


# ------------------------------------------------------------


@require_GET
@admin_required
def search(request):
    """Search the database by term."""

    term = ""
    organizations = None
    memberships = None
    events = None
    persons = None
    airports = None
    training_requests = None
    comments = None

    if request.method == "GET" and "term" in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            term = form.cleaned_data.get("term", "").strip()
            tokens = re.split(r"\s+", term)
            results_combined = []

            organizations = list(
                Organization.objects.filter(
                    Q(domain__icontains=term) | Q(fullname__icontains=term)
                ).order_by("fullname")
            )
            results_combined += organizations

            memberships = list(
                Membership.objects.filter(
                    Q(name__icontains=term) | Q(registration_code__icontains=term)
                ).order_by("-agreement_start")
            )
            results_combined += memberships

            events = list(
                Event.objects.filter(
                    Q(slug__icontains=term)
                    | Q(host__domain__icontains=term)
                    | Q(host__fullname__icontains=term)
                    | Q(url__icontains=term)
                    | Q(contact__icontains=term)
                    | Q(venue__icontains=term)
                    | Q(address__icontains=term)
                ).order_by("-slug")
            )
            results_combined += events

            # if user searches for two words, assume they mean a person
            # name
            if len(tokens) == 2:
                name1, name2 = tokens
                complex_q = (
                    (Q(personal__icontains=name1) & Q(family__icontains=name2))
                    | (Q(personal__icontains=name2) & Q(family__icontains=name1))
                    | Q(email__icontains=term)
                    | Q(secondary_email__icontains=term)
                    | Q(github__icontains=term)
                )
                persons = list(Person.objects.filter(complex_q))
            else:
                persons = list(
                    Person.objects.filter(
                        Q(personal__icontains=term)
                        | Q(family__icontains=term)
                        | Q(email__icontains=term)
                        | Q(secondary_email__icontains=term)
                        | Q(github__icontains=term)
                    ).order_by("family")
                )

            results_combined += persons

            airports = list(
                Airport.objects.filter(
                    Q(iata__icontains=term) | Q(fullname__icontains=term)
                ).order_by("iata")
            )
            results_combined += airports

            training_requests = list(
                TrainingRequest.objects.filter(
                    Q(group_name__icontains=term)
                    | Q(family__icontains=term)
                    | Q(email__icontains=term)
                    | Q(github__icontains=term)
                    | Q(affiliation__icontains=term)
                    | Q(location__icontains=term)
                    | Q(user_notes__icontains=term)
                )
            )
            results_combined += training_requests

            comments = list(
                Comment.objects.filter(
                    Q(comment__icontains=term)
                    | Q(user_name__icontains=term)
                    | Q(user_email__icontains=term)
                    | Q(user__personal__icontains=term)
                    | Q(user__family__icontains=term)
                    | Q(user__email__icontains=term)
                    | Q(user__github__icontains=term)
                ).prefetch_related("content_object")
            )
            results_combined += comments

            # only 1 record found? Let's move to it immediately
            if len(results_combined) == 1 and not form.cleaned_data["no_redirect"]:
                result = results_combined[0]
                msg = format_html(
                    "You were moved to this page, because your search <i>{}</i> "
                    "yields only this result.",
                    term,
                )
                if isinstance(result, Comment):
                    messages.success(request, msg)
                    return redirect(
                        result.content_object.get_absolute_url()
                        + "#c{}".format(result.id)
                    )
                elif hasattr(result, "get_absolute_url"):
                    messages.success(request, msg)
                    return redirect(result.get_absolute_url())

        else:
            messages.error(request, "Fix errors below.")

    # if empty GET, we'll create a blank form
    else:
        form = SearchForm()

    context = {
        "title": "Search",
        "form": form,
        "term": term,
        "organisations": organizations,
        "memberships": memberships,
        "events": events,
        "persons": persons,
        "airports": airports,
        "comments": comments,
        "training_requests": training_requests,
    }
    return render(request, "dashboard/search.html", context)
