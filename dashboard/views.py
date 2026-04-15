from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.utils.text import slugify
from .models import Startup, StartupUpdate, Vehicle

def index(request):
    startups = Startup.objects.all().order_by('name')
    vehicles = Vehicle.objects.all().order_by('name')
    return render(request, 'dashboard/index.html', {'startups': startups, 'vehicles': vehicles})

def startup_detail(request, pk):
    startup = get_object_or_404(Startup, pk=pk)
    reports = StartupUpdate.objects.filter(startup=startup).order_by('-year', '-quarter')
    return render(request, 'dashboard/startup_detail.html', {'startup': startup, 'reports': reports})

def report_detail(request, pk):
    report = get_object_or_404(StartupUpdate, pk=pk)
    return render(request, 'dashboard/report_detail.html', {'report': report})


def api_startups(request):
    startups = Startup.objects.all().order_by('name').values('id', 'name')
    payload = [
        {
            'id': row['id'],
            'name': row['name'],
            'slug': slugify(row['name']),
        }
        for row in startups
    ]
    return JsonResponse(payload, safe=False)


def api_startup_by_slug(request, slug):
    for row in Startup.objects.all().order_by('name').values('id', 'name'):
        if slugify(row['name']) == slug:
            return JsonResponse(
                {
                    'id': row['id'],
                    'name': row['name'],
                    'slug': slugify(row['name']),
                }
            )
    return JsonResponse({'detail': 'Not found.'}, status=404)


def api_startup_reports_by_slug(request, slug):
    startup_row = None
    for row in Startup.objects.all().order_by('name').values('id', 'name'):
        if slugify(row['name']) == slug:
            startup_row = row
            break

    if startup_row is None:
        return JsonResponse({'detail': 'Not found.'}, status=404)

    reports = StartupUpdate.objects.filter(startup_id=startup_row['id']).order_by('-year', '-quarter').values(
        'id',
        'period_label',
        'quarter',
        'year',
        'received_at',
    )
    payload = [
        {
            'id': report['id'],
            'period_label': report['period_label'],
            'quarter': report['quarter'],
            'year': report['year'],
            'received_at': report['received_at'].isoformat() if report['received_at'] else None,
        }
        for report in reports
    ]
    return JsonResponse(payload, safe=False)
