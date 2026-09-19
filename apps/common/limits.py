"""Upper bounds for numbers and text coming from clients.

Without them a request such as ``qty=99999999999`` or ``amount=10**30`` slips
past validation and blows up in the database (BigInteger overflow -> HTTP 500),
and a megabyte-long ``note`` is stored as is. They are far above anything a
real shop needs, so they never get in an honest user's way."""

from decimal import Decimal

MAX_PRICE = 10**10  # 10 milliard so'm per unit
MAX_DEBT = 10**12  # one debt / payment entry
MAX_QTY = Decimal("1000000")  # units, kg or litres in one line
MAX_LINES = 100  # lines in one sale
MAX_NOTE = 500  # characters in a free-text note
MAX_PASSWORD = 128
