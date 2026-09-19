from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """20 per page by default; a screen that needs a bigger chunk (the sale
    search, pickers) can ask with ?page_size=, capped so one request can't
    pull the whole catalogue."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
