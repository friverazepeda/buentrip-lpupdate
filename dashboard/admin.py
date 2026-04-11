from django.contrib import admin
from .models import Firm, Vehicle, Startup, VehicleStartup, StartupUpdate, StartupMetric, QuarterlyLPReport, StartupUpdateManager

class StartupMetricInline(admin.TabularInline):
    model = StartupMetric
    extra = 0

class StartupUpdateInline(admin.TabularInline):
    model = StartupUpdate
    extra = 0
    fields = ('vehicle', 'quarter', 'year', 'period_label')
    show_change_link = True

class StartupUpdateManagerAdmin(admin.ModelAdmin):
    list_display = ('name', 'sector', 'business_model', 'update_count')
    search_fields = ('name',)
    inlines = [StartupUpdateInline]
    
    # Hide the default Startup fields so they only focus on editing updates
    fields = ('name',)
    readonly_fields = ('name',)
    
    def update_count(self, obj):
        return obj.updates.count()
    update_count.short_description = 'Parsed Updates'

class StartupUpdateAdmin(admin.ModelAdmin):
    list_display = ('startup', 'vehicle', 'quarter', 'year', 'period_label')
    list_filter = ('startup', 'vehicle', 'year', 'quarter')
    inlines = [StartupMetricInline]

class QuarterlyLPReportAdmin(admin.ModelAdmin):
    list_display = ('vehicle', 'quarter', 'year')
    list_filter = ('vehicle', 'year', 'quarter')

class VehicleStartupInline(admin.TabularInline):
    model = VehicleStartup
    extra = 1

class VehicleAdmin(admin.ModelAdmin):
    list_display = ('name', 'firm', 'legal_structure')
    inlines = [VehicleStartupInline]

class StartupAdmin(admin.ModelAdmin):
    list_display = ('name', 'sector', 'business_model', 'get_vehicles')
    search_fields = ('name',)
    
    def get_vehicles(self, obj):
        return ", ".join([v.vehicle.name for v in obj.vehiclestartup_set.all()])
    get_vehicles.short_description = 'Vehicles'

admin.site.register(Firm)
admin.site.register(Vehicle, VehicleAdmin)
admin.site.register(Startup, StartupAdmin)
admin.site.register(VehicleStartup)
admin.site.register(StartupUpdateManager, StartupUpdateManagerAdmin)
admin.site.register(StartupUpdate, StartupUpdateAdmin)
admin.site.register(QuarterlyLPReport, QuarterlyLPReportAdmin)

# Custom admin ordering
def get_app_list(self, request, app_label=None):
    app_dict = self._build_app_dict(request, app_label)
    if not app_dict:
        return []
    
    app_list = sorted(app_dict.values(), key=lambda x: x['name'].lower())
    
    custom_order = {
        'Startups': 1,
        'Updates by Startup': 2,
        'All raw updates': 3,
        'Quarterly lp reports': 4,
        'Vehicles': 5,
        'Vehicle Companies': 6,
        'Firms': 7
    }
    
    for app in app_list:
        if app['app_label'] == 'dashboard':
            # Keep StartupUpdate in the main list, but rename it for clarity
            for m in app['models']:
                if m['object_name'] == 'StartupUpdate':
                    m['name'] = 'All raw updates'
                elif m['object_name'] == 'StartupUpdateManager':
                    m['name'] = 'Updates by Startup'
                    
            app['models'].sort(key=lambda x: custom_order.get(x['name'], 999))
        else:
            app['models'].sort(key=lambda x: x['name'])
    
    return app_list

admin.AdminSite.get_app_list = get_app_list
