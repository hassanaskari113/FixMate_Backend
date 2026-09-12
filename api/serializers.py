from django.db.models.aggregates import Avg
from django.utils import timezone
from rest_framework import serializers

from core.models import (
    Booking,
    BookingStatus,
    Offer,
    OfferStatus,
    ProviderProfile,
    RequestImage,
    RequestStatus,
    Review,
    ReviewImage,
    RoleStatus,
    Service,
    ServiceArea,
    ServiceCategory,
    ServiceRequest,
    User,
    VerificationStatus,
)


# google auth request serializers
class GoogleAuthRequestSerializer(serializers.Serializer):
    id_token = serializers.CharField()


# google auth response serializers
class GoogleAuthResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    is_created = serializers.BooleanField()


# User
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "profile_picture",
            "role",
            "joined_at",
        )
        read_only_fields = ("id", "joined_at", "role")

    def validate_profile_picture(self, value):
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Image size is too large!")
        return value


# Service Category
class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = "__all__"
        read_only_fields = ("id", "created_at")


# Service
class ServiceSerializer(serializers.ModelSerializer):
    category = ServiceCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=ServiceCategory.objects.all()
    )

    class Meta:
        model = Service
        fields = ("id", "name", "category", "category_id", "created_at")
        read_only_fields = ("id", "created_at")

    def create(self, validated_data):
        service_category = validated_data.pop("category_id")
        return Service.objects.create(category=service_category, **validated_data)

    def update(self, instance, validated_data):
        category = validated_data.pop("category_id", None)
        if category is not None:
            instance.category = category
        return super().update(instance, validated_data)


# Service Area
class ServiceAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceArea
        fields = "__all__"
        read_only_fields = ("id", "created_at")


# Provider Profile
class ProviderProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    services = ServiceSerializer(many=True, read_only=True)
    services_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Service.objects.all(), write_only=True, required=False
    )
    service_areas = ServiceAreaSerializer(many=True, read_only=True)
    service_areas_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=ServiceArea.objects.all(), write_only=True, required=False
    )
    completed_jobs = serializers.SerializerMethodField(read_only=True)
    avg_rating = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProviderProfile
        fields = (
            "id",
            "user",
            "bio",
            "experience",
            "verification_status",
            "services",
            "service_areas",
            "created_at",
            "services_ids",
            "service_areas_ids",
            "completed_jobs",
            "avg_rating",
        )
        read_only_fields = ("id", "verification_status", "created_at")

    def create(self, validated_data):
        user = self.context["request"].user

        service_ids = validated_data.pop("services_ids")
        service_areas_ids = validated_data.pop("service_areas_ids")

        profile = ProviderProfile.objects.create(user=user, **validated_data)

        profile.services.set(service_ids)
        profile.service_areas.set(service_areas_ids)

        user.role = RoleStatus.PROVIDER
        user.save(update_fields=["role"])

        return profile

    def update(self, instance, validated_data):
        service_ids = validated_data.pop("services_ids", None)
        if service_ids is not None:
            instance.services.set(service_ids)

        service_areas_ids = validated_data.pop("service_areas_ids", None)
        if service_areas_ids is not None:
            instance.service_areas.set(service_areas_ids)

        return super().update(instance, validated_data)

    def get_completed_jobs(self, obj) -> int:
        return Booking.objects.filter(
            offer__service_provider=obj, status=BookingStatus.COMPLETED
        ).count()

    def get_avg_rating(self, obj) -> float:
        avg_rating = (
            Review.objects.filter(booking__offer__service_provider=obj)
            .aggregate(avg_rating=Avg("rating"))
            .get("avg_rating")
        )
        return avg_rating if avg_rating is not None else 0.0


#  Service Request
class RequestImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestImage
        fields = ("id", "image", "created_at")
        read_only_fields = ("id", "created_at")

    def validate_image(self, value):
        if value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("Image size is too large!")
        return value


class ServiceRequestSerializer(serializers.ModelSerializer):
    customer = UserSerializer(read_only=True)
    category = ServiceCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=ServiceCategory.objects.all()
    )
    request_images = RequestImageSerializer(many=True, required=False)

    class Meta:
        model = ServiceRequest
        fields = (
            "id",
            "customer",
            "description",
            "min_budget",
            "max_budget",
            "urgency",
            "category",
            "category_id",
            "status",
            "location",
            "request_images",
            "created_at",
        )
        read_only_fields = ("id", "status", "created_at")

    def validate(self, attrs):
        min_budget = attrs.get(
            "min_budget", self.instance.min_budget if self.instance else None
        )
        max_budget = attrs.get(
            "max_budget", self.instance.max_budget if self.instance else None
        )

        if (
            min_budget is not None
            and max_budget is not None
            and min_budget >= max_budget
        ):
            raise serializers.ValidationError(
                "Minimum budget should be less than maximum budget"
            )

        if not self.context["request"].user.is_active:
            raise serializers.ValidationError("Deactivated user can not create request")
        urgency = attrs.get("urgency", self.instance.urgency if self.instance else None)
        if urgency is not None and urgency <= timezone.now():
            raise serializers.ValidationError("Urgency time should be valid")

        return attrs

    def validate_min_budget(self, value):
        if value <= 0:
            raise serializers.ValidationError("Minimum budget should be greater than 0")
        return value

    def validate_max_budget(self, value):
        if value <= 0:
            raise serializers.ValidationError("Maximum budget should be greater than 0")
        return value

    def create(self, validated_data):
        request_category = validated_data.pop("category_id")
        request_images = validated_data.pop("request_images", [])
        request = ServiceRequest.objects.create(
            category=request_category,
            customer=self.context["request"].user,
            **validated_data,
        )
        for request_image in request_images:
            RequestImage.objects.create(request=request, **request_image)
        return request

    def update(self, instance, validated_data):
        request_category = validated_data.pop("category_id", None)
        request_images = validated_data.pop("request_images", None)

        if request_images is not None or request_category is not None:
            raise serializers.ValidationError(
                "Can not update request's images or category"
            )
        return super().update(instance, validated_data)


class ReOpenServiceRequestSerializer(serializers.Serializer):
    new_urgency_time = serializers.DateTimeField()


# Offer
class OfferSerializer(serializers.ModelSerializer):
    service_request = ServiceRequestSerializer(read_only=True)
    service_request_id = serializers.PrimaryKeyRelatedField(
        queryset=ServiceRequest.objects.all()
    )
    service_provider = ProviderProfileSerializer(read_only=True)

    class Meta:
        model = Offer
        fields = (
            "id",
            "service_request",
            "service_request_id",
            "service_provider",
            "price",
            "arrival_time",
            "status",
            "created_at",
        )
        read_only_fields = ("id", "status", "created_at")

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price should be greater than 0")
        return value

    def create(self, validated_data):
        provider = self.context["request"].user.provider_profile
        service_request = validated_data.pop("service_request_id")
        if (
            provider.verification_status == VerificationStatus.APPROVED
            and (
                service_request.status == RequestStatus.OPEN
                and provider.user.id != service_request.customer.id
            )
            and any(
                service.category == service_request.category
                for service in provider.services.all()
            )
            and any(
                service_area.name in service_request.location
                for service_area in provider.service_areas.all()
            )
        ):
            return Offer.objects.create(
                service_request=service_request,
                service_provider=provider,
                **validated_data,
            )
        raise serializers.ValidationError("Invalid Offer")

    def update(self, instance, validated_data):
        if validated_data != {}:
            raise serializers.ValidationError("Offer is immutable")
        return instance


# Booking
class BookingSerializer(serializers.ModelSerializer):
    offer = OfferSerializer(read_only=True)
    offer_id = serializers.PrimaryKeyRelatedField(queryset=Offer.objects.all())

    class Meta:
        model = Booking
        fields = (
            "id",
            "offer",
            "offer_id",
            "scheduled_time",
            "final_price",
            "status",
            "created_at",
            "cancellation_reason",
        )
        read_only_fields = (
            "id",
            "status",
            "created_at",
            "final_price",
            "scheduled_time",
            "cancellation_reason",
        )

    def create(self, validated_data):
        offer = validated_data.pop("offer_id")
        if (
            offer.status == OfferStatus.ACCEPTED
            and (
                self.context["request"].user.is_staff
                or offer.service_request.customer == self.context["request"].user
            )
            and not Booking.objects.filter(offer=offer).exists()
        ):
            return Booking.objects.create(
                offer=offer,
                scheduled_time=offer.arrival_time,
                final_price=offer.price,
                **validated_data,
            )
        raise serializers.ValidationError("Invalid Booking")

    def update(self, instance, validated_data):
        if validated_data != {}:
            raise serializers.ValidationError("Booking is immutable")
        return instance


# Review
class ReviewImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewImage
        fields = ("id", "image", "created_at")
        read_only_fields = ("id", "created_at")

    def validate_image(self, value):
        if value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("Image size is too large!")
        return value


class ReviewSerializer(serializers.ModelSerializer):
    booking = BookingSerializer(read_only=True)
    booking_id = serializers.PrimaryKeyRelatedField(queryset=Booking.objects.all())
    review_images = ReviewImageSerializer(many=True, required=False)

    class Meta:
        model = Review
        fields = (
            "id",
            "booking",
            "booking_id",
            "text",
            "rating",
            "review_images",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value

    def create(self, validated_data):
        booking = validated_data.pop("booking_id")
        if (
            booking.status == BookingStatus.COMPLETED
            and self.context["request"].user == booking.offer.service_request.customer
        ):
            review_images = validated_data.pop("review_images", [])
            review = Review.objects.create(booking=booking, **validated_data)

            for review_image in review_images:
                ReviewImage.objects.create(review=review, **review_image)
            return review
        raise serializers.ValidationError("Invalid Review")

    def update(self, instance, validated_data):
        review_images = validated_data.pop("review_images", None)
        booking = validated_data.pop("booking_id", None)
        if booking is not None or review_images is not None:
            raise serializers.ValidationError(
                "Can not update review's booking or images"
            )
        if (
            self.context["request"].user
            != instance.booking.offer.service_request.customer
        ):
            raise serializers.ValidationError(
                "Only the customer who created the booking can update this review"
            )
        return super().update(instance, validated_data)
