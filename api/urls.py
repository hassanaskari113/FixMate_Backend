from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import *

router = DefaultRouter()
router.register("users", UserViewSet)
router.register("service_categories", ServiceCategoryViewSet)
router.register("services", ServiceViewSet)
router.register("service_areas", ServiceAreaViewSet)
router.register("provider_profiles", ProviderProfileViewSet)
router.register("service_requests", ServiceRequestViewSet)
router.register("offers", OfferViewSet)
router.register("bookings", BookingViewSet)
router.register("reviews", ReviewViewSet)


urlpatterns = [
    path("auth/google/", GoogleAuthView.as_view(), name="auth_google"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("", include(router.urls)),
]
