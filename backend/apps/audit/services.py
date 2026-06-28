from .models import AuditLog


class AuditService:

    @staticmethod
    def log(
        *,
        actor,
        entity_type,
        entity_id=None,
        action,
        description,
        changes=None,
        ip_address=None,
    ):
        return AuditLog.objects.create(
            actor=actor,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            description=description,
            changes=changes,
            ip_address=ip_address,
        )

    @staticmethod
    def list_logs(
        *,
        entity_type=None,
        entity_id=None,
        action=None,
        actor_id=None,
        date_from=None,
        date_to=None,
        page=1,
        page_size=20,
    ):
        qs = AuditLog.objects.select_related("actor")

        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        if entity_id:
            qs = qs.filter(entity_id=entity_id)
        if action:
            qs = qs.filter(action=action)
        if actor_id:
            qs = qs.filter(actor_id=actor_id)
        if date_from:
            qs = qs.filter(timestamp__date__gte=date_from)
        if date_to:
            qs = qs.filter(timestamp__date__lte=date_to)

        qs = qs.order_by("-timestamp")

        total = qs.count()
        start = (page - 1) * page_size
        end = start + page_size
        results = qs[start:end]

        return {
            "count": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "results": list(results),
        }

    @staticmethod
    def get_log(pk):
        from apps.core.exceptions import NotFoundError
        try:
            return AuditLog.objects.select_related("actor").get(id=pk)
        except AuditLog.DoesNotExist:
            raise NotFoundError("Audit log entry not found.")
