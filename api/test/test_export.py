import datetime
import json
import unittest
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status

from api.test.base import APITestBase
from api.views import (
    ExportBadgesView,
    ExportBadgesByPersonView,
    ExportInstructorLocationsView,
    ExportMembersView,
)
from workshops.models import (
    Badge,
    Award,
    Person,
    Airport,
    Role,
)
from workshops.util import universal_date_format


class BaseExportingTest(APITestBase):
    def setUp(self):
        # remove all existing badges (this will be rolled back anyway)
        # including swc-instructor and dc-instructor introduced by migration
        # 0064
        Badge.objects.all().delete()

    def login(self):
        self.admin = Person.objects.create_superuser(
                username="admin", personal="Super", family="User",
                email="sudo@example.org", password='admin')
        self.client.login(username='admin', password='admin')


class TestExportingBadges(BaseExportingTest):
    def setUp(self):
        super().setUp()

        today = datetime.date.today()

        # set up two badges, one with users, one without any
        self.badge1 = Badge.objects.create(name='badge1', title='Badge1',
                                           criteria='')
        self.badge2 = Badge.objects.create(name='badge2', title='Badge2',
                                           criteria='')
        self.user1 = Person.objects.create_user(
            username='user1', email='user1@name.org',
            personal='User1', family='Name')
        self.user2 = Person.objects.create_user(
            username='user2', email='user2@name.org',
            personal='User2', family='Name')
        Award.objects.create(person=self.user1, badge=self.badge1,
                             awarded=today)
        Award.objects.create(person=self.user2, badge=self.badge1,
                             awarded=today)

        # make sure we *do* get empty badges
        self.expecting = [
            {
                'name': 'badge1',
                'persons': [
                    {'name': 'User1 Name', 'user': 'user1',
                     'awarded': '{:%Y-%m-%d}'.format(today)},
                    {'name': 'User2 Name', 'user': 'user2',
                     'awarded': '{:%Y-%m-%d}'.format(today)},
                ],
            },
            {
                'name': 'badge2',
                'persons': [],
            },
        ]

    def test_serialization(self):
        view = ExportBadgesView()
        serializer = view.get_serializer_class()
        response = serializer(view.get_queryset(), many=True)
        self.assertEqual(response.data, self.expecting)

    def test_view(self):
        # test only JSON output
        url = reverse('api:export-badges')
        response = self.client.get(url, format='json')
        content = response.content.decode('utf-8')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(content), self.expecting)


class TestExportingBadgesByPerson(BaseExportingTest):
    def setUp(self):
        super().setUp()

        # set up two users one with badges, one without any
        self.user1 = Person.objects.create_user(
            username='user1', email='user1@name.org',
            personal='User1', family='Name')
        self.user2 = Person.objects.create_user(
            username='user2', email='user2@name.org',
            personal='User2', family='Name')
        self.badge1 = Badge.objects.create(name='badge1', title='Badge1',
                                           criteria='')
        self.badge2 = Badge.objects.create(name='badge2', title='Badge2',
                                           criteria='')
        Award.objects.create(person=self.user1, badge=self.badge1)
        Award.objects.create(person=self.user1, badge=self.badge2)

        # make sure we *do* get users without badges
        self.expecting = [
            {
                'username': 'user1',
                'email': 'user1@name.org',
                'personal': 'User1',
                'middle': '',
                'family': 'Name',
                'badges': [
                    {
                        'name': 'badge1',
                        'title': 'Badge1',
                        'criteria': '',
                    },
                    {
                        'name': 'badge2',
                        'title': 'Badge2',
                        'criteria': '',
                    },
                ],
            },
        ]

    def test_serialization(self):
        view = ExportBadgesByPersonView()
        serializer = view.get_serializer_class()
        response = serializer(view.get_queryset(), many=True)
        self.assertEqual(response.data, self.expecting)

    def test_view(self):
        # test only JSON output
        url = reverse('api:export-badges-by-person')
        response = self.client.get(url, format='json')
        content = response.content.decode('utf-8')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(content), self.expecting)


class TestExportingInstructors(BaseExportingTest):
    def setUp(self):
        super().setUp()

        # set up two badges, one for each user
        self.swc_instructor = Badge.objects.create(
            name='swc-instructor', title='Software Carpentry Instructor',
            criteria='')
        self.dc_instructor = Badge.objects.create(
            name='dc-instructor', title='Data Carpentry Instructor',
            criteria='')
        self.airport1 = Airport.objects.create(
            iata='ABC', fullname='Airport1', country='PL', latitude=1,
            longitude=2,
        )
        self.airport2 = Airport.objects.create(
            iata='ABD', fullname='Airport2', country='US', latitude=2,
            longitude=1,
        )
        self.user1 = Person.objects.create(
            username='user1', personal='User1', family='Name',
            email='user1@name.org', airport=self.airport1,
            publish_profile=True,
        )
        self.user2 = Person.objects.create(
            username='user2', personal='User2', family='Name',
            email='user2@name.org', airport=self.airport1,
            publish_profile=True,
        )
        # user1 is only a SWC instructor
        Award.objects.create(person=self.user1, badge=self.swc_instructor)
        # user2 is only a DC instructor
        Award.objects.create(person=self.user2, badge=self.dc_instructor)

        # make sure we *do not* get empty airports
        self.expecting = [
            {
                'name': 'Airport1',
                'country': 'PL',
                'latitude': 1.0,
                'longitude': 2.0,
                'instructors': [
                    {'name': 'User1 Name', 'user': 'user1'},
                    {'name': 'User2 Name', 'user': 'user2'},
                ]
            },
        ]

    def test_serialization(self):
        view = ExportInstructorLocationsView()
        serializer = view.get_serializer_class()
        response = serializer(view.get_queryset(), many=True)
        self.assertEqual(response.data, self.expecting)

    def test_view(self):
        # test only JSON output
        url = reverse('api:export-instructors')
        response = self.client.get(url, format='json')
        content = response.content.decode('utf-8')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(content), self.expecting)


class TestExportingInstructorsRegression(BaseExportingTest):
    """This unit test helps to ensure that no non-instructors nor people who
    agreed to publish their profiles are exposed via API."""

    def setUp(self):
        super().setUp()

        # an airport for testing purposes, it will have some instructors and
        # users associated
        self.airport1 = Airport.objects.create(
            iata='ABC', fullname='Airport1', country='PL', latitude=1,
            longitude=2,
        )
        # a different airport, this time with instructors who have not agreed
        # to publish their profile
        self.airport2 = Airport.objects.create(
            iata='ABD', fullname='Airport2', country='US', latitude=2,
            longitude=1,
        )

        # set up two badges
        self.swc_instructor = Badge.objects.create(
            name='swc-instructor', title='Software Carpentry Instructor',
            criteria='')
        self.dc_instructor = Badge.objects.create(
            name='dc-instructor', title='Data Carpentry Instructor',
            criteria='')

        # set up 3 instructors with this specific airport, but only 2 have
        # allowed to publish their profiles
        self.instructor1 = Person.objects.create(
            username='instructor1', personal='Instructor1', family='Name',
            email='instructor1@name.org', airport=self.airport1,
            publish_profile=True,
        )
        self.instructor2 = Person.objects.create(
            username='instructor2', personal='Instructor2', family='Name',
            email='instructor2@name.org', airport=self.airport1,
            publish_profile=True,
        )
        self.instructor3 = Person.objects.create(
            username='instructor3', personal='Instructor3', family='Name',
            email='instructor3@name.org', airport=self.airport1,
            publish_profile=False,
        )
        self.instructor4 = Person.objects.create(
            username='instructor4', personal='Instructor4', family='Name',
            email='instructor4@name.org', airport=self.airport2,
            publish_profile=False,
        )

        # set up 3 "normal" users with the first airport, but only 2 have
        # allowed to publish their profiles
        self.user1 = Person.objects.create(
            username='user1', personal='User1', family='Name',
            email='user1@name.org', airport=self.airport1,
            publish_profile=True,
        )
        self.user2 = Person.objects.create(
            username='user2', personal='User2', family='Name',
            email='user2@name.org', airport=self.airport1,
            publish_profile=True,
        )
        self.user3 = Person.objects.create(
            username='user3', personal='User3', family='Name',
            email='user3@name.org', airport=self.airport1,
            publish_profile=False,
        )

        # awards some badges for the instructors
        Award.objects.create(person=self.instructor1,
                             badge=self.swc_instructor)
        Award.objects.create(person=self.instructor2,
                             badge=self.dc_instructor)

        # make sure we don't get:
        # * non-instructor users
        # * instructors who did not allow for their profiles to be published
        self.expecting = [
            {
                'name': 'Airport1',
                'country': 'PL',
                'latitude': 1.0,
                'longitude': 2.0,
                'instructors': [
                    {'name': 'Instructor1 Name', 'user': 'instructor1'},
                    {'name': 'Instructor2 Name', 'user': 'instructor2'},
                ]
            },
        ]

    def test_serialization(self):
        view = ExportInstructorLocationsView()
        serializer = view.get_serializer_class()
        response = serializer(view.get_queryset(), many=True)
        self.assertEqual(response.data, self.expecting)

    def test_view(self):
        # test only JSON output
        url = reverse('api:export-instructors')
        response = self.client.get(url, format='json')
        content = response.content.decode('utf-8')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(content), self.expecting)


class TestExportingInstructorsEmptyAirportRegression(BaseExportingTest):
    """This unit test aims to ensure that empty airport regression is
    always remembered."""

    def setUp(self):
        super().setUp()

        # an airport with instructors who have not agreed to publish their
        # profiles
        self.airport1 = Airport.objects.create(
            iata='ABC', fullname='Airport1', country='PL', latitude=1,
            longitude=2,
        )

        # set up two badges
        self.swc_instructor = Badge.objects.create(
            name='swc-instructor', title='Software Carpentry Instructor',
            criteria='')
        self.dc_instructor = Badge.objects.create(
            name='dc-instructor', title='Data Carpentry Instructor',
            criteria='')

        # set up 2 instructors with this specific airport, none of them agreed
        # to publish their profile
        self.instructor1 = Person.objects.create(
            username='instructor1', personal='Instructor1', family='Name',
            email='instructor1@name.org', airport=self.airport1,
            publish_profile=False,
        )
        self.instructor2 = Person.objects.create(
            username='instructor2', personal='Instructor2', family='Name',
            email='instructor2@name.org', airport=self.airport1,
            publish_profile=False,
        )
        # additional user, who is not an instructor, but associated with
        # the airport *and* allowing to publish their profile
        self.user1 = Person.objects.create(
            username='user1', personal='User1', family='Name',
            email='user1@name.org', airport=self.airport1,
            publish_profile=True,
        )

        # awards some badges for the instructors
        Award.objects.create(person=self.instructor1,
                             badge=self.swc_instructor)
        Award.objects.create(person=self.instructor2,
                             badge=self.dc_instructor)

        # we should not get empty airports, but we do and cannot do anything
        # about it, because we're already doing some pretty advanced querying
        # in `ExportInstructorLocationsView.queryset` thanks to Django's
        # Prefetch() object
        self.expecting = []

    @unittest.expectedFailure
    def test_serialization(self):
        view = ExportInstructorLocationsView()
        serializer = view.get_serializer_class()
        response = serializer(view.get_queryset(), many=True)
        self.assertEqual(response.data, self.expecting)

    @unittest.expectedFailure
    def test_view(self):
        # test only JSON output
        url = reverse('api:export-instructors')
        response = self.client.get(url, format='json')
        content = response.content.decode('utf-8')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(content), self.expecting)


class TestExportingMembers(BaseExportingTest):
    def setUp(self):
        super().setUp()

        # Note: must create instructor badges for get_members query to run.
        # Same for instructor role
        Badge.objects.create(
            name='swc-instructor', title='Software Carpentry Instructor',
            criteria='')
        Badge.objects.create(
            name='dc-instructor', title='Data Carpentry Instructor',
            criteria='')
        Role.objects.create(name='instructor')

        self.spiderman = Person.objects.create(
            personal='Peter', middle='Q.', family='Parker',
            email='peter@webslinger.net',
            username="spiderman")

        self.member = Badge.objects.create(name='member',
                                           title='Member',
                                           criteria='')

        Award.objects.create(person=self.spiderman,
                             badge=self.member,
                             awarded=datetime.date(2014, 1, 1))

        self.expecting = [
            {
                'name': 'Peter Q. Parker',
                'email': 'peter@webslinger.net',
                'username': 'spiderman',
            },
        ]

    @patch.object(ExportMembersView, 'request', query_params={}, create=True)
    def test_serialization(self, mock_request):
        # we're mocking a request here because it's not possible to create
        # a fake request context for the view
        view = ExportMembersView()
        serializer = view.get_serializer_class()
        response = serializer(view.get_queryset(), many=True)
        self.assertEqual(response.data, self.expecting)

    def test_requires_login(self):
        url = reverse('api:export-members')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.login()
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_view_default_cutoffs(self):
        # test only JSON output
        url = reverse('api:export-members')
        self.login()
        response = self.client.get(url, format='json')
        content = response.content.decode('utf-8')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(content), self.expecting)

    def test_view_explicit_earliest(self):
        url = reverse('api:export-members')
        data = {'earliest': universal_date_format(datetime.date.today())}

        self.login()
        response = self.client.get(url, data, format='json')
        content = response.content.decode('utf-8')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(content), self.expecting)
