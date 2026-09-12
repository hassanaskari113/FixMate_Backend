from django.contrib.auth.models import AbstractUser
from django.db import models


# User
class RoleStatus(models.TextChoices):
    CUSTOMER = "C", "Customer"
    PROVIDER = "P", "Provider"


class User(AbstractUser):
    profile_picture = models.ImageField(upload_to="users/", blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    phone_number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    role = models.CharField(
        max_length=1, choices=RoleStatus.choices, default=RoleStatus.CUSTOMER
    )
    firebase_uid = models.TextField(
        unique=True,
    )

    class Meta:
        ordering = ("id",)


# Service Category
class ServiceCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)


# Service
class Service(models.Model):
    name = models.CharField(max_length=50, unique=True)
    category = models.ForeignKey(
        ServiceCategory, on_delete=models.CASCADE, related_name="services"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)


# Service Area
class ServiceArea(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)


# Provider Profile
class VerificationStatus(models.TextChoices):
    PENDING = "P", "Pending"
    APPROVED = "A", "Approved"
    REJECTED = "R", "Rejected"


class ProviderProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="provider_profile"
    )
    bio = models.TextField(blank=True)
    experience = models.PositiveIntegerField()
    verification_status = models.CharField(
        max_length=1,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    services = models.ManyToManyField(
        Service,
        related_name="providers",
    )
    service_areas = models.ManyToManyField(ServiceArea, related_name="providers")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)


# Service Request
class RequestStatus(models.TextChoices):
    OPEN = "O", "Open"
    CLOSED = "C", "Closed"
    EXPIRED = "E", "Expired"


class ServiceRequest(models.Model):
    customer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="service_requests"
    )
    description = models.TextField()
    min_budget = models.DecimalField(max_digits=7, decimal_places=2)
    max_budget = models.DecimalField(max_digits=7, decimal_places=2)
    urgency = models.DateTimeField()
    category = models.ForeignKey(
        ServiceCategory, on_delete=models.CASCADE, related_name="service_requests"
    )
    status = models.CharField(
        max_length=1, choices=RequestStatus.choices, default=RequestStatus.OPEN
    )
    created_at = models.DateTimeField(auto_now_add=True)
    location = models.TextField()

    class Meta:
        ordering = ("id",)


class RequestImage(models.Model):
    image = models.ImageField(upload_to="request_images/")
    request = models.ForeignKey(
        ServiceRequest, on_delete=models.CASCADE, related_name="request_images"
    )
    created_at = models.DateTimeField(auto_now_add=True)


# Offer
class OfferStatus(models.TextChoices):
    PENDING = "P", "Pending"
    ACCEPTED = "A", "Accepted"
    REJECTED = "R", "Rejected"
    EXPIRED = "E", "Expired"


class Offer(models.Model):
    service_request = models.ForeignKey(
        ServiceRequest, on_delete=models.CASCADE, related_name="offers"
    )
    service_provider = models.ForeignKey(
        ProviderProfile,
        on_delete=models.CASCADE,
        related_name="offers",
    )
    price = models.DecimalField(max_digits=7, decimal_places=2)
    arrival_time = models.DateTimeField()
    status = models.CharField(
        max_length=1, choices=OfferStatus.choices, default=OfferStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=models.Q(price__gt=0), name="positive_price"
            ),
            models.UniqueConstraint(
                fields=("service_request", "service_provider"),
                name="one_offer_per_request",
            ),
        )

        ordering = ("id",)


# Booking
class BookingStatus(models.TextChoices):
    CONFIRMED = "CONF", "Confirmed"
    COMPLETED = "COMP", "Completed"
    CANCELLED = "CANC", "Cancelled"


class Booking(models.Model):
    offer = models.OneToOneField(
        Offer, on_delete=models.CASCADE, related_name="booking"
    )
    scheduled_time = models.DateTimeField()
    final_price = models.DecimalField(max_digits=7, decimal_places=2)
    status = models.CharField(
        max_length=4, choices=BookingStatus.choices, default=BookingStatus.CONFIRMED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    cancellation_reason = models.TextField(blank=True)

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=models.Q(final_price__gt=0), name="positive_final_price"
            ),
        )

        ordering = ("id",)


# Review
class Review(models.Model):
    booking = models.OneToOneField(
        Booking, on_delete=models.CASCADE, related_name="review"
    )
    text = models.TextField()
    rating = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=models.Q(rating__gte=1) & models.Q(rating__lte=5),
                name="rating_between_1_and_5",
            ),
        )

        ordering = ("id",)


class ReviewImage(models.Model):
    image = models.ImageField(upload_to="review_images/")
    review = models.ForeignKey(
        Review, on_delete=models.CASCADE, related_name="review_images"
    )
    created_at = models.DateTimeField(auto_now_add=True)
