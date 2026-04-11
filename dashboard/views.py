from django.shortcuts import render, get_object_or_404
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
