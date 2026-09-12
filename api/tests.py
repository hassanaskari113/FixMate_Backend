from datetime import timedelta
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import (
    Booking,
    BookingStatus,
    Offer,
    OfferStatus,
    ProviderProfile,
    RequestStatus,
    Review,
    RoleStatus,
    Service,
    ServiceArea,
    ServiceCategory,
    ServiceRequest,
    User,
    VerificationStatus,
)


def future(days=1):
    return timezone.now() + timedelta(days=days)


def past(days=1):
    return timezone.now() - timedelta(days=days)


class BaseSetupMixin:
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff",
            email="staff@x.com",
            password="pass12345",
            firebase_uid="uid-staff",
            is_staff=True,
            phone_number="03000000001",
        )

        self.customer = User.objects.create_user(
            username="customer",
            email="customer@x.com",
            password="pass12345",
            firebase_uid="uid-customer",
            role=RoleStatus.CUSTOMER,
            phone_number="03000000002",
        )

        self.other_customer = User.objects.create_user(
            username="customer2",
            email="customer2@x.com",
            password="pass12345",
            firebase_uid="uid-customer2",
            role=RoleStatus.CUSTOMER,
            phone_number="03000000003",
        )

        self.provider_user = User.objects.create_user(
            username="provider",
            email="provider@x.com",
            password="pass12345",
            firebase_uid="uid-provider",
            role=RoleStatus.PROVIDER,
            phone_number="03000000004",
        )

        self.category = ServiceCategory.objects.create(name="Plumbing")
        self.other_category = ServiceCategory.objects.create(name="Electrical")

        self.service = Service.objects.create(
            name="Pipe Repair",
            category=self.category,
        )

        self.area = ServiceArea.objects.create(name="Lahore")

        self.provider_profile = ProviderProfile.objects.create(
            user=self.provider_user,
            bio="Experienced plumber",
            experience=5,
            verification_status=VerificationStatus.APPROVED,
        )

        self.provider_profile.services.add(self.service)
        self.provider_profile.service_areas.add(self.area)

    def make_service_request(
        self,
        customer=None,
        status_=RequestStatus.OPEN,
        location="Lahore, Gulberg",
        category=None,
    ):
        return ServiceRequest.objects.create(
            customer=customer or self.customer,
            description="Leaking pipe under sink",
            min_budget=100,
            max_budget=500,
            urgency=future(),
            category=category or self.category,
            status=status_,
            location=location,
        )

    def make_offer(
        self,
        service_request=None,
        provider=None,
        status_=OfferStatus.PENDING,
        price=200,
    ):
        return Offer.objects.create(
            service_request=service_request or self.make_service_request(),
            service_provider=provider or self.provider_profile,
            price=price,
            arrival_time=future(),
            status=status_,
        )

    def make_booking(
        self,
        offer=None,
        status_=BookingStatus.CONFIRMED,
    ):
        offer = offer or self.make_offer(status_=OfferStatus.ACCEPTED)

        return Booking.objects.create(
            offer=offer,
            scheduled_time=offer.arrival_time,
            final_price=offer.price,
            status=status_,
        )

    def get_results(self, response):
        if "results" in response.data:
            return response.data["results"]
        return response.data


# ============================================================
# MODEL CONSTRAINTS
# ============================================================


class ModelConstraintTests(BaseSetupMixin, APITestCase):
    def test_offer_price_must_be_positive(self):
        service_request = self.make_service_request()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Offer.objects.create(
                    service_request=service_request,
                    service_provider=self.provider_profile,
                    price=0,
                    arrival_time=future(),
                )

    def test_booking_final_price_must_be_positive(self):
        offer = self.make_offer(status_=OfferStatus.ACCEPTED)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Booking.objects.create(
                    offer=offer,
                    scheduled_time=future(),
                    final_price=0,
                )

    def test_review_rating_must_be_between_1_and_5(self):
        booking = self.make_booking(status_=BookingStatus.COMPLETED)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Review.objects.create(
                    booking=booking,
                    text="Bad",
                    rating=6,
                )

    def test_only_one_offer_per_provider_per_request(self):
        service_request = self.make_service_request()

        self.make_offer(service_request=service_request)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Offer.objects.create(
                    service_request=service_request,
                    service_provider=self.provider_profile,
                    price=300,
                    arrival_time=future(),
                )

    def test_phone_number_is_unique_when_provided(self):
        User.objects.create_user(
            username="phone1",
            email="phone1@x.com",
            firebase_uid="phone-uid-1",
            phone_number="03001234567",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    username="phone2",
                    email="phone2@x.com",
                    firebase_uid="phone-uid-2",
                    phone_number="03001234567",
                )

    def test_multiple_users_can_have_no_phone_number(self):
        user1 = User.objects.create_user(
            username="nophone1",
            email="nophone1@x.com",
            firebase_uid="uid-np1",
        )

        user2 = User.objects.create_user(
            username="nophone2",
            email="nophone2@x.com",
            firebase_uid="uid-np2",
        )

        self.assertIsNone(user1.phone_number)
        self.assertIsNone(user2.phone_number)


# ============================================================
# GOOGLE AUTH
# ============================================================


class GoogleAuthViewTests(BaseSetupMixin, APITestCase):
    url = "/api/auth/google/"

    def test_missing_id_token_returns_400(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    @patch("api.views.verify_token")
    def test_invalid_token_returns_401(self, mock_verify):
        mock_verify.side_effect = ValueError("Invalid token")

        response = self.client.post(
            self.url,
            {"id_token": "bad"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    @patch("api.views.verify_token")
    def test_new_user_is_created(self, mock_verify):
        mock_verify.return_value = {
            "uid": "new-uid",
            "email": "brandnew@x.com",
            "name": "Ali Khan",
        }

        response = self.client.post(
            self.url,
            {"id_token": "token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_created"])

        user = User.objects.get(firebase_uid="new-uid")

        self.assertEqual(user.first_name, "Ali")
        self.assertEqual(user.last_name, "Khan")
        self.assertIsNone(user.phone_number)

        self.assertIn("access_token", response.data)
        self.assertIn("refresh_token", response.data)

    @patch("api.views.verify_token")
    def test_existing_firebase_user_logs_in(self, mock_verify):
        mock_verify.return_value = {
            "uid": "uid-customer",
            "email": "customer@x.com",
            "name": "Customer",
        }

        response = self.client.post(
            self.url,
            {"id_token": "token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_created"])

        self.assertEqual(
            User.objects.filter(firebase_uid="uid-customer").count(),
            1,
        )

    @patch("api.views.verify_token")
    def test_existing_user_name_is_updated(self, mock_verify):
        mock_verify.return_value = {
            "uid": "uid-customer",
            "email": "customer@x.com",
            "name": "New Customer",
        }

        response = self.client.post(
            self.url,
            {"id_token": "token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.customer.refresh_from_db()

        self.assertEqual(self.customer.first_name, "New")
        self.assertEqual(self.customer.last_name, "Customer")

    @patch("api.views.verify_token")
    def test_duplicate_email_with_different_uid_is_rejected(self, mock_verify):
        mock_verify.return_value = {
            "uid": "different-uid",
            "email": "customer@x.com",
            "name": "Someone",
        }

        response = self.client.post(
            self.url,
            {"id_token": "token"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    @patch("api.views.verify_token")
    def test_deactivated_user_cannot_login(self, mock_verify):
        self.customer.is_active = False
        self.customer.save()

        mock_verify.return_value = {
            "uid": "uid-customer",
            "email": "customer@x.com",
            "name": "Customer",
        }

        response = self.client.post(
            self.url,
            {"id_token": "token"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )


# ============================================================
# USERS
# ============================================================


class UserViewSetTests(BaseSetupMixin, APITestCase):
    def test_anonymous_cannot_list_users(self):
        response = self.client.get("/api/users/")

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_non_staff_cannot_list_users(self):
        self.client.force_authenticate(self.customer)

        response = self.client.get("/api/users/")

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_staff_can_list_users(self):
        self.client.force_authenticate(self.staff)

        response = self.client.get("/api/users/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_owner_can_retrieve_profile(self):
        self.client.force_authenticate(self.customer)

        response = self.client.get(f"/api/users/{self.customer.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_other_user_cannot_retrieve_profile(self):
        self.client.force_authenticate(self.other_customer)

        response = self.client.get(f"/api/users/{self.customer.id}/")

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_user_creation_endpoint_is_disabled(self):
        response = self.client.post(
            "/api/users/",
            {"username": "newuser"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_destroy_deactivates_user(self):
        self.client.force_authenticate(self.customer)

        response = self.client.delete(f"/api/users/{self.customer.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.customer.refresh_from_db()

        self.assertFalse(self.customer.is_active)
        self.assertTrue(User.objects.filter(id=self.customer.id).exists())

    def test_destroy_already_deactivated_user_returns_400(self):
        self.customer.is_active = False
        self.customer.save()

        self.client.force_authenticate(self.customer)

        response = self.client.delete(f"/api/users/{self.customer.id}/")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    @patch("api.views.verify_token")
    def test_reactivate_deactivated_user(self, mock_verify):
        self.customer.is_active = False
        self.customer.save()

        mock_verify.return_value = {"uid": "uid-customer"}

        response = self.client.post(
            "/api/users/reactivate/",
            {"id_token": "token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.customer.refresh_from_db()

        self.assertTrue(self.customer.is_active)

    @patch("api.views.verify_token")
    def test_reactivate_active_user_returns_400(self, mock_verify):
        mock_verify.return_value = {"uid": "uid-customer"}

        response = self.client.post(
            "/api/users/reactivate/",
            {"id_token": "token"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )


# ============================================================
# CATALOG
# ============================================================


class CatalogViewSetTests(BaseSetupMixin, APITestCase):
    def test_authenticated_user_can_list_categories(self):
        self.client.force_authenticate(self.customer)

        response = self.client.get("/api/service_categories/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_anonymous_user_cannot_list_categories(self):
        response = self.client.get("/api/service_categories/")

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_non_staff_cannot_create_category(self):
        self.client.force_authenticate(self.customer)

        response = self.client.post(
            "/api/service_categories/",
            {"name": "Carpentry"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_staff_can_create_category(self):
        self.client.force_authenticate(self.staff)

        response = self.client.post(
            "/api/service_categories/",
            {"name": "Carpentry"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_staff_can_create_service(self):
        self.client.force_authenticate(self.staff)

        response = self.client.post(
            "/api/services/",
            {
                "name": "Drain Cleaning",
                "category_id": self.category.id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            Service.objects.filter(
                name="Drain Cleaning",
                category=self.category,
            ).exists()
        )

    def test_staff_can_create_service_area(self):
        self.client.force_authenticate(self.staff)

        response = self.client.post(
            "/api/service_areas/",
            {"name": "Model Town"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

    def test_category_search_works(self):
        self.client.force_authenticate(self.customer)

        response = self.client.get("/api/service_categories/?search=Plumb")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = self.get_results(response)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Plumbing")

    def test_category_ordering_works(self):
        ServiceCategory.objects.create(name="AAA")

        self.client.force_authenticate(self.customer)

        response = self.client.get("/api/service_categories/?ordering=name")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = self.get_results(response)

        self.assertEqual(results[0]["name"], "AAA")


# ============================================================
# PROVIDER PROFILE
# ============================================================


class ProviderProfileViewSetTests(BaseSetupMixin, APITestCase):
    def test_customer_can_create_provider_profile(self):
        self.client.force_authenticate(self.customer)

        response = self.client.post(
            "/api/provider_profiles/",
            {
                "bio": "Handy person",
                "experience": 2,
                "services_ids": [self.service.id],
                "service_areas_ids": [self.area.id],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.customer.refresh_from_db()

        self.assertEqual(
            self.customer.role,
            RoleStatus.PROVIDER,
        )

        self.assertTrue(ProviderProfile.objects.filter(user=self.customer).exists())

    def test_approved_provider_cannot_create_second_profile(self):
        self.client.force_authenticate(self.provider_user)

        response = self.client.post(
            "/api/provider_profiles/",
            {
                "bio": "Second profile",
                "experience": 1,
                "services_ids": [self.service.id],
                "service_areas_ids": [self.area.id],
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_staff_can_approve_provider(self):
        self.provider_profile.verification_status = VerificationStatus.PENDING
        self.provider_profile.save()

        self.client.force_authenticate(self.staff)

        response = self.client.post(
            f"/api/provider_profiles/{self.provider_profile.id}/app_ver_status/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.provider_profile.refresh_from_db()

        self.assertEqual(
            self.provider_profile.verification_status,
            VerificationStatus.APPROVED,
        )

    def test_non_staff_cannot_approve_provider(self):
        self.client.force_authenticate(self.customer)

        response = self.client.post(
            f"/api/provider_profiles/{self.provider_profile.id}/app_ver_status/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_staff_can_reject_provider(self):
        self.client.force_authenticate(self.staff)

        response = self.client.post(
            f"/api/provider_profiles/{self.provider_profile.id}/rej_ver_status/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.provider_profile.refresh_from_db()

        self.assertEqual(
            self.provider_profile.verification_status,
            VerificationStatus.REJECTED,
        )

    def test_provider_profile_contains_statistics(self):
        booking = self.make_booking(status_=BookingStatus.COMPLETED)

        Review.objects.create(
            booking=booking,
            text="Great service",
            rating=5,
        )

        self.client.force_authenticate(self.provider_user)

        response = self.client.get(
            f"/api/provider_profiles/{self.provider_profile.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertIn("completed_jobs", response.data)
        self.assertIn("avg_rating", response.data)

        self.assertEqual(response.data["completed_jobs"], 1)
        self.assertEqual(float(response.data["avg_rating"]), 5.0)


# ============================================================
# SERVICE REQUESTS
# ============================================================


class ServiceRequestViewSetTests(BaseSetupMixin, APITestCase):
    def valid_payload(self, **overrides):
        payload = {
            "description": "Broken heater",
            "min_budget": "100.00",
            "max_budget": "500.00",
            "urgency": future().isoformat(),
            "category_id": self.category.id,
            "location": "Lahore, DHA",
        }

        payload.update(overrides)

        return payload

    def test_customer_can_create_request(self):
        self.client.force_authenticate(self.customer)

        response = self.client.post(
            "/api/service_requests/",
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        request = ServiceRequest.objects.get()

        self.assertEqual(
            request.customer,
            self.customer,
        )

        self.assertEqual(
            request.category,
            self.category,
        )

    def test_provider_cannot_create_request(self):
        self.client.force_authenticate(self.provider_user)

        response = self.client.post(
            "/api/service_requests/",
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_min_budget_must_be_less_than_max_budget(self):
        self.client.force_authenticate(self.customer)

        response = self.client.post(
            "/api/service_requests/",
            self.valid_payload(
                min_budget="500.00",
                max_budget="500.00",
            ),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_negative_budget_is_rejected(self):
        self.client.force_authenticate(self.customer)

        response = self.client.post(
            "/api/service_requests/",
            self.valid_payload(min_budget="0.00"),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_past_urgency_is_rejected(self):
        self.client.force_authenticate(self.customer)

        response = self.client.post(
            "/api/service_requests/",
            self.valid_payload(urgency=past().isoformat()),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_deactivated_customer_cannot_create_request(self):
        self.customer.is_active = False
        self.customer.save()

        self.client.force_authenticate(self.customer)

        response = self.client.post(
            "/api/service_requests/",
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_customer_sees_only_own_requests(self):
        own = self.make_service_request(customer=self.customer)

        self.make_service_request(customer=self.other_customer)

        self.client.force_authenticate(self.customer)

        response = self.client.get("/api/service_requests/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = self.get_results(response)

        ids = [item["id"] for item in results]

        self.assertEqual(ids, [own.id])

    def test_provider_sees_only_eligible_open_requests(self):
        matching = self.make_service_request(location="Lahore, Gulberg")

        self.make_service_request(location="Karachi, Clifton")

        self.make_service_request(
            category=self.other_category,
            location="Lahore, Gulberg",
        )

        self.client.force_authenticate(self.provider_user)

        response = self.client.get("/api/service_requests/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = self.get_results(response)

        ids = [item["id"] for item in results]

        self.assertIn(matching.id, ids)
        self.assertEqual(len(ids), 1)

    def test_owner_can_close_open_request(self):
        service_request = self.make_service_request()

        offer = self.make_offer(service_request=service_request)

        self.client.force_authenticate(self.customer)

        response = self.client.post(
            f"/api/service_requests/{service_request.id}/close_request/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        service_request.refresh_from_db()
        offer.refresh_from_db()

        self.assertEqual(
            service_request.status,
            RequestStatus.CLOSED,
        )

        self.assertEqual(
            offer.status,
            OfferStatus.REJECTED,
        )

    def test_cannot_close_closed_request(self):
        service_request = self.make_service_request(status_=RequestStatus.CLOSED)

        self.client.force_authenticate(self.customer)

        response = self.client.post(
            f"/api/service_requests/{service_request.id}/close_request/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_staff_can_expire_request(self):
        service_request = self.make_service_request()

        offer = self.make_offer(service_request=service_request)

        self.client.force_authenticate(self.staff)

        response = self.client.post(
            f"/api/service_requests/{service_request.id}/expire_request/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        service_request.refresh_from_db()
        offer.refresh_from_db()

        self.assertEqual(
            service_request.status,
            RequestStatus.EXPIRED,
        )

        self.assertEqual(
            offer.status,
            OfferStatus.EXPIRED,
        )

    def test_customer_cannot_expire_request(self):
        service_request = self.make_service_request()

        self.client.force_authenticate(self.customer)

        response = self.client.post(
            f"/api/service_requests/{service_request.id}/expire_request/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_can_update_open_request(self):
        service_request = self.make_service_request()

        self.client.force_authenticate(self.customer)

        response = self.client.patch(
            f"/api/service_requests/{service_request.id}/",
            {"description": "Updated description"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        service_request.refresh_from_db()

        self.assertEqual(
            service_request.description,
            "Updated description",
        )

    def test_cannot_update_closed_request(self):
        service_request = self.make_service_request(status_=RequestStatus.CLOSED)

        self.client.force_authenticate(self.customer)

        response = self.client.patch(
            f"/api/service_requests/{service_request.id}/",
            {"description": "Updated"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_reopen_requires_closed_request(self):
        service_request = self.make_service_request()

        self.client.force_authenticate(self.customer)

        response = self.client.post(
            f"/api/service_requests/{service_request.id}/reopen_request/",
            {"new_urgency_time": future().isoformat()},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_reopen_after_cancelled_booking(self):
        service_request = self.make_service_request(status_=RequestStatus.CLOSED)

        offer = self.make_offer(
            service_request=service_request,
            status_=OfferStatus.ACCEPTED,
        )

        self.make_booking(
            offer=offer,
            status_=BookingStatus.CANCELLED,
        )

        self.client.force_authenticate(self.customer)

        response = self.client.post(
            f"/api/service_requests/{service_request.id}/reopen_request/",
            {"new_urgency_time": future(2).isoformat()},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        service_request.refresh_from_db()

        self.assertEqual(
            service_request.status,
            RequestStatus.OPEN,
        )


# ============================================================
# OFFERS
# ============================================================


class OfferViewSetTests(BaseSetupMixin, APITestCase):
    def valid_payload(self, service_request):
        return {
            "service_request_id": service_request.id,
            "price": "250.00",
            "arrival_time": future().isoformat(),
        }

    def test_approved_provider_can_create_offer(self):
        service_request = self.make_service_request()

        self.client.force_authenticate(self.provider_user)

        response = self.client.post(
            "/api/offers/",
            self.valid_payload(service_request),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        offer = Offer.objects.get()

        self.assertEqual(
            offer.service_request,
            service_request,
        )

        self.assertEqual(
            offer.service_provider,
            self.provider_profile,
        )

    def test_unverified_provider_cannot_create_offer(self):
        self.provider_profile.verification_status = VerificationStatus.PENDING
        self.provider_profile.save()

        service_request = self.make_service_request()

        self.client.force_authenticate(self.provider_user)

        response = self.client.post(
            "/api/offers/",
            self.valid_payload(service_request),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_customer_cannot_create_offer(self):
        service_request = self.make_service_request(customer=self.other_customer)

        self.client.force_authenticate(self.customer)

        response = self.client.post(
            "/api/offers/",
            self.valid_payload(service_request),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_offer_wrong_category_is_rejected(self):
        service_request = self.make_service_request(category=self.other_category)

        self.client.force_authenticate(self.provider_user)

        response = self.client.post(
            "/api/offers/",
            self.valid_payload(service_request),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_offer_outside_service_area_is_rejected(self):
        service_request = self.make_service_request(location="Karachi, Clifton")

        self.client.force_authenticate(self.provider_user)

        response = self.client.post(
            "/api/offers/",
            self.valid_payload(service_request),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_provider_cannot_offer_on_own_request(self):
        service_request = ServiceRequest.objects.create(
            customer=self.provider_user,
            description="Self request",
            min_budget=100,
            max_budget=500,
            urgency=future(),
            category=self.category,
            location="Lahore, Gulberg",
        )

        self.client.force_authenticate(self.provider_user)

        response = self.client.post(
            "/api/offers/",
            self.valid_payload(service_request),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_offer_on_closed_request_is_rejected(self):
        service_request = self.make_service_request(status_=RequestStatus.CLOSED)

        self.client.force_authenticate(self.provider_user)

        response = self.client.post(
            "/api/offers/",
            self.valid_payload(service_request),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_invalid_offer_price_is_rejected(self):
        service_request = self.make_service_request()

        self.client.force_authenticate(self.provider_user)

        response = self.client.post(
            "/api/offers/",
            {
                **self.valid_payload(service_request),
                "price": "0.00",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_customer_accepting_offer_creates_booking(self):
        service_request = self.make_service_request()

        offer1 = self.make_offer(service_request=service_request)

        second_provider_user = User.objects.create_user(
            username="provider2",
            email="provider2@x.com",
            password="pass12345",
            firebase_uid="uid-provider2",
            role=RoleStatus.PROVIDER,
        )

        provider2 = ProviderProfile.objects.create(
            user=second_provider_user,
            experience=1,
            verification_status=VerificationStatus.APPROVED,
        )

        provider2.services.add(self.service)
        provider2.service_areas.add(self.area)

        offer2 = self.make_offer(
            service_request=service_request,
            provider=provider2,
        )

        self.client.force_authenticate(self.customer)

        response = self.client.post(f"/api/offers/{offer1.id}/accept_offer/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        offer1.refresh_from_db()
        offer2.refresh_from_db()
        service_request.refresh_from_db()

        self.assertEqual(
            offer1.status,
            OfferStatus.ACCEPTED,
        )

        self.assertEqual(
            offer2.status,
            OfferStatus.REJECTED,
        )

        self.assertEqual(
            service_request.status,
            RequestStatus.CLOSED,
        )

        booking = Booking.objects.get(offer=offer1)

        self.assertEqual(
            booking.final_price,
            offer1.price,
        )

        self.assertEqual(
            booking.scheduled_time,
            offer1.arrival_time,
        )

    def test_provider_cannot_accept_offer(self):
        service_request = self.make_service_request()

        offer = self.make_offer(service_request=service_request)

        self.client.force_authenticate(self.provider_user)

        response = self.client.post(f"/api/offers/{offer.id}/accept_offer/")

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_customer_can_reject_offer(self):
        service_request = self.make_service_request()

        offer = self.make_offer(service_request=service_request)

        self.client.force_authenticate(self.customer)

        response = self.client.post(f"/api/offers/{offer.id}/reject_offer/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        offer.refresh_from_db()

        self.assertEqual(
            offer.status,
            OfferStatus.REJECTED,
        )

    def test_already_accepted_offer_cannot_be_accepted_again(self):
        service_request = self.make_service_request(status_=RequestStatus.CLOSED)

        offer = self.make_offer(
            service_request=service_request,
            status_=OfferStatus.ACCEPTED,
        )

        self.client.force_authenticate(self.customer)

        response = self.client.post(f"/api/offers/{offer.id}/accept_offer/")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )


# ============================================================
# BOOKINGS
# ============================================================


class BookingViewSetTests(BaseSetupMixin, APITestCase):
    def test_customer_cannot_create_booking_directly(self):
        offer = self.make_offer(status_=OfferStatus.ACCEPTED)

        self.client.force_authenticate(self.customer)

        response = self.client.post(
            "/api/bookings/",
            {"offer_id": offer.id},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_staff_can_create_booking_directly(self):
        offer = self.make_offer(status_=OfferStatus.ACCEPTED)

        self.client.force_authenticate(self.staff)

        response = self.client.post(
            "/api/bookings/",
            {"offer_id": offer.id},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(Booking.objects.filter(offer=offer).exists())

    def test_staff_cannot_create_booking_from_pending_offer(self):
        offer = self.make_offer(status_=OfferStatus.PENDING)

        self.client.force_authenticate(self.staff)

        response = self.client.post(
            "/api/bookings/",
            {"offer_id": offer.id},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_customer_can_cancel_booking(self):
        booking = self.make_booking()

        self.client.force_authenticate(self.customer)

        response = self.client.post(
            f"/api/bookings/{booking.id}/cancel_booking/",
            {"cancellation_reason": "Change of plans"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        booking.refresh_from_db()

        self.assertEqual(
            booking.status,
            BookingStatus.CANCELLED,
        )

        self.assertEqual(
            booking.cancellation_reason,
            "Change of plans",
        )

    def test_provider_can_cancel_booking(self):
        booking = self.make_booking()

        self.client.force_authenticate(self.provider_user)

        response = self.client.post(
            f"/api/bookings/{booking.id}/cancel_booking/",
            {"cancellation_reason": "Unavailable"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_booking_cannot_be_cancelled_without_reason(self):
        booking = self.make_booking()

        self.client.force_authenticate(self.customer)

        response = self.client.post(
            f"/api/bookings/{booking.id}/cancel_booking/",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_blank_cancellation_reason_is_rejected(self):
        booking = self.make_booking()

        self.client.force_authenticate(self.customer)

        response = self.client.post(
            f"/api/bookings/{booking.id}/cancel_booking/",
            {"cancellation_reason": "   "},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_completed_booking_cannot_be_cancelled(self):
        booking = self.make_booking(status_=BookingStatus.COMPLETED)

        self.client.force_authenticate(self.customer)

        response = self.client.post(
            f"/api/bookings/{booking.id}/cancel_booking/",
            {"cancellation_reason": "Too late"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_customer_can_complete_booking(self):
        booking = self.make_booking()

        self.client.force_authenticate(self.customer)

        response = self.client.post(f"/api/bookings/{booking.id}/complete_booking/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        booking.refresh_from_db()

        self.assertEqual(
            booking.status,
            BookingStatus.COMPLETED,
        )

    def test_provider_cannot_complete_booking(self):
        booking = self.make_booking()

        self.client.force_authenticate(self.provider_user)

        response = self.client.post(f"/api/bookings/{booking.id}/complete_booking/")

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_cancelled_booking_cannot_be_completed(self):
        booking = self.make_booking(status_=BookingStatus.CANCELLED)

        self.client.force_authenticate(self.customer)

        response = self.client.post(f"/api/bookings/{booking.id}/complete_booking/")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_customer_sees_only_own_bookings(self):
        own_booking = self.make_booking()

        other_request = self.make_service_request(customer=self.other_customer)

        other_offer = self.make_offer(
            service_request=other_request,
            status_=OfferStatus.ACCEPTED,
        )

        self.make_booking(offer=other_offer)

        self.client.force_authenticate(self.customer)

        response = self.client.get("/api/bookings/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        results = self.get_results(response)

        ids = [item["id"] for item in results]

        self.assertIn(own_booking.id, ids)
        self.assertEqual(len(ids), 1)


# ============================================================
# REVIEWS
# ============================================================


class ReviewViewSetTests(BaseSetupMixin, APITestCase):
    def test_customer_can_review_completed_booking(self):
        booking = self.make_booking(status_=BookingStatus.COMPLETED)

        self.client.force_authenticate(self.customer)

        response = self.client.post(
            "/api/reviews/",
            {
                "booking_id": booking.id,
                "text": "Great service!",
                "rating": 5,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        review = Review.objects.get(booking=booking)

        self.assertEqual(review.rating, 5)
        self.assertEqual(review.text, "Great service!")

    def test_customer_cannot_review_incomplete_booking(self):
        booking = self.make_booking(status_=BookingStatus.CONFIRMED)

        self.client.force_authenticate(self.customer)

        response = self.client.post(
            "/api/reviews/",
            {
                "booking_id": booking.id,
                "text": "Too early",
                "rating": 5,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_customer_cannot_review_someone_elses_booking(self):
        booking = self.make_booking(status_=BookingStatus.COMPLETED)

        self.client.force_authenticate(self.other_customer)

        response = self.client.post(
            "/api/reviews/",
            {
                "booking_id": booking.id,
                "text": "Not mine",
                "rating": 5,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_nonexistent_booking_returns_400(self):
        self.client.force_authenticate(self.customer)

        response = self.client.post(
            "/api/reviews/",
            {
                "booking_id": 999999,
                "text": "Ghost booking",
                "rating": 5,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_rating_out_of_range_is_rejected(self):
        booking = self.make_booking(status_=BookingStatus.COMPLETED)

        self.client.force_authenticate(self.customer)

        response = self.client.post(
            "/api/reviews/",
            {
                "booking_id": booking.id,
                "text": "Invalid",
                "rating": 6,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_duplicate_review_is_rejected(self):
        booking = self.make_booking(status_=BookingStatus.COMPLETED)

        Review.objects.create(
            booking=booking,
            text="First review",
            rating=4,
        )

        self.client.force_authenticate(self.customer)

        response = self.client.post(
            "/api/reviews/",
            {
                "booking_id": booking.id,
                "text": "Second review",
                "rating": 5,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_owner_can_update_review_text(self):
        booking = self.make_booking(status_=BookingStatus.COMPLETED)

        review = Review.objects.create(
            booking=booking,
            text="Good",
            rating=3,
        )

        self.client.force_authenticate(self.customer)

        response = self.client.patch(
            f"/api/reviews/{review.id}/",
            {"text": "Actually great"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        review.refresh_from_db()

        self.assertEqual(
            review.text,
            "Actually great",
        )

    def test_non_owner_cannot_update_review(self):
        booking = self.make_booking(status_=BookingStatus.COMPLETED)

        review = Review.objects.create(
            booking=booking,
            text="Good",
            rating=3,
        )

        self.client.force_authenticate(self.other_customer)

        response = self.client.patch(
            f"/api/reviews/{review.id}/",
            {"text": "Hijacked"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_booking_cannot_be_changed_on_review_update(self):
        booking = self.make_booking(status_=BookingStatus.COMPLETED)

        other_booking = self.make_booking(status_=BookingStatus.COMPLETED)

        review = Review.objects.create(
            booking=booking,
            text="Good",
            rating=3,
        )

        self.client.force_authenticate(self.customer)

        response = self.client.patch(
            f"/api/reviews/{review.id}/",
            {"booking_id": other_booking.id},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_provider_sees_only_their_reviews(self):
        booking = self.make_booking(status_=BookingStatus.COMPLETED)

        Review.objects.create(
            booking=booking,
            text="Great",
            rating=5,
        )

        self.client.force_authenticate(self.provider_user)

        response = self.client.get("/api/reviews/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        results = self.get_results(response)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["rating"], 5)

    def test_provider_filter_works(self):
        booking = self.make_booking(status_=BookingStatus.COMPLETED)

        Review.objects.create(
            booking=booking,
            text="Great",
            rating=5,
        )

        self.client.force_authenticate(self.customer)

        response = self.client.get(
            f"/api/reviews/?provider_id={self.provider_profile.id}"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        results = self.get_results(response)

        self.assertEqual(len(results), 1)
