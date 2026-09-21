from rest_framework.exceptions import APIException


class BarcodeConflict(APIException):
    """TZ v2 8.5: a barcode already assigned to another product -> 409."""

    status_code = 409
    default_detail = "Bu kod boshqa mahsulotga biriktirilgan."
    default_code = "barcode_conflict"


class ProductInUse(APIException):
    """A product that has been sold keeps its receipts — it can only be archived."""

    status_code = 409
    default_detail = "Bu mahsulot sotilgan, o'chirib bo'lmaydi. Uni arxivlang."
    default_code = "product_in_use"


class BatchQtyTooLow(APIException):
    """Correcting a batch's quantity below what already left it is impossible."""

    status_code = 400
    default_code = "batch_qty_too_low"

    def __init__(self, minimum):
        super().__init__(
            f"Bu partiyadan {minimum} allaqachon chiqqan, undan kam bo'lishi mumkin emas."
        )
