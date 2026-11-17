# Database Models

This reference describes the application models currently declared in `apps/*/models.py`. It records Django field types and model-level constraints; exact physical SQL types can vary with the configured database backend.

`null` describes whether the database column accepts `NULL`; `blank` describes form/validation behavior. Unless listed otherwise, fields are required, have no explicit default, and have no additional uniqueness constraint. All `BigAutoField` IDs are primary keys.

## Accounts (`accounts`)

### `Role` — table `role`

| Field | Type | Options / meaning |
|---|---|---|
| `id` | `BigAutoField` | Primary key |
| `name` | `CharField(50)` | Unique |
| `description` | `TextField` | `blank=True` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |
| `updated_at` | `DateTimeField` | `auto_now=True` |

### `User` — table `user`

| Field | Type | Options / meaning |
|---|---|---|
| `id` | `BigAutoField` | Primary key |
| `username` | `CharField(100)` | Unique |
| `email` | `EmailField(150)` | Unique; `null=True`, `blank=True` |
| `password_hash` | `CharField(255)` | |
| `role_id` | `ForeignKey → Role` | Required; `db_column="role_id"`; `on_delete=RESTRICT` |
| `service_department_id` | `ForeignKey → ServiceDepartment` | `null=True`, `blank=True`; `db_column="service_department_id"`; `on_delete=RESTRICT` |
| `is_active` | `BooleanField` | Default `True` |
| `last_login` | `DateTimeField` | `null=True`, `blank=True` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |
| `updated_at` | `DateTimeField` | `auto_now=True` |

## Departments (`departments`)

### `ServiceDepartment` — table `service_department`

| Field | Type | Options / meaning |
|---|---|---|
| `id` | `BigAutoField` | Primary key |
| `code` | `CharField(20)` | Unique |
| `name` | `CharField(150)` | |
| `hod_user_id` | `ForeignKey → User` | `null=True`, `blank=True`; `db_column="hod_user_id"`; `on_delete=RESTRICT` |
| `status` | `BooleanField` | Default `True` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |
| `updated_at` | `DateTimeField` | `auto_now=True` |

### `AcademicDepartment` — table `academic_department`

| Field | Type | Options / meaning |
|---|---|---|
| `id` | `BigAutoField` | Primary key |
| `code` | `CharField(20)` | |
| `stream` | `CharField(10)` | Choices: `SFM`, `SFW`, `Aided`; default `SFM` |
| `degree` | `CharField(50)` | |
| `branch` | `CharField(100)` | |
| `type` | `CharField(100)` | Choices: `UG`, `PG` |
| `category` | `CharField(100)` | Choices: `ARTS`, `SCIENCE` |
| `status` | `CharField(10)` | Choices: `active`, `inactive`; default `active` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |
| `updated_at` | `DateTimeField` | `auto_now=True` |

Constraints and ordering: unique together on (`code`, `stream`); index on (`type`, `category`); ordered by `code`, `stream`.

## Students (`students`)

### `Student` — table `student`

| Field | Type | Options / meaning |
|---|---|---|
| `id` | `BigAutoField` | Primary key |
| `register_number` | `CharField(30)` | Unique |
| `name` | `CharField(100)` | |
| `dob` | `DateField` | `null=True`, `blank=True` |
| `user_id` | `OneToOneField → User` | Required; `db_column="user_id"`; `on_delete=RESTRICT` |
| `academic_department_id` | `ForeignKey → AcademicDepartment` | Required; `db_column="academic_department_id"`; `on_delete=RESTRICT` |
| `year_of_admission` | `CharField(9)` | |
| `section` | `CharField(10)` | `null=True`, `blank=True` |
| `stream` | `CharField(10)` | Choices: `SFM`, `SFW`, `AIDED`; default `SFM` |
| `mobile_number` | `CharField(15)` | |
| `status` | `BooleanField` | Default `True` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |
| `updated_at` | `DateTimeField` | `auto_now=True` |

## Services (`services`)

### `Service` — table `service`

| Field | Type | Options / meaning |
|---|---|---|
| `id` | `BigAutoField` | Primary key |
| `code` | `CharField(20)` | Unique |
| `name` | `CharField(200)` | |
| `service_department_id` | `ForeignKey → ServiceDepartment` | Required; `db_column="service_department_id"`; `on_delete=RESTRICT` |
| `base_fee` | `DecimalField(10, 2)` | Default `0` |
| `sla_days` | `SmallIntegerField` | Default `7` |
| `description` | `TextField` | `null=True`, `blank=True` |
| `status` | `BooleanField` | Default `True` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |
| `updated_at` | `DateTimeField` | `auto_now=True` |

### `ServiceField` — table `service_field`

| Field | Type | Options / meaning |
|---|---|---|
| `id` | `BigAutoField` | Primary key |
| `service_id` | `ForeignKey → Service` | Required; `db_column="service_id"`; `on_delete=CASCADE` |
| `field_label` | `CharField(150)` | |
| `field_type` | `CharField(20)` | |
| `is_required` | `BooleanField` | Default `False` |
| `display_order` | `SmallIntegerField` | Default `0` |
| `options_json` | `JSONField` | `null=True`, `blank=True` |
| `conditional_logic` | `JSONField` | `null=True`, `blank=True` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |
| `updated_at` | `DateTimeField` | `auto_now=True` |

### `ServiceDocument` — table `service_document`

| Field | Type | Options / meaning |
|---|---|---|
| `id` | `BigAutoField` | Primary key |
| `service_id` | `ForeignKey → Service` | Required; `db_column="service_id"`; `on_delete=CASCADE` |
| `document_name` | `CharField(150)` | |
| `is_mandatory` | `BooleanField` | Default `True` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |
| `updated_at` | `DateTimeField` | `auto_now=True` |

## Requests (`requests`)

### `Request` — table `request`

| Field | Type | Options / meaning |
|---|---|---|
| `id` | `BigAutoField` | Primary key |
| `request_number` | `CharField(30)` | Unique |
| `student_id` | `ForeignKey → Student` | Required; `db_column="student_id"`; `on_delete=RESTRICT` |
| `service_id` | `ForeignKey → Service` | Required; `db_column="service_id"`; `on_delete=RESTRICT` |
| `current_status` | `CharField(30)` | Default `DRAFT` |
| `current_step_id` | `ForeignKey → WorkflowStep` | `null=True`, `blank=True`; `db_column="current_step_id"`; `on_delete=RESTRICT` |
| `submitted_at` | `DateTimeField` | `null=True`, `blank=True` |
| `completed_at` | `DateTimeField` | `null=True`, `blank=True` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |
| `updated_at` | `DateTimeField` | `auto_now=True` |

Indexes: (`student_id`, `current_status`) and (`service_id`, `current_status`).

### `RequestFieldValue` — table `request_field_value`

| Field | Type | Options / meaning |
|---|---|---|
| `id` | `BigAutoField` | Primary key |
| `request_id` | `ForeignKey → Request` | Required; `db_column="request_id"`; `on_delete=CASCADE` |
| `field_id` | `ForeignKey → ServiceField` | Required; `db_column="field_id"`; `on_delete=RESTRICT` |
| `field_value` | `TextField` | `null=True`, `blank=True` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |
| `updated_at` | `DateTimeField` | `auto_now=True` |

## Documents (`documents`)

### `Document` — table `document`

| Field | Type | Options / meaning |
|---|---|---|
| `id` | `BigAutoField` | Primary key |
| `request_id` | `ForeignKey → Request` | Required; `db_column="request_id"`; `on_delete=CASCADE` |
| `service_document_id` | `ForeignKey → ServiceDocument` | Required; `db_column="service_document_id"`; `on_delete=RESTRICT` |
| `file_path` | `CharField(500)` | |
| `file_hash` | `CharField(64)` | |
| `verification_status` | `CharField(20)` | Default `PENDING` |
| `rejection_remarks` | `TextField` | `null=True`, `blank=True` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |
| `updated_at` | `DateTimeField` | `auto_now=True` |

## Workflow (`workflow`)

### `WorkflowStep` — table `workflow_step`

| Field | Type | Options / meaning |
|---|---|---|
| `id` | `BigAutoField` | Primary key |
| `service_id` | `ForeignKey → Service` | Required; `db_column="service_id"`; `on_delete=CASCADE` |
| `step_order` | `SmallIntegerField` | |
| `step_name` | `CharField(150)` | |
| `step_kind` | `CharField(20)` | Choices are defined by `WorkflowStepKinds`; default `CUSTOM` |
| `responsible_role_id` | `ForeignKey → Role` | Required; `db_column="responsible_role_id"`; `on_delete=RESTRICT` |
| `allowed_actions` | `JSONField` | Default `[]`; `blank=True` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |
| `updated_at` | `DateTimeField` | `auto_now=True` |

Constraint and ordering: unique together on (`service_id`, `step_order`); ordered by `step_order`, `id`.

### `WorkflowHistory` — table `workflow_history`

| Field | Type | Options / meaning |
|---|---|---|
| `id` | `BigAutoField` | Primary key |
| `request_id` | `ForeignKey → Request` | Required; `db_column="request_id"`; `on_delete=CASCADE` |
| `step_id` | `ForeignKey → WorkflowStep` | `null=True`, `blank=True`; `db_column="step_id"`; `on_delete=RESTRICT` |
| `action_by_user_id` | `ForeignKey → User` | Required; `db_column="action_by_user_id"`; `on_delete=RESTRICT` |
| `action` | `CharField(30)` | |
| `remarks` | `TextField` | `null=True`, `blank=True` |
| `action_at` | `DateTimeField` | `auto_now_add=True` |

Index: (`request_id`, `action_at`).

## Payments (`payments`)

### `Payment` — table `payment`

| Field | Type | Options / meaning |
|---|---|---|
| `id` | `BigAutoField` | Primary key |
| `request_id` | `OneToOneField → Request` | Required; `db_column="request_id"`; `on_delete=RESTRICT` |
| `amount` | `DecimalField(10, 2)` | |
| `payment_status` | `CharField(20)` | Choices: `Pending`, `Success`, `Issue`; default `Pending` |
| `amount_received` | `DecimalField(10, 2)` | `null=True`, `blank=True` |
| `payment_date` | `DateField` | `null=True`, `blank=True` |
| `receipt_number` | `CharField(100)` | `null=True`, `blank=True` |
| `verified_by` | `ForeignKey → User` | `null=True`, `blank=True`; `on_delete=SET_NULL`; reverse name `verified_payments` |
| `verified_at` | `DateTimeField` | `null=True`, `blank=True` |
| `remarks` | `TextField` | `blank=True` |
| `rejection_reason` | `TextField` | `blank=True` |
| `paid_at` | `DateTimeField` | `null=True`, `blank=True` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |
| `updated_at` | `DateTimeField` | `auto_now=True` |

### `PaymentVerificationLog` — table `payment_verification_log`

| Field | Type | Options / meaning |
|---|---|---|
| `id` | `BigAutoField` | Primary key |
| `payment` | `ForeignKey → Payment` | Required; `on_delete=RESTRICT`; reverse name `verification_history` |
| `request` | `ForeignKey → Request` | Required; `on_delete=RESTRICT`; reverse name `payment_verification_history` |
| `action` | `CharField(10)` | Choices: `Confirm`, `Reject` |
| `amount_received` | `DecimalField(10, 2)` | `null=True`, `blank=True` |
| `payment_date` | `DateField` | `null=True`, `blank=True` |
| `receipt_number` | `CharField(100)` | `null=True`, `blank=True` |
| `remarks` | `TextField` | `blank=True` |
| `reason` | `TextField` | `blank=True` |
| `acted_by` | `ForeignKey → User` | Required; `on_delete=RESTRICT`; reverse name `payment_verification_actions` |
| `acted_at` | `DateTimeField` | `auto_now_add=True` |

Index: (`payment`, `acted_at`). Conditional uniqueness: non-empty `receipt_number` values must be unique case-insensitively.

## Notifications (`notifications`)

### `NotificationTemplate` — table `notification_template`

| Field | Type | Options / meaning |
|---|---|---|
| `id` | `BigAutoField` | Primary key |
| `name` | `CharField(150)` | `blank=True`; default `""` |
| `description` | `TextField` | `blank=True`; default `""` |
| `event_code` | `CharField(40)` | |
| `channel` | `CharField(10)` | Choices: `EMAIL`, `IN_APP`; default `EMAIL` |
| `subject` | `CharField(200)` | `blank=True`; default `""` |
| `template_body` | `TextField` | |
| `is_active` | `BooleanField` | Default `True` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |
| `updated_at` | `DateTimeField` | `auto_now=True` |

Constraint and ordering: unique together on (`event_code`, `channel`); ordered by `event_code`, `channel`.

### `Notification` — table `notification`

| Field | Type | Options / meaning |
|---|---|---|
| `id` | `BigAutoField` | Primary key |
| `request_id` | `ForeignKey → Request` | `null=True`, `blank=True`; `db_column="request_id"`; `on_delete=SET_NULL`; reverse name `notifications` |
| `user_id` | `ForeignKey → User` | `null=True`, `blank=True`; `db_column="user_id"`; `on_delete=SET_NULL`; reverse name `notifications` |
| `channel` | `CharField(10)` | Choices: `EMAIL`, `IN_APP`; default `EMAIL` |
| `template_id` | `ForeignKey → NotificationTemplate` | `null=True`, `blank=True`; `db_column="template_id"`; `on_delete=SET_NULL`; reverse name `notifications` |
| `recipient_email` | `EmailField(255)` | `blank=True`; default `""` |
| `subject` | `CharField(200)` | `blank=True`; default `""` |
| `message` | `TextField` | `blank=True`; default `""` |
| `status` | `CharField(20)` | Choices: `QUEUED`, `SENDING`, `SENT`, `DELIVERED`, `FAILED`, `UNCERTAIN`; default `QUEUED` |
| `delivery_error` | `TextField` | `blank=True`; default `""` |
| `retry_count` | `PositiveSmallIntegerField` | Default `0` |
| `provider_message_id` | `CharField(255)` | `blank=True`; default `""` |
| `event_identifier` | `CharField(100)` | `null=True`, `blank=True`; indexed |
| `event_code` | `CharField(50)` | `blank=True`; default `""` |
| `request_number_snapshot` | `CharField(50)` | `blank=True`; default `""` |
| `is_test` | `BooleanField` | Default `False` |
| `last_attempt_at` | `DateTimeField` | `null=True`, `blank=True` |
| `sent_at` | `DateTimeField` | `null=True`, `blank=True` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |
| `updated_at` | `DateTimeField` | `auto_now=True` |

Indexes: `request_id`, `status`, `created_at`, and `event_code`. Conditional uniqueness: (`event_identifier`, `channel`) is unique for non-test notifications when `event_identifier` is neither `NULL` nor empty. Ordered newest first by `created_at`.

## Audit (`audit`)

### `AuditLog` — table `audit_log`

| Field | Type | Options / meaning |
|---|---|---|
| `id` | `BigAutoField` | Implicit primary key |
| `app_label` | `CharField(100)` | `null=True`, `blank=True` |
| `model_name` | `CharField(100)` | `null=True`, `blank=True` |
| `object_id` | `CharField(100)` | `null=True`, `blank=True` |
| `object_repr` | `CharField(200)` | `blank=True` |
| `action` | `CharField(50)` | Choices: `CREATE`, `UPDATE`, `ACTIVATE`, `DEACTIVATE`, `DELETE`, `VIEW`, `LOGIN`, `LOGOUT`, `UPLOAD`, `EXPORT`, `IMPORT` |
| `changes` | `JSONField` | Default `{}`; `blank=True` |
| `user_id` | `CharField(100)` | `null=True`, `blank=True`; stored identifier, not a foreign key |
| `user_name` | `CharField(200)` | `null=True`, `blank=True` |
| `ip_address` | `GenericIPAddressField` | `null=True`, `blank=True` |
| `user_agent` | `TextField` | `blank=True` |
| `request_path` | `CharField(500)` | `blank=True` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |

Indexes: `created_at`, `model_name`, `user_id`, and `action`. Ordered newest first by `created_at`.

## Relationship Summary

| Source | Relationship | Target | Delete behavior |
|---|---|---|---|
| `User.role_id` | many-to-one | `Role` | `RESTRICT` |
| `User.service_department_id` | many-to-one, optional | `ServiceDepartment` | `RESTRICT` |
| `ServiceDepartment.hod_user_id` | many-to-one, optional | `User` | `RESTRICT` |
| `Student.user_id` | one-to-one | `User` | `RESTRICT` |
| `Student.academic_department_id` | many-to-one | `AcademicDepartment` | `RESTRICT` |
| `Service.service_department_id` | many-to-one | `ServiceDepartment` | `RESTRICT` |
| `ServiceField.service_id` | many-to-one | `Service` | `CASCADE` |
| `ServiceDocument.service_id` | many-to-one | `Service` | `CASCADE` |
| `Request.student_id` | many-to-one | `Student` | `RESTRICT` |
| `Request.service_id` | many-to-one | `Service` | `RESTRICT` |
| `Request.current_step_id` | many-to-one, optional | `WorkflowStep` | `RESTRICT` |
| `RequestFieldValue.request_id` | many-to-one | `Request` | `CASCADE` |
| `RequestFieldValue.field_id` | many-to-one | `ServiceField` | `RESTRICT` |
| `Document.request_id` | many-to-one | `Request` | `CASCADE` |
| `Document.service_document_id` | many-to-one | `ServiceDocument` | `RESTRICT` |
| `WorkflowStep.service_id` | many-to-one | `Service` | `CASCADE` |
| `WorkflowStep.responsible_role_id` | many-to-one | `Role` | `RESTRICT` |
| `WorkflowHistory.request_id` | many-to-one | `Request` | `CASCADE` |
| `WorkflowHistory.step_id` | many-to-one, optional | `WorkflowStep` | `RESTRICT` |
| `WorkflowHistory.action_by_user_id` | many-to-one | `User` | `RESTRICT` |
| `Payment.request_id` | one-to-one | `Request` | `RESTRICT` |
| `Payment.verified_by` | many-to-one, optional | `User` | `SET_NULL` |
| `PaymentVerificationLog.payment` | many-to-one | `Payment` | `RESTRICT` |
| `PaymentVerificationLog.request` | many-to-one | `Request` | `RESTRICT` |
| `PaymentVerificationLog.acted_by` | many-to-one | `User` | `RESTRICT` |
| `Notification.request_id` | many-to-one, optional | `Request` | `SET_NULL` |
| `Notification.user_id` | many-to-one, optional | `User` | `SET_NULL` |
| `Notification.template_id` | many-to-one, optional | `NotificationTemplate` | `SET_NULL` |

`RESTRICT` prevents deletion while referenced; `CASCADE` deletes related rows; `SET_NULL` preserves the referencing row and clears its nullable FK. A many-to-one relation permits multiple source rows to reference one target.

## Scope Notes

- The application defines 17 model classes in the apps listed above. The `reports`, `profile`, `department_queue`, and `dashboard` apps currently declare no models.
- Django framework-owned models (for example auth permissions, sessions, and token blacklist tables) are not included.
- `apps.students.fields.EncryptedTextField` is a custom `TextField` subclass, but no current model field uses it.
