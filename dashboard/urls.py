from django.urls import path
from . import views

app_name = 'dashboard'
urlpatterns = [
    path('', views.index, name='index'),
    path('api/startups/', views.api_startups, name='api_startups'),
    path(
        'api/startups/by-slug/<slug:slug>/',
        views.api_startup_by_slug,
        name='api_startup_by_slug',
    ),
    path(
        'api/startups/by-slug/<slug:slug>/reports/',
        views.api_startup_reports_by_slug,
        name='api_startup_reports_by_slug',
    ),
    path('api/reports/<int:id>/', views.api_report_by_id, name='api_report_by_id'),
    path('startup/<int:pk>/', views.startup_detail, name='startup_detail'),
    path('report/<int:pk>/', views.report_detail, name='report_detail'),
]
