from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.role_constants import Roles
from apps.audit.models import AuditLog
from apps.departments.models import ServiceDepartment
from apps.payments.models import Payment
from apps.requests.models import Request
from apps.services.models import Service
from apps.workflow.constants import AllowedActions, RequestStatuses
from apps.workflow.models import WorkflowHistory


DASHBOARD_ROLES = (
    Roles.SYSTEM_ADMIN,
    Roles.SERVICE_DEPT_ADMIN,
    Roles.SERVICE_DEPT_STAFF,
)
NON_DRAFT_STATUSES = (
    RequestStatuses.SUBMITTED,
    RequestStatuses.UNDER_VERIFICATION,
    RequestStatuses.APPROVED,
    RequestStatuses.COMPLETED,
    RequestStatuses.REJECTED,
    RequestStatuses.RETURNED,
)
TERMINAL_STATUSES = (RequestStatuses.COMPLETED, RequestStatuses.REJECTED)
PENDING_STATUSES = (
    RequestStatuses.SUBMITTED,
    RequestStatuses.UNDER_VERIFICATION,
    RequestStatuses.APPROVED,
    RequestStatuses.RETURNED,
)


class IsDashboardRole(BasePermission):
    """Restrict dashboard aggregates to the three roles that own this dashboard."""

    message = "This dashboard is not available for your role."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "is_active", False)
            and getattr(user, "role_name", None) in DASHBOARD_ROLES
        )


class DashboardView(APIView):
    """
    Return live dashboard aggregates.

    Draft requests are excluded. Department admin counts include the current
    department's admin/staff workflow steps; staff counts include only steps
    routed to SERVICE_DEPT_STAFF. Open means any in-scope status except
    COMPLETED and REJECTED. SLA uses submitted_at plus the service's elapsed
    24-hour SLA days. Monthly completion uses completed_at in the current local
    calendar month; revenue is successful payments paid in that month.
    """

    permission_classes = [IsAuthenticated, IsDashboardRole]

    def get(self, request):
        user = request.user
        role = user.role_name
        system_admin = role == Roles.SYSTEM_ADMIN
        department_id = None

        if not system_admin:
            department = getattr(user, "service_department_id", None)
            department_id = getattr(department, "id", None)
            if department_id is None:
                return Response(
                    {"detail": "A service department is required for this dashboard."},
                    status=403,
                )

        now = timezone.now()
        local_now = timezone.localtime(now)
        month_start = timezone.make_aware(
            datetime.combine(
                local_now.date().replace(day=1),
                time.min,
            ),
            timezone.get_current_timezone(),
        )
        month_index = local_now.year * 12 + local_now.month - 1
        revenue_periods = []
        for offset in range(5, -1, -1):
            period_index = month_index - offset
            period_date = date(period_index // 12, period_index % 12 + 1, 1)
            revenue_periods.append(
                timezone.make_aware(
                    datetime.combine(period_date, time.min),
                    timezone.get_current_timezone(),
                )
            )
        revenue_start = revenue_periods[0]
        next_month_start = timezone.make_aware(
            datetime.combine(
                date(
                    local_now.year + (1 if local_now.month == 12 else 0),
                    1 if local_now.month == 12 else local_now.month + 1,
                    1,
                ),
                time.min,
            ),
            timezone.get_current_timezone(),
        )
        today_start = timezone.make_aware(
            datetime.combine(local_now.date(), time.min),
            timezone.get_current_timezone(),
        )
        tomorrow_start = today_start + timedelta(days=1)
        week_start = today_start - timedelta(days=local_now.weekday())

        requests = Request.objects.filter(current_status__in=NON_DRAFT_STATUSES)
        if not system_admin:
            requests = requests.filter(service_id__service_department_id_id=department_id)
            if role == Roles.SERVICE_DEPT_STAFF:
                requests = requests.filter(
                    current_step_id__responsible_role_id__name=Roles.SERVICE_DEPT_STAFF
                )
            else:
                requests = requests.filter(
                    current_step_id__responsible_role_id__name__in=(
                        Roles.SERVICE_DEPT_ADMIN,
                        Roles.SERVICE_DEPT_STAFF,
                    )
                )

        total_requests = requests.count()
        open_requests = requests.exclude(current_status__in=TERMINAL_STATUSES)
        status_counts = list(
            requests.values("current_status")
            .annotate(count=Count("id"))
            .order_by("current_status")
        )
        services = list(
            requests.values("service_id", "service_id__name")
            .annotate(request_count=Count("id"))
            .order_by("-request_count", "service_id__name")[:8]
        )

        recent_requests = list(
            requests.select_related("student_id", "service_id", "service_id__service_department_id")
            .order_by("-submitted_at", "-id")
            .values(
                "id",
                "request_number",
                "current_status",
                "submitted_at",
                "student_id__name",
                "student_id__register_number",
                "service_id__name",
                "service_id__service_department_id__name",
            )[:8]
        )

        active_sla_requests = open_requests.filter(submitted_at__isnull=False).values_list(
            "submitted_at", "service_id__sla_days"
        )
        sla_breaches = 0
        due_today = 0
        for submitted_at, sla_days in active_sla_requests:
            due_at = submitted_at + timedelta(days=sla_days)
            if due_at < now:
                sla_breaches += 1
            elif today_start <= due_at < tomorrow_start:
                due_today += 1

        completed_this_month = requests.filter(
            current_status=RequestStatuses.COMPLETED,
            completed_at__gte=month_start,
            completed_at__lte=now,
        ).count()

        actions_today = None
        forwarded_this_week = None
        revenue_scope = Payment.objects.filter(
                payment_status="SUCCESS",
                paid_at__gte=revenue_start,
                paid_at__lt=next_month_start,
            )
        if not system_admin:
            revenue_scope = revenue_scope.filter(
                request_id__service_id__service_department_id_id=department_id
            )

        revenue_by_month = {
            timezone.localtime(item["month"]).strftime("%Y-%m"): item["total"]
            for item in revenue_scope.annotate(month=TruncMonth("paid_at"))
            .values("month")
            .annotate(total=Sum("amount"))
        }
        revenue_history = [
            {
                "month": timezone.localtime(period).strftime("%Y-%m"),
                "amount": str(revenue_by_month.get(
                    timezone.localtime(period).strftime("%Y-%m"), Decimal("0.00")
                )),
            }
            for period in revenue_periods
        ]
        paid_revenue = revenue_by_month.get(
            local_now.strftime("%Y-%m"), Decimal("0.00")
        )

        if system_admin:
            active_users = User.objects.filter(is_active=True).count()
            service_departments = ServiceDepartment.objects.count()
            service_counts = dict(
                Service.objects.values("service_department_id_id")
                .annotate(total=Count("id"))
                .values_list("service_department_id_id", "total")
            )
            staff_counts = dict(
                User.objects.filter(
                    is_active=True,
                    role_id__name__in=(Roles.SERVICE_DEPT_ADMIN, Roles.SERVICE_DEPT_STAFF),
                    service_department_id__isnull=False,
                )
                .values("service_department_id_id")
                .annotate(total=Count("id"))
                .values_list("service_department_id_id", "total")
            )
            department_requests = list(
                requests.values("service_id__service_department_id_id")
                .annotate(
                    total=Count("id"),
                    pending=Count("id", filter=Q(current_status__in=PENDING_STATUSES)),
                )
            )
            request_counts = {
                item["service_id__service_department_id_id"]: item for item in department_requests
            }
            department_breaches = {}
            for department_key, submitted_at, sla_days in open_requests.filter(
                submitted_at__isnull=False
            ).values_list(
                "service_id__service_department_id_id",
                "submitted_at",
                "service_id__sla_days",
            ):
                if submitted_at + timedelta(days=sla_days) < now:
                    department_breaches[department_key] = (
                        department_breaches.get(department_key, 0) + 1
                    )
            department_revenue = {
                item["request_id__service_id__service_department_id_id"]: item["total"]
                for item in revenue_scope.filter(paid_at__gte=month_start, paid_at__lte=now)
                .values("request_id__service_id__service_department_id_id")
                .annotate(total=Sum("amount"))
            }
            department_overview = [
                {
                    "id": department.id,
                    "code": department.code,
                    "name": department.name,
                    "services": service_counts.get(department.id, 0),
                    "staff": staff_counts.get(department.id, 0),
                    "requests": request_counts.get(department.id, {}).get("total", 0),
                    "pending": request_counts.get(department.id, {}).get("pending", 0),
                    "sla_breaches": department_breaches.get(department.id, 0),
                    "paid_revenue_this_month": str(
                        department_revenue.get(department.id, Decimal("0.00"))
                    ),
                }
                for department in ServiceDepartment.objects.order_by("name")
            ]
            staff_activity = []
            activities = [
                {
                    "id": activity.id,
                    "action": activity.action,
                    "summary": activity.object_repr or activity.model_name or activity.action,
                    "actor": activity.user_name or "System",
                    "occurred_at": activity.created_at,
                }
                for activity in AuditLog.objects.order_by("-created_at")[:8]
            ]
            scope = {"type": "global", "department": None}
        else:
            active_users = (
                User.objects.filter(is_active=True, service_department_id_id=department_id).count()
                if role == Roles.SERVICE_DEPT_ADMIN
                else None
            )
            service_departments = None
            department_overview = []
            if role == Roles.SERVICE_DEPT_ADMIN:
                staff_activity = [
                    {
                        "username": item["action_by_user_id__username"],
                        "requests_handled": item["requests_handled"],
                    }
                    for item in WorkflowHistory.objects.filter(
                        request_id__service_id__service_department_id_id=department_id,
                        step_id__responsible_role_id__name=Roles.SERVICE_DEPT_STAFF,
                        action_at__gte=month_start,
                        action_at__lt=next_month_start,
                    )
                    .values("action_by_user_id__username")
                    .annotate(requests_handled=Count("request_id", distinct=True))
                    .order_by("-requests_handled", "action_by_user_id__username")[:8]
                ]
            else:
                staff_activity = []

            activity_query = WorkflowHistory.objects.filter(
                request_id__service_id__service_department_id_id=department_id
            )
            if role == Roles.SERVICE_DEPT_STAFF:
                activity_query = activity_query.filter(
                    step_id__responsible_role_id__name=Roles.SERVICE_DEPT_STAFF
                )
            if role == Roles.SERVICE_DEPT_STAFF:
                staff_history = WorkflowHistory.objects.filter(
                    action_by_user_id=user,
                    request_id__service_id__service_department_id_id=department_id,
                    step_id__responsible_role_id__name=Roles.SERVICE_DEPT_STAFF,
                )
                actions_today = staff_history.filter(
                    action_at__gte=today_start, action_at__lt=tomorrow_start
                ).count()
                forwarded_this_week = staff_history.filter(
                    action=AllowedActions.FORWARD,
                    action_at__gte=week_start,
                    action_at__lt=tomorrow_start,
                ).count()
            else:
                actions_today = None
                forwarded_this_week = None
            activities = [
                {
                    "id": activity.id,
                    "action": activity.action,
                    "summary": activity.remarks or activity.action.replace("_", " ").title(),
                    "actor": activity.action_by_user_id.username,
                    "request_number": activity.request_id.request_number,
                    "occurred_at": activity.action_at,
                }
                for activity in activity_query.select_related(
                    "action_by_user_id", "request_id"
                ).order_by("-action_at")[:8]
            ]
            scope = {
                "type": "service_department",
                "department": user.service_department_id.name,
            }

        awaiting_approval = requests.filter(
            current_status__in=(RequestStatuses.SUBMITTED, RequestStatuses.UNDER_VERIFICATION),
            current_step_id__responsible_role_id__name=Roles.SERVICE_DEPT_ADMIN,
        ).count()

        return Response(
            {
                "role": role,
                "scope": scope,
                "period": {
                    "month_start": month_start,
                    "as_of": now,
                },
                "metrics": {
                    "total_requests": total_requests,
                    "open_requests": open_requests.count(),
                    "awaiting_verification": requests.filter(
                        current_status__in=(
                            RequestStatuses.SUBMITTED,
                            RequestStatuses.UNDER_VERIFICATION,
                        )
                    ).count(),
                    "awaiting_approval": awaiting_approval,
                    "completed_this_month": completed_this_month,
                    "sla_breaches": sla_breaches,
                    "due_today": due_today if role == Roles.SERVICE_DEPT_STAFF else None,
                    "actions_today": actions_today,
                    "forwarded_this_week": forwarded_this_week,
                    "paid_revenue_this_month": (
                        str(paid_revenue)
                        if role in (Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN)
                        else None
                    ),
                    "active_users": active_users,
                    "service_departments": service_departments,
                },
                "status_counts": [
                    {"status": item["current_status"], "count": item["count"]}
                    for item in status_counts
                ],
                "services": [
                    {
                        "id": item["service_id"],
                        "name": item["service_id__name"],
                        "request_count": item["request_count"],
                    }
                    for item in services
                ],
                "revenue_history": (
                    revenue_history
                    if role in (Roles.SYSTEM_ADMIN, Roles.SERVICE_DEPT_ADMIN)
                    else []
                ),
                "department_overview": department_overview,
                "staff_activity": staff_activity,
                "recent_requests": [
                    {
                        "id": item["id"],
                        "request_number": item["request_number"],
                        "status": item["current_status"],
                        "submitted_at": item["submitted_at"],
                        "student_name": item["student_id__name"],
                        "register_number": item["student_id__register_number"],
                        "service_name": item["service_id__name"],
                        "department_name": item["service_id__service_department_id__name"],
                    }
                    for item in recent_requests
                ],
                "recent_activity": activities,
            }
        )
