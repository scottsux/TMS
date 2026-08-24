from enum import Enum


class ParcelStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    IN_TRANSIT = "IN_TRANSIT"
    ARRIVED = "ARRIVED"
    PACK_REQUESTED = "PACK_REQUESTED"
    PACKED = "PACKED"
    REJECTED = "REJECTED"


class OrderStatus(str, Enum):
    DRAFT = "DRAFT"
    READY_TO_PACK = "READY_TO_PACK"
    PACKING = "PACKING"
    READY_TO_SHIP = "READY_TO_SHIP"
    COMPLETED = "COMPLETED"


class TaskStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


class ExceptionType(str, Enum):
    CUSTOMER_CANCEL = "CUSTOMER_CANCEL"
    ADDRESS_ERROR = "ADDRESS_ERROR"
    DAMAGED = "DAMAGED"
    PROHIBITED = "PROHIBITED"
    PRICE_DISPUTE = "PRICE_DISPUTE"


class ExceptionStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class UserRole(str, Enum):
    customer = "customer"
    staff = "staff"
    operator = "operator"
