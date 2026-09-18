from rest_framework.exceptions import APIException


class BarcodeConflict(APIException):
    """TZ v2 8.5: a barcode already assigned to another product -> 409."""

    status_code = 409
    default_detail = "Bu kod boshqa mahsulotga biriktirilgan."
    default_code = "barcode_conflict"
