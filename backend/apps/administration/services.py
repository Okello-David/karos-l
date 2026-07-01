from django.contrib.auth.models import Group

from apps.accounts.models import User
from apps.core.exceptions import ConflictError, NotFoundError
from apps.properties.models import Property
from apps.sections.models import Section
from apps.units.models import PricingRule, Unit, UnitStatus


class AdminService:

    # ---- Properties ----

    @staticmethod
    def list_properties():
        return Property.objects.all().order_by("name")

    @staticmethod
    def get_property(pk):
        try:
            return Property.objects.get(id=pk)
        except Property.DoesNotExist:
            raise NotFoundError("Property not found.")

    @staticmethod
    def create_property(data):
        return Property.objects.create(**data)

    @staticmethod
    def update_property(instance, data):
        for attr, value in data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    @staticmethod
    def archive_property(pk):
        prop = AdminService.get_property(pk)
        if prop.sections.filter(is_active=True).exists():
            raise ConflictError(
                "Cannot archive a property with active sections. "
                "Archive all sections first."
            )
        prop.is_active = False
        prop.save()
        return prop

    # ---- Sections ----

    @staticmethod
    def list_sections(property_id=None):
        qs = Section.objects.select_related("property").all()
        if property_id:
            qs = qs.filter(property_id=property_id)
        return qs.order_by("property__name", "order", "name")

    @staticmethod
    def get_section(pk):
        try:
            return Section.objects.select_related("property").get(id=pk)
        except Section.DoesNotExist:
            raise NotFoundError("Section not found.")

    @staticmethod
    def create_section(data):
        return Section.objects.create(**data)

    @staticmethod
    def update_section(instance, data):
        for attr, value in data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    @staticmethod
    def archive_section(pk):
        section = AdminService.get_section(pk)
        if section.units.filter(is_active=True).exists():
            raise ConflictError(
                "Cannot archive a section with active units. "
                "Archive all units first."
            )
        section.is_active = False
        section.save()
        return section

    @staticmethod
    def reorder_sections(order_data):
        for item in order_data:
            Section.objects.filter(id=item["id"]).update(order=item["order"])
        return True

    # ---- Units ----

    @staticmethod
    def list_units(section_id=None, status=None):
        qs = Unit.objects.select_related("section__property").all()
        if section_id:
            qs = qs.filter(section_id=section_id)
        if status:
            qs = qs.filter(status=status)
        return qs.order_by("section__name", "order", "name")

    @staticmethod
    def get_unit(pk):
        try:
            return Unit.objects.select_related("section__property").get(id=pk)
        except Unit.DoesNotExist:
            raise NotFoundError("Unit not found.")

    @staticmethod
    def create_unit(data):
        return Unit.objects.create(**data)

    @staticmethod
    def update_unit(instance, data):
        for attr, value in data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    @staticmethod
    def archive_unit(pk):
        unit = AdminService.get_unit(pk)
        if unit.current_occupant_count() > 0:
            raise ConflictError(
                "Cannot archive a unit that has active occupants. "
                "Check out all occupants first."
            )
        unit.status = UnitStatus.ARCHIVED
        unit.save()
        return unit

    # ---- Pricing Rules ----

    @staticmethod
    def list_pricing_rules(unit_id=None, billing_mode=None):
        qs = PricingRule.objects.select_related("unit__section__property").all()
        if unit_id:
            qs = qs.filter(unit_id=unit_id)
        if billing_mode:
            qs = qs.filter(billing_mode=billing_mode)
        return qs.order_by("-effective_date")

    @staticmethod
    def get_pricing_rule(pk):
        try:
            return PricingRule.objects.get(id=pk)
        except PricingRule.DoesNotExist:
            raise NotFoundError("Pricing rule not found.")

    @staticmethod
    def create_pricing_rule(data):
        return PricingRule.objects.create(**data)

    @staticmethod
    def update_pricing_rule(instance, data):
        for attr, value in data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    @staticmethod
    def delete_pricing_rule(pk):
        rule = AdminService.get_pricing_rule(pk)
        rule.delete()
        return True

    @staticmethod
    def get_effective_price(unit_id, billing_mode, as_of_date=None):
        from datetime import date
        as_of = as_of_date or date.today()
        rule = PricingRule.objects.filter(
            unit_id=unit_id,
            billing_mode=billing_mode,
            effective_date__lte=as_of,
        ).order_by("-effective_date").first()
        if rule:
            return rule.price
        unit = Unit.objects.get(id=unit_id)
        if billing_mode == "semester":
            return unit.semester_price
        return unit.monthly_price

    # ---- Users ----

    @staticmethod
    def list_users():
        return User.objects.all().order_by("username")

    @staticmethod
    def get_user(pk):
        try:
            return User.objects.get(id=pk)
        except User.DoesNotExist:
            raise NotFoundError("User not found.")

    @staticmethod
    def create_user(data):
        groups_data = data.pop("groups", [])
        password = data.pop("password", None)
        user = User(**data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        user.groups.set(groups_data)
        return user

    @staticmethod
    def update_user(instance, data):
        groups_data = data.pop("groups", None)
        password = data.pop("password", None)
        for attr, value in data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        if groups_data is not None:
            instance.groups.set(groups_data)
        return instance

    @staticmethod
    def list_groups():
        return Group.objects.all().order_by("name")
