from django.contrib.auth.models import Group
from django.urls import reverse

from workshops.tests import TestBase
from workshops.models import (
    Event,
    Organization,
    Tag,
    Person,
)


class TestAdminDashboard(TestBase):
    """Tests for the admin dashboard."""

    def setUp(self):
        self._setUpEvents()
        self._setUpUsersAndLogin()

    def test_has_upcoming_events(self):
        """Test that the admin dashboard is passed some
        upcoming_events in the context."""

        response = self.client.get(reverse('admin-dashboard'))

        # This will fail if the context variable doesn't exist
        events = response.context['current_events']

        # They should all be labeled 'upcoming'.
        assert all([('upcoming' in e.slug or 'ongoing' in e.slug)
                    for e in events])

    def test_no_inactive_events(self):
        """Make sure we don't display stalled or completed events on the
        dashboard."""
        stalled_tag = Tag.objects.get(name='stalled')
        unresponsive_tag = Tag.objects.get(name='unresponsive')
        cancelled_tag = Tag.objects.get(name='unresponsive')

        stalled = Event.objects.create(
            slug='stalled-event', host=Organization.objects.first(),
        )
        stalled.tags.add(stalled_tag)

        unresponsive = Event.objects.create(
            slug='unresponsive-event', host=Organization.objects.first(),
        )
        unresponsive.tags.add(unresponsive_tag)

        cancelled = Event.objects.create(
            slug='cancelled-event', host=Organization.objects.first(),
        )
        cancelled.tags.add(cancelled_tag)

        completed = Event.objects.create(slug='completed-event',
                                         completed=True,
                                         host=Organization.objects.first())

        # stalled event appears in unfiltered list of events
        self.assertNotIn(stalled, Event.objects.unpublished_events())
        self.assertNotIn(unresponsive, Event.objects.unpublished_events())
        self.assertNotIn(cancelled, Event.objects.unpublished_events())
        self.assertNotIn(completed, Event.objects.unpublished_events())

        response = self.client.get(reverse('admin-dashboard'))
        self.assertNotIn(stalled, response.context['unpublished_events'])
        self.assertNotIn(unresponsive, response.context['unpublished_events'])
        self.assertNotIn(cancelled, response.context['unpublished_events'])
        self.assertNotIn(completed, response.context['unpublished_events'])


class TestDispatch(TestBase):
    """Test that the right dashboard (trainee or admin dashboard) is displayed
    after logging in."""

    def test_superuser_logs_in(self):
        person = Person.objects.create_superuser(
            username='admin', personal='', family='',
            email='admin@example.org', password='pass')
        person.data_privacy_agreement = True
        person.save()

        rv = self.client.post(reverse('login'),
                              {'username':'admin', 'password':'pass'},
                              follow=True)

        self.assertEqual(rv.resolver_match.view_name, 'admin-dashboard')

    def test_mentor_logs_in(self):
        mentor = Person.objects.create_user(
            username='user', personal='', family='',
            email='mentor@example.org', password='pass')
        admins = Group.objects.get(name='administrators')
        mentor.groups.add(admins)
        mentor.data_privacy_agreement = True
        mentor.save()

        rv = self.client.post(reverse('login'),
                              {'username': 'user', 'password': 'pass'},
                              follow=True)

        self.assertEqual(rv.resolver_match.view_name, 'admin-dashboard')

    def test_steering_committee_member_logs_in(self):
        mentor = Person.objects.create_user(
            username='user', personal='', family='',
            email='user@example.org', password='pass')
        steering_committee= Group.objects.get(name='steering committee')
        mentor.groups.add(steering_committee)
        mentor.data_privacy_agreement = True
        mentor.save()

        rv = self.client.post(reverse('login'),
                              {'username': 'user', 'password': 'pass'},
                              follow=True)

        self.assertEqual(rv.resolver_match.view_name, 'admin-dashboard')

    def test_trainee_logs_in(self):
        self.trainee = Person.objects.create_user(
            username='trainee', personal='', family='',
            email='trainee@example.org', password='pass')
        self.trainee.data_privacy_agreement = True
        self.trainee.save()

        rv = self.client.post(reverse('login'),
                              {'username': 'trainee', 'password': 'pass'},
                              follow=True)

        self.assertEqual(rv.resolver_match.view_name, 'trainee-dashboard')
