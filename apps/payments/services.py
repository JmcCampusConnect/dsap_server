import logging
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.audit.models import AuditLog
from apps.notifications.models import Notification, NotificationTemplate
from apps.requests.models import Request
from apps.workflow.constants import RequestStatuses, WorkflowStepKinds
from apps.workflow.models import WorkflowHistory, WorkflowStep

from .models import Payment, PaymentStatuses, PaymentVerificationLog

logger = logging.getLogger(__name__)


class PaymentFlowError(APIException):
    def __init__(self, code, detail, http_status):
        self.status_code = http_status
        super().__init__({"code": code, "detail": detail}, code=code)


def _payment_step(request_obj):
    step = (
        WorkflowStep.objects.filter(
            service_id=request_obj.service_id,
            step_kind=WorkflowStepKinds.PAYMENT_VERIFY,
        )
        .order_by("step_order")
        .first()
    )
    if not step:
        raise PaymentFlowError(
            "PAYMENT_NOT_CONFIGURED",
            "Payment verification is not configured for this service.",
            409,
        )
    return step


def _notify_student_after_commit(request_id, event_code, extra_context=None):
    request_obj = (
        Request.objects.select_related("student_id__user_id")
        .filter(pk=request_id)
        .first()
    )
    if not request_obj:
        logger.error(
            "Payment notification skipped: request %s no longer exists.", request_id
        )
        return

    templates = NotificationTemplate.objects.filter(event_code=event_code)
    if not templates.exists():
        logger.warning(
            "Payment notification skipped: no templates for event %s.", event_code
        )
        return

    context = defaultdict(
        str,
        {
            "request_number": request_obj.request_number,
            "amount": str(request_obj.payment.amount),
            "department_name": request_obj.service_id.service_department_id.name,
            "office_address": request_obj.service_id.service_department_id.office_address,
            "office_hours": request_obj.service_id.service_department_id.office_hours,
            "contact_phone": request_obj.service_id.service_department_id.contact_phone,
            "rejection_reason": request_obj.payment.rejection_reason,
            **(extra_context or {}),
        },
    )
    now = timezone.now()
    notifications = []
    for template in templates:
        body = template.template_body.format_map(context)
        notifications.append(
            Notification(
                request_id=request_obj,
                user_id=request_obj.student_id.user_id,
                channel=template.channel,
                template_id=template,
                subject=template.subject.format_map(context),
                message=body,
                status="SENT" if template.channel == "IN_APP" else "QUEUED",
                sent_at=now if template.channel == "IN_APP" else None,
            )
        )
        if body != template.template_body:
            logger.debug(
                "Rendered payment notification %s for request %s.",
                event_code,
                request_id,
            )
    Notification.objects.bulk_create(notifications)


def _schedule_notification(request_id, event_code, extra_context=None):
    transaction.on_commit(
        lambda: _notify_student_after_commit(request_id, event_code, extra_context)
    )


def send_payment_reminders(now=None):
    """Queue due in-app reminders for pending payments, respecting each department's cap."""
    now = now or timezone.now()
    payment_ids = Payment.objects.filter(
        payment_status=PaymentStatuses.PENDING,
        request_id__submitted_at__isnull=False,
    ).values_list("pk", flat=True)
    scheduled = 0

    for payment_id in payment_ids.iterator():
        with transaction.atomic():
            payment = Payment.objects.select_for_update(of=("self",)).get(
                pk=payment_id
            )
            request_obj = (
                Request.objects.select_for_update(of=("self",))
                .select_related("service_id__service_department_id")
                .get(pk=payment.request_id_id)
            )
            department = request_obj.service_id.service_department_id
            interval_days = department.payment_reminder_days
            maximum = department.payment_max_reminders
            if not interval_days or not maximum or payment.reminder_count >= maximum:
                continue

            last_sent = payment.last_reminder_at or request_obj.submitted_at
            if not last_sent or now < last_sent + timedelta(days=interval_days):
                continue
            if not NotificationTemplate.objects.filter(
                event_code="PAYMENT_REMINDER"
            ).exists():
                logger.error(
                    "Payment reminder skipped: no templates for request %s.",
                    request_obj.pk,
                )
                continue

            payment.reminder_count += 1
            payment.last_reminder_at = now
            payment.save(
                update_fields=["reminder_count", "last_reminder_at", "updated_at"]
            )
            _schedule_notification(request_obj.pk, "PAYMENT_REMINDER")
            scheduled += 1

    return scheduled


def submit_request(request_obj, *, submitted_by, offline_payment_acknowledged=False):
    """Submit a draft, snapshot its fee, and route it to the correct first step."""
    with transaction.atomic():
        locked_request = (
            Request.objects.select_for_update()
            .select_related("service_id__service_department_id", "student_id")
            .get(pk=request_obj.pk)
        )
        if locked_request.current_status != RequestStatuses.DRAFT:
            raise PaymentFlowError(
                "REQUEST_NOT_DRAFT", "Only draft requests can be submitted.", 400
            )

        service = locked_request.service_id
        department = service.service_department_id
        fee = Decimal(service.base_fee or 0)
        payment, _ = Payment.objects.select_for_update().get_or_create(
            request_id=locked_request,
            defaults={"amount": fee, "payment_status": PaymentStatuses.PENDING},
        )
        payment.amount = fee
        now = timezone.now()
        locked_request.submitted_at = now

        if fee > 0:
            if not offline_payment_acknowledged:
                raise PaymentFlowError(
                    "OFFLINE_PAYMENT_ACK_REQUIRED",
                    "Acknowledge the offline payment instructions before submitting.",
                    400,
                )
            step = _payment_step(locked_request)
            payment.payment_status = PaymentStatuses.PENDING
            due_days = department.payment_due_days
            payment.payment_due_at = (
                now + timedelta(days=due_days) if due_days else None
            )
            locked_request.current_status = RequestStatuses.PAYMENT_PENDING
            event_code = "PAYMENT_PENDING"
        else:
            step = (
                WorkflowStep.objects.filter(service_id=service)
                .exclude(step_kind=WorkflowStepKinds.PAYMENT_VERIFY)
                .order_by("step_order", "id")
                .first()
            )
            if not step:
                raise PaymentFlowError(
                    "WORKFLOW_NOT_CONFIGURED",
                    "No verification workflow step is configured for this service.",
                    409,
                )
            payment.payment_status = PaymentStatuses.SUCCESS
            payment.paid_at = now
            payment.payment_due_at = None
            locked_request.current_status = RequestStatuses.SUBMITTED
            event_code = None

        locked_request.current_step_id = step
        payment.save()
        locked_request.save(
            update_fields=[
                "current_status",
                "current_step_id",
                "submitted_at",
                "updated_at",
            ]
        )
        WorkflowHistory.objects.create(
            request_id=locked_request,
            step_id=step,
            action_by_user_id=submitted_by,
            action="SUBMIT",
            remarks="Application submitted.",
        )

        if event_code:
            _schedule_notification(locked_request.pk, event_code)

    request_obj.refresh_from_db()
    payment.refresh_from_db()
    return payment


def _locked_payment(payment):
    locked_payment = Payment.objects.select_for_update(of=("self",)).get(
        pk=payment.pk
    )
    request_obj = (
        Request.objects.select_for_update(of=("self",))
        .select_related(
            "service_id__service_department_id",
            "current_step_id__responsible_role_id",
            "student_id__user_id",
        )
        .get(pk=locked_payment.request_id_id)
    )
    locked_payment.request_id = request_obj
    return locked_payment


def _validate_payment_stage(payment):
    request_obj = payment.request_id
    if payment.payment_status == PaymentStatuses.SUCCESS:
        raise PaymentFlowError(
            "PAYMENT_ALREADY_VERIFIED", "This payment is already verified.", 409
        )
    if payment.payment_status not in {PaymentStatuses.PENDING, PaymentStatuses.ISSUE}:
        raise PaymentFlowError(
            "PAYMENT_NOT_VERIFIED", "This payment cannot be verified in its current state.", 409
        )
    if (
        request_obj.current_status
        not in {RequestStatuses.PAYMENT_PENDING, RequestStatuses.PAYMENT_ISSUE}
        or not request_obj.current_step_id
        or request_obj.current_step_id.step_kind != WorkflowStepKinds.PAYMENT_VERIFY
    ):
        raise PaymentFlowError(
            "PAYMENT_NOT_VERIFIED",
            "The application is not waiting at the payment verification stage.",
            409,
        )
    return request_obj


def _create_verification_log(**values):
    try:
        with transaction.atomic():
            return PaymentVerificationLog.objects.create(**values)
    except IntegrityError as exc:
        receipt_number = values.get("receipt_number")
        if receipt_number and PaymentVerificationLog.objects.filter(
            receipt_number__iexact=receipt_number
        ).exists():
            raise PaymentFlowError(
                "DUPLICATE_RECEIPT",
                "This receipt/reference number has already been recorded.",
                409,
            ) from exc
        raise


def confirm_payment(payment, staff_user, data):
    """Confirm a physically inspected bank challan and advance the request."""
    with transaction.atomic():
        locked_payment = _locked_payment(payment)
        request_obj = _validate_payment_stage(locked_payment)
        received_amount = Decimal(data["amount_received"])
        if received_amount != locked_payment.amount:
            raise PaymentFlowError(
                "AMOUNT_MISMATCH",
                "Amount received must match the application fee.",
                400,
            )

        next_step = (
            WorkflowStep.objects.filter(
                service_id=request_obj.service_id,
                step_order__gt=request_obj.current_step_id.step_order,
                step_kind=WorkflowStepKinds.VERIFICATION,
            )
            .order_by("step_order", "id")
            .first()
        )
        if not next_step:
            raise PaymentFlowError(
                "WORKFLOW_NOT_CONFIGURED",
                "No verification step is configured after payment verification.",
                409,
            )

        values = {
            "payment": locked_payment,
            "request": request_obj,
            "action": PaymentVerificationLog.CONFIRM,
            "amount_received": received_amount,
            "payment_date": data["payment_date"],
            "payment_mode": data["payment_mode"],
            "bank_name": data["bank_name"].strip(),
            "bank_branch": data.get("bank_branch", "").strip(),
            "receipt_number": (data.get("receipt_number") or "").strip() or None,
            "remarks": data.get("remarks", "").strip(),
            "reason": "",
            "acted_by": staff_user,
        }
        _create_verification_log(**values)

        now = timezone.now()
        locked_payment.payment_status = PaymentStatuses.SUCCESS
        locked_payment.amount_received = received_amount
        locked_payment.payment_date = data["payment_date"]
        locked_payment.payment_mode = data["payment_mode"]
        locked_payment.payment_method = data["payment_mode"]
        locked_payment.bank_name = values["bank_name"]
        locked_payment.bank_branch = values["bank_branch"]
        locked_payment.receipt_number = values["receipt_number"]
        locked_payment.remarks = values["remarks"]
        locked_payment.rejection_reason = ""
        locked_payment.verified_by = staff_user
        locked_payment.verified_at = now
        locked_payment.paid_at = now
        locked_payment.save()

        current_step = request_obj.current_step_id
        request_obj.current_step_id = next_step
        request_obj.current_status = RequestStatuses.SUBMITTED
        request_obj.save(
            update_fields=["current_step_id", "current_status", "updated_at"]
        )
        WorkflowHistory.objects.create(
            request_id=request_obj,
            step_id=current_step,
            action_by_user_id=staff_user,
            action="PAYMENT_CONFIRM",
            remarks=values["remarks"] or "Offline payment verified.",
        )
        AuditLog.log(
            request=None,
            action="UPDATE",
            obj=locked_payment,
            changes={"payment_status": {"old": PaymentStatuses.PENDING, "new": PaymentStatuses.SUCCESS}},
            user=staff_user,
        )
        _schedule_notification(request_obj.pk, "PAYMENT_VERIFIED")

    payment.refresh_from_db()
    return payment


def reject_payment(payment, staff_user, reason, data=None):
    """Record a rejected payment attempt without losing earlier attempts."""
    reason = (reason or "").strip()
    if not reason:
        raise PaymentFlowError(
            "REJECTION_REASON_REQUIRED", "A rejection reason is required.", 400
        )
    data = data or {}

    with transaction.atomic():
        locked_payment = _locked_payment(payment)
        request_obj = _validate_payment_stage(locked_payment)
        current_step = request_obj.current_step_id
        _create_verification_log(
            payment=locked_payment,
            request=request_obj,
            action=PaymentVerificationLog.REJECT,
            amount_received=data.get("amount_received"),
            payment_date=data.get("payment_date"),
            payment_mode=data.get("payment_mode"),
            bank_name=(data.get("bank_name") or "").strip(),
            bank_branch=(data.get("bank_branch") or "").strip(),
            receipt_number=(data.get("receipt_number") or "").strip() or None,
            remarks=(data.get("remarks") or "").strip(),
            reason=reason,
            acted_by=staff_user,
        )

        now = timezone.now()
        locked_payment.payment_status = PaymentStatuses.ISSUE
        locked_payment.rejection_reason = reason
        locked_payment.remarks = (data.get("remarks") or "").strip()
        locked_payment.verified_by = staff_user
        locked_payment.verified_at = now
        locked_payment.save(
            update_fields=[
                "payment_status",
                "rejection_reason",
                "remarks",
                "verified_by",
                "verified_at",
                "updated_at",
            ]
        )
        request_obj.current_status = RequestStatuses.PAYMENT_ISSUE
        request_obj.save(update_fields=["current_status", "updated_at"])
        WorkflowHistory.objects.create(
            request_id=request_obj,
            step_id=current_step,
            action_by_user_id=staff_user,
            action="PAYMENT_REJECT",
            remarks=reason,
        )
        AuditLog.log(
            request=None,
            action="UPDATE",
            obj=locked_payment,
            changes={"payment_status": {"old": PaymentStatuses.PENDING, "new": PaymentStatuses.ISSUE}},
            user=staff_user,
        )
        _schedule_notification(
            request_obj.pk,
            "PAYMENT_REJECTED",
            {"rejection_reason": reason},
        )

    payment.refresh_from_db()
    return payment
