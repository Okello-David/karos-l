from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.core.permissions import IsPropertyManager

from .models import Section
from .serializers import SectionSerializer


class SectionListView(generics.ListAPIView):
    serializer_class = SectionSerializer
    permission_classes = [IsAuthenticated | IsPropertyManager]
    pagination_class = None

    def get_queryset(self):
        queryset = Section.objects.filter(is_active=True)
        property_id = self.request.query_params.get("property")
        if property_id:
            queryset = queryset.filter(property_id=property_id)
        return queryset
