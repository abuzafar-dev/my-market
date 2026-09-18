from django.contrib import admin
from django.contrib.auth.models import Group
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

admin.site.site_header = "My Market"
admin.site.site_title = "My Market"
admin.site.index_title = "Boshqaruv paneli"

# These are Django/JWT internals, not anything a shop owner ever needs to
# open — Group-based permissions aren't used (roles live on User.role
# instead), and outstanding/blacklisted tokens are pure session bookkeeping.
# Hiding them keeps the sidebar to only what's actually relevant day to day.
for _model in (Group, BlacklistedToken, OutstandingToken):
    try:
        admin.site.unregister(_model)
    except admin.sites.NotRegistered:
        pass
