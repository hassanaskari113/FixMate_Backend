from django.contrib import admin

from .models import (
    Booking,
    Offer,
    ProviderProfile,
    RequestImage,
    Review,
    ReviewImage,
    Service,
    ServiceArea,
    ServiceCategory,
    ServiceRequest,
    User,
)

# Register your models here.
admin.site.register(User)
admin.site.register(ServiceCategory)
admin.site.register(Service)
admin.site.register(ServiceArea)
admin.site.register(ProviderProfile)
admin.site.register(RequestImage)
admin.site.register(ServiceRequest)
admin.site.register(Offer)
admin.site.register(Booking)
admin.site.register(ReviewImage)
admin.site.register(Review)
