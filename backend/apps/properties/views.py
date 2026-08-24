from django.db.models import Prefetch, Q

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.occupancy.models import Occupancy
from apps.sections.models import Section
from apps.units.models import Unit

from .models import Property
from .serializers import PropertyExplorerSerializer, PropertySerializer


class PropertyListView(generics.ListAPIView):
    queryset = Property.objects.filter(is_active=True)
    serializer_class = PropertySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None


class PropertyExplorerView(generics.ListAPIView):
    serializer_class = PropertyExplorerSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        search = self.request.query_params.get("search", "").strip()

        base_units = Unit.objects.filter(is_active=True)

        if search:
            matching_unit_ids = base_units.filter(
                Q(name__icontains=search)
                | Q(occupancies__student__first_name__icontains=search)
                | Q(occupancies__student__last_name__icontains=search)
            ).values_list("id", flat=True).distinct()

            matching_property_ids = (
                Unit.objects
                .filter(id__in=matching_unit_ids)
                .values_list("section__property_id", flat=True)
                .distinct()
            )

            property_qs = Property.objects.filter(
                id__in=matching_property_ids, is_active=True
            )
            units_qs = base_units.filter(id__in=matching_unit_ids)
        else:
            property_qs = Property.objects.filter(is_active=True)
            units_qs = base_units

        units_qs = units_qs.prefetch_related(
            Prefetch(
                "occupancies",
                queryset=Occupancy.objects
                .filter(end_date__isnull=True)
                .select_related("student"),
                to_attr="active_occupancies",
            )
        ).order_by("name")

        sections_qs = Section.objects.filter(is_active=True).prefetch_related(
            Prefetch("units", queryset=units_qs)
        )

        property_qs = property_qs.prefetch_related(
            Prefetch("sections", queryset=sections_qs)
        ).order_by("name")

        return property_qs
