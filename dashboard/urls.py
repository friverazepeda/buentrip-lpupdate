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
    path('api/vehicles/<int:id>/generate-report/', views.api_generate_vehicle_report, name='api_generate_vehicle_report'),
    path('api/lp-reports/', views.api_lp_reports, name='api_lp_reports'),
    path('api/lp-reports/<int:id>/', views.api_lp_report_update, name='api_lp_report_update'),
    path('startup/<int:pk>/', views.startup_detail, name='startup_detail'),
    path('report/<int:pk>/', views.report_detail, name='report_detail'),
]
