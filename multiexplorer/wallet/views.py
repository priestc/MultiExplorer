from django.template.response import TemplateResponse

# Create your views here.

def home(request):
    return TemplateResponse(request, "wallet_home.html", {})
