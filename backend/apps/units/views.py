from rest_framework import generics
from rest_framework.permissions import IsAuthenticated


from .models import Unit
from .serializers import UnitDetailSerializer, UnitSerializer


class UnitListView(generics.ListAPIView):
    serializer_class = UnitSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        queryset = Unit.objects.filter(is_active=True).select_related("section__property")
        section_id = self.request.query_params.get("section")
        if section_id:
            queryset = queryset.filter(section_id=section_id)
        return queryset


class UnitDetailView(generics.RetrieveAPIView):
    serializer_class = UnitDetailSerializer
    permission_classes = [IsAuthenticated]
    queryset = Unit.objects.filter(is_active=True).select_related("section__property")
