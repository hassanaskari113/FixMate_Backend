import django_filters
from django.db import transaction
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import (
    BasePermission,
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from core.firebase import verify_token
from core.models import *

from .serializers import *


class Pagination(PageNumberPagination):
    page_size = 20


# Google Auth View
class GoogleAuthView(APIView):
    def post(self, request):
        id_token = request.data.get("id_token", None)
        if id_token is None:
            return Response(
                {"detail": "Id token is not provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            id_info = verify_token(id_token=id_token)
        except ValueError:
            return Response(
                {"detail": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED
            )

        name = id_info.get("name", "")
        email = id_info.get("email", None)
        uid = id_info.get("uid", None)

        if email is None or uid is None:
            return Response(
                {"detail": "No email or uid"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        first_name = ""
        last_name = ""

        if name:
            name_parts = name.split()
            first_name = name_parts[0]
            last_name = " ".join(name_parts[1:])

        created = False
        if User.objects.filter(firebase_uid=uid).exists():
            user = User.objects.get(
                firebase_uid=uid,
            )
        elif User.objects.filter(email=email).exists():
            return Response(
                {"detail": "The email already exists!"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        else:
            user = User.objects.create(
                firebase_uid=uid,
                email=email,
                first_name=first_name,
                last_name=last_name,
                username=email,
            )
            created = True

        if not created:
            updated = False
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                updated = True
            if updated:
                user.save()

        if not user.is_active:
            return Response(
                {"detail": "The account is deactivated"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh = RefreshToken.for_user(user=user)

        return Response(
            {
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_created": created,
            }
        )


# User
class IsStaff(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_staff


class IsUserOwnerOrStaff(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj == request.user or request.user.is_staff


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = ()
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    filterset_fields = ("role",)
    search_fields = ("username", "email", "phone_number", "first_name", "last_name")
    ordering_fields = ("joined_at", "first_name", "username")
    pagination_class = Pagination

    def get_permissions(self):
        if self.action == "list":
            return [
                IsAuthenticated(),
                IsStaff(),
            ]
        elif self.action in ("retrieve", "update", "partial_update", "destroy"):
            return [IsUserOwnerOrStaff(), IsAuthenticated()]
        else:
            return []

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "User creation is not allowed through this endpoint"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if not user.is_active:
            return Response(
                {"detail": "The account is deactivated"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = False
        user.save()
        return Response(
            {"detail": "User account deactivated"},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])
    def reactivate(self, request):
        id_token = request.data.get("id_token", None)
        if id_token is None:
            return Response(
                {"detail": "id_token not provided for reactivation"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            id_info = verify_token(id_token=id_token)
        except ValueError:
            return Response(
                {"detail": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED
            )

        uid = id_info.get("uid")
        try:
            user = User.objects.get(firebase_uid=uid)
            if user.is_active == False:
                user.is_active = True
                user.save()
                return Response(
                    {"detail": "User account reactivated"},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"detail": "The user is already active"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except User.DoesNotExist:
            return Response(
                {"detail": "User does not exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )


# Service Category
class ServiceCategoryViewSet(viewsets.ModelViewSet):
    queryset = ServiceCategory.objects.all()
    serializer_class = ServiceCategorySerializer
    permission_classes = ()
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    filterset_fields = ("name",)
    search_fields = ("name",)
    ordering_fields = ("name", "created_at")
    pagination_class = Pagination

    def get_permissions(self):
        if self.action == "list" or self.action == "retrieve":
            return [IsAuthenticated()]
        else:
            return [IsAuthenticated(), IsStaff()]


# Service
class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = ()
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    filterset_fields = ("name", "category")
    search_fields = ("name", "category__name")
    ordering_fields = ("name", "created_at", "category")
    pagination_class = Pagination

    def get_permissions(self):
        if self.action == "list" or self.action == "retrieve":
            return [IsAuthenticated()]
        else:
            return [IsAuthenticated(), IsStaff()]


# Service Area
class ServiceAreaViewSet(viewsets.ModelViewSet):
    queryset = ServiceArea.objects.all()
    serializer_class = ServiceAreaSerializer
    permission_classes = ()
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    filterset_fields = ("name",)
    search_fields = ("name",)
    ordering_fields = ("name", "created_at")
    pagination_class = Pagination

    def get_permissions(self):
        if self.action == "list" or self.action == "retrieve":
            return [IsAuthenticated()]
        else:
            return [IsAuthenticated(), IsStaff()]


# Provider Profile
class IsProfileOwnerOrStaff(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user or request.user.is_staff


class IsNotProvider(BasePermission):
    def has_permission(self, request, view):
        if request.user.role != RoleStatus.PROVIDER:
            return True

        return (
            hasattr(request.user, "provider_profile")
            and request.user.provider_profile.verification_status
            == VerificationStatus.REJECTED
        )


class ProviderProfileViewSet(viewsets.ModelViewSet):
    queryset = ProviderProfile.objects.select_related("user").prefetch_related(
        "services", "service_areas"
    )
    serializer_class = ProviderProfileSerializer
    permission_classes = ()
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    filterset_fields = (
        "user__username",
        "experience",
        "verification_status",
        "service_areas__name",
        "services__category__name",
    )
    search_fields = (
        "user__username",
        "bio",
        "services__name",
        "service_areas__name",
        "services__category__name",
    )
    ordering_fields = (
        "user__username",
        "experience",
        "services__category__name",
        "service_areas__name",
        "created_at",
    )
    pagination_class = Pagination

    def get_permissions(self):
        if self.action == "list" or self.action == "retrieve":
            return [IsAuthenticated()]
        elif self.action == "create":
            return [IsAuthenticated(), IsNotProvider()]
        elif (
            self.action == "approve_verification_status"
            or self.action == "reject_verification_status"
            or self.action == "destroy"
        ):
            return [IsAuthenticated(), IsStaff()]

        else:
            return [IsProfileOwnerOrStaff(), IsAuthenticated()]

    @action(detail=True, methods=["post"], url_path="app_ver_status")
    def approve_verification_status(self, request, pk=None):
        profile = self.get_object()
        profile.verification_status = VerificationStatus.APPROVED
        profile.save()
        return Response(
            {"detail": "Profile verification approved"}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"], url_path="rej_ver_status")
    def reject_verification_status(self, request, pk=None):
        profile = self.get_object()
        profile.verification_status = VerificationStatus.REJECTED
        profile.save()
        return Response(
            {"detail": "Profile verification rejected"}, status=status.HTTP_200_OK
        )


# Service Request
class IsCustomerOrStaff(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == RoleStatus.CUSTOMER or request.user.is_staff


class IsServiceRequestOwnerOrStaff(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.customer == request.user or request.user.is_staff


class IsEligibleProviderOrStaff(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True

        if request.user.role != RoleStatus.PROVIDER or not hasattr(
            request.user, "provider_profile"
        ):
            return False

        profile = request.user.provider_profile

        return any(
            obj.category == service.category for service in profile.services.all()
        ) and any(
            service_area.name in obj.location
            for service_area in profile.service_areas.all()
        )


class ServiceRequestViewSet(viewsets.ModelViewSet):
    queryset = ServiceRequest.objects.select_related(
        "customer", "category"
    ).prefetch_related("request_images")
    serializer_class = ServiceRequestSerializer
    permission_classes = ()
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    filterset_fields = (
        "customer__username",
        "min_budget",
        "max_budget",
        "urgency",
        "category__name",
        "status",
    )
    search_fields = (
        "customer__username",
        "description",
        "category__name",
        "location",
    )
    ordering_fields = (
        "customer__username",
        "min_budget",
        "max_budget",
        "urgency",
        "category__name",
        "created_at",
    )
    pagination_class = Pagination

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        if (
            self.action == "list"
            and self.request.user.is_authenticated
            and self.request.user.role == RoleStatus.CUSTOMER
        ):
            return self.queryset.filter(customer=self.request.user)
        elif (
            self.action == "list"
            and self.request.user.is_authenticated
            and self.request.user.role == RoleStatus.PROVIDER
        ):
            areas = self.request.user.provider_profile.service_areas.all()
            if not areas.exists():
                return self.queryset.none()
            area_query = Q()
            for area in areas:
                area_query |= Q(location__icontains=area.name)
            return self.queryset.filter(
                Q(
                    category__in=(
                        service.category
                        for service in self.request.user.provider_profile.services.all()
                    )
                )
                & Q(status=RequestStatus.OPEN)
                & area_query
            )
        else:
            return self.queryset

    def get_permissions(self):
        if self.action == "list":
            return [IsAuthenticated()]
        elif (
            self.action == "retrieve"
            and self.request.user.is_authenticated
            and self.request.user.role == RoleStatus.CUSTOMER
        ):
            return [IsAuthenticated(), IsServiceRequestOwnerOrStaff()]
        elif (
            self.action == "retrieve"
            and self.request.user.is_authenticated
            and self.request.user.role == RoleStatus.PROVIDER
        ):
            return [IsAuthenticated(), IsEligibleProviderOrStaff()]
        elif self.action == "create":
            return [IsAuthenticated(), IsCustomerOrStaff()]
        elif self.action in (
            "update",
            "partial_update",
            "destroy",
            "close_request",
            "reopen_request",
        ):
            return [IsServiceRequestOwnerOrStaff()]
        elif self.action == "expire_request":
            return [IsAuthenticated(), IsStaff()]
        else:
            return [IsAuthenticated(), IsStaff()]

    @action(detail=True, methods=["post"])
    def close_request(self, request, pk=None):
        with transaction.atomic():
            service_request = ServiceRequest.objects.select_for_update().get(
                pk=self.get_object().pk
            )

            if service_request.status != RequestStatus.OPEN:
                return Response(
                    {"detail": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST
                )

            service_request.status = RequestStatus.CLOSED
            service_request.save(update_fields=["status"])

            service_request.offers.filter(status=OfferStatus.PENDING).update(
                status=OfferStatus.REJECTED
            )

        return Response({"detail": "Request closed"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def expire_request(self, request, pk=None):
        with transaction.atomic():
            service_request = ServiceRequest.objects.select_for_update().get(
                pk=self.get_object().pk
            )

            if service_request.status != RequestStatus.OPEN:
                return Response(
                    {"detail": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST
                )

            service_request.status = RequestStatus.EXPIRED
            service_request.save(update_fields=["status"])

            service_request.offers.filter(status=OfferStatus.PENDING).update(
                status=OfferStatus.EXPIRED
            )

        return Response({"detail": "Request expired"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def reopen_request(self, request, pk=None):
        service_request = self.get_object()
        if service_request.status != RequestStatus.CLOSED:
            return Response(
                {"detail": "Invalid action. Only closed requests can be reopened"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        eligible = False
        for offer in service_request.offers.all():
            if (
                offer.status == OfferStatus.ACCEPTED
                and offer.booking.status == BookingStatus.CANCELLED
            ):
                eligible = True
        if eligible:
            ser = ReOpenServiceRequestSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            new_time = ser.validated_data["new_urgency_time"]

            if new_time >= timezone.now():
                service_request.urgency = new_time
                service_request.status = RequestStatus.OPEN
                service_request.save()
                return Response(
                    {"detail": "Service request opened"},
                    status=status.HTTP_200_OK,
                )
            return Response(
                {
                    "detail": "Invalid action. Valid time and date required for reopening"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {"detail": "Invalid action. Can not open service request"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def update(self, request, *args, **kwargs):
        service_request = self.get_object()
        if service_request.status == RequestStatus.OPEN:
            return super().update(request, *args, **kwargs)
        else:
            return Response(
                {"detail": "Invalid action! Cannot edit closed/expired request"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def partial_update(self, request, *args, **kwargs):
        service_request = self.get_object()
        if service_request.status == RequestStatus.OPEN:
            return super().partial_update(request, *args, **kwargs)
        else:
            return Response(
                {"detail": "Invalid action! Cannot edit closed/expired request"},
                status=status.HTTP_400_BAD_REQUEST,
            )


# Offer
class IsVerifiedProvider(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.role == RoleStatus.PROVIDER
            and hasattr(request.user, "provider_profile")
            and request.user.provider_profile.verification_status
            == VerificationStatus.APPROVED
        )


class IsOfferOwnerOrStaff(BasePermission):
    def has_object_permission(self, request, view, obj):
        return (
            obj.service_provider == request.user.provider_profile
            or request.user.is_staff
        )


class IsOfferOnUserRequestOrStaff(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.service_request.customer == request.user or request.user.is_staff


class IsOfferCustomerOrStaff(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.service_request.customer == request.user or request.user.is_staff


class OfferViewSet(viewsets.ModelViewSet):
    queryset = Offer.objects.select_related(
        "service_request",
        "service_provider",
        "service_request__customer",
        "service_request__category",
        "service_provider__user",
    ).prefetch_related(
        "service_provider__services",
        "service_provider__service_areas",
    )
    serializer_class = OfferSerializer
    permission_classes = ()
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    filterset_fields = (
        "service_request__customer__username",
        "service_request__category__name",
        "service_provider__user__username",
        "price",
        "arrival_time",
        "status",
    )
    search_fields = (
        "service_request__customer__username",
        "service_request__category__name",
        "service_provider__user__username",
        "service_request__description",
        "service_request__location",
    )
    ordering_fields = (
        "service_request__customer__username",
        "price",
        "arrival_time",
        "service_request__category__name",
        "created_at",
    )
    pagination_class = Pagination

    def get_permissions(self):
        if self.action == "list":
            return [IsAuthenticated()]
        elif (
            self.action == "retrieve"
            and self.request.user.is_authenticated
            and self.request.user.role == RoleStatus.PROVIDER
        ):
            return [IsAuthenticated(), IsOfferOwnerOrStaff()]
        elif (
            self.action == "retrieve"
            and self.request.user.is_authenticated
            and self.request.user.role == RoleStatus.CUSTOMER
        ):
            return [IsAuthenticated(), IsOfferOnUserRequestOrStaff()]
        elif self.action == "create":
            return [IsAuthenticated(), IsVerifiedProvider()]
        elif self.action in ("update", "partial_update"):
            return [IsAuthenticated(), IsStaff()]
        elif self.action == "accept_offer" or self.action == "reject_offer":
            return [IsAuthenticated(), IsOfferCustomerOrStaff()]
        else:
            return [IsAuthenticated(), IsStaff()]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        if (
            self.action == "list"
            and self.request.user.is_authenticated
            and self.request.user.role == RoleStatus.PROVIDER
        ):
            return self.queryset.filter(
                service_provider=self.request.user.provider_profile
            )
        elif (
            self.action == "list"
            and self.request.user.is_authenticated
            and self.request.user.role == RoleStatus.CUSTOMER
        ):
            return self.queryset.filter(service_request__customer=self.request.user)
        else:
            return self.queryset

    @action(detail=True, methods=["post"])
    def accept_offer(self, request, pk=None):
        with transaction.atomic():
            offer = self.get_object()

            service_request = ServiceRequest.objects.select_for_update().get(
                pk=offer.service_request.id
            )

            if (
                offer.status != OfferStatus.PENDING
                or service_request.status != RequestStatus.OPEN
            ):
                return Response(
                    {"detail": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST
                )

            offer.status = OfferStatus.ACCEPTED
            offer.save(update_fields=["status"])

            service_request.offers.filter(status=OfferStatus.PENDING).update(
                status=OfferStatus.REJECTED
            )

            Booking.objects.create(
                offer=offer, scheduled_time=offer.arrival_time, final_price=offer.price
            )

            service_request.status = RequestStatus.CLOSED
            service_request.save(update_fields=["status"])

        return Response({"detail": "Offer accepted"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def reject_offer(self, request, pk=None):
        offer = self.get_object()
        if (
            offer.status == OfferStatus.PENDING
            and offer.service_request.status == RequestStatus.OPEN
        ):
            offer.status = OfferStatus.REJECTED
            offer.save()
            return Response({"detail": "Offer rejected"}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"detail": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST
            )


# Booking
class IsBookingProviderOrStaff(BasePermission):
    def has_object_permission(self, request, view, obj):
        return (
            request.user.is_staff
            or obj.offer.service_provider == request.user.provider_profile
        )


class IsBookingCustomerOrStaff(BasePermission):
    def has_object_permission(self, request, view, obj):
        return (
            obj.offer.service_request.customer == request.user or request.user.is_staff
        )


class IsBookingCustomerOrProviderOrStaff(BasePermission):
    def has_object_permission(self, request, view, obj):
        return (
            request.user.is_staff
            or obj.offer.service_request.customer == request.user
            or obj.offer.service_provider == request.user.provider_profile
        )


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.select_related(
        "offer",
        "offer__service_request",
        "offer__service_request__customer",
        "offer__service_request__category",
        "offer__service_provider",
        "offer__service_provider__user",
    )
    serializer_class = BookingSerializer
    permission_classes = ()
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    filterset_fields = (
        "offer__service_request__customer__username",
        "offer__service_request__category__name",
        "offer__service_provider__user__username",
        "final_price",
        "status",
        "scheduled_time",
    )
    search_fields = (
        "offer__service_request__customer__username",
        "offer__service_request__category__name",
        "offer__service_provider__user__username",
        "offer__service_request__description",
        "offer__service_request__location",
    )
    ordering_fields = (
        "offer__service_request__customer__username",
        "final_price",
        "scheduled_time",
        "offer__service_request__category__name",
        "created_at",
    )
    pagination_class = Pagination

    def get_permissions(self):
        if self.action == "list":
            return [IsAuthenticated()]
        elif (
            self.action == "retrieve"
            and self.request.user.is_authenticated
            and self.request.user.role == RoleStatus.PROVIDER
        ):
            return [IsAuthenticated(), IsBookingProviderOrStaff()]
        elif (
            self.action == "retrieve"
            and self.request.user.is_authenticated
            and self.request.user.role == RoleStatus.CUSTOMER
        ):
            return [IsAuthenticated(), IsBookingCustomerOrStaff()]
        elif self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsStaff()]
        elif self.action == "cancel_booking":
            return [IsAuthenticated(), IsBookingCustomerOrProviderOrStaff()]
        elif self.action == "complete_booking":
            return [IsAuthenticated(), IsBookingCustomerOrStaff()]
        else:
            return [IsAuthenticated()]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        if (
            self.action == "list"
            and self.request.user.is_authenticated
            and self.request.user.role == RoleStatus.CUSTOMER
        ):
            return self.queryset.filter(
                offer__service_request__customer=self.request.user
            )

        elif (
            self.action == "list"
            and self.request.user.is_authenticated
            and self.request.user.role == RoleStatus.PROVIDER
        ):
            return self.queryset.filter(
                offer__service_provider=self.request.user.provider_profile
            )
        else:
            return self.queryset

    @action(detail=True, methods=["post"])
    def cancel_booking(self, request, pk=None):
        booking = self.get_object()
        if booking.status != BookingStatus.CONFIRMED:
            return Response(
                {
                    "detail": "Invalid action. Booking should be confirmed before cancelling"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        reason = request.data.get("cancellation_reason", None)
        if reason is None or reason.strip() == "":
            return Response(
                {"detail": "Booking can not be cancelled without a reason"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        booking.status = BookingStatus.CANCELLED
        booking.cancellation_reason = reason
        booking.save()
        return Response(
            {"detail": "Booking cancelled"},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def complete_booking(self, request, pk=None):
        booking = self.get_object()
        if booking.status == BookingStatus.CONFIRMED:
            booking.status = BookingStatus.COMPLETED
            booking.save()
            return Response(
                {"detail": "Booking completed"},
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                "detail": "Booking can not be completed if its cancelled or not confirmed"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


# Review
class ReviewFilterSet(django_filters.FilterSet):
    provider_id = django_filters.NumberFilter(
        field_name="booking__offer__service_provider__id",
    )

    class Meta:
        model = Review
        fields = ()


class IsReviewOwnerOrStaff(BasePermission):
    def has_object_permission(self, request, view, obj):
        return (
            obj.booking.offer.service_request.customer == request.user
            or request.user.is_staff
        )


class IsReviewProviderOrStaff(BasePermission):
    def has_object_permission(self, request, view, obj):
        return (
            request.user.is_staff
            or obj.booking.offer.service_provider == request.user.provider_profile
        )


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.select_related(
        "booking",
        "booking__offer",
        "booking__offer__service_request",
        "booking__offer__service_request__customer",
        "booking__offer__service_request__category",
        "booking__offer__service_provider",
        "booking__offer__service_provider__user",
    ).prefetch_related("review_images")
    serializer_class = ReviewSerializer
    permission_classes = ()
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    search_fields = (
        "booking__offer__service_request__customer__username",
        "booking__offer__service_request__category__name",
        "booking__offer__service_provider__user__username",
        "booking__offer__service_request__description",
        "booking__offer__service_request__location",
        "text",
    )
    ordering_fields = (
        "booking__offer__service_request__customer__username",
        "booking__final_price",
        "booking__scheduled_time",
        "booking__offer__service_request__category__name",
        "created_at",
        "rating",
    )
    filterset_class = ReviewFilterSet
    pagination_class = Pagination

    def get_permissions(self):
        if self.action == "list":
            return [IsAuthenticated()]
        elif self.action in ("update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsReviewOwnerOrStaff()]
        elif (
            self.action == "retrieve"
            and self.request.user.is_authenticated
            and self.request.user.role == RoleStatus.PROVIDER
        ):
            return [IsAuthenticated(), IsReviewProviderOrStaff()]
        elif (
            self.action == "retrieve"
            and self.request.user.is_authenticated
            and self.request.user.role == RoleStatus.CUSTOMER
        ):
            return [IsAuthenticated(), IsReviewOwnerOrStaff()]

        else:
            return [IsCustomerOrStaff()]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        if (
            self.action == "list"
            and self.request.user.is_authenticated
            and self.request.user.role == RoleStatus.CUSTOMER
        ):
            return self.queryset.filter(
                booking__offer__service_request__customer=self.request.user
            )

        elif (
            self.action == "list"
            and self.request.user.is_authenticated
            and self.request.user.role == RoleStatus.PROVIDER
        ):
            return self.queryset.filter(
                booking__offer__service_provider=self.request.user.provider_profile
            )

        else:
            return self.queryset

    def create(self, request, *args, **kwargs):
        booking_id = request.data.get("booking_id")

        if Booking.objects.filter(id=booking_id).exists():
            booking = Booking.objects.filter(id=booking_id).first()
            if booking.offer.service_request.customer == request.user:
                if booking.status != BookingStatus.COMPLETED:
                    return Response(
                        {"detail": "Booking must be completed before review"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if hasattr(booking, "review"):
                    return Response(
                        {"detail": "Only one review per booking allowed"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                return super().create(request, *args, **kwargs)
            else:
                return Response(
                    {
                        "detail": "Invalid action. Customer can only review their own bookings"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return Response(
            {"detail": "Booking does not exists"},
            status=status.HTTP_400_BAD_REQUEST,
        )
