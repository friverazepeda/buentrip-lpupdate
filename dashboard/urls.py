from django.urls import path
from . import views

app_name = 'dashboard'
urlpatterns = [
    path('', views.index, name='index'),
    path('api/startups/', views.api_startups, name='api_startups'),
    path('startup/<int:pk>/', views.startup_detail, name='startup_detail'),
    path('report/<int:pk>/', views.report_detail, name='report_detail'),
]
