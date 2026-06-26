from django.urls import path
from . import views

urlpatterns = [
    path('sales-order/', views.sales_order_webhook, name='sales_order_webhook'),
]
