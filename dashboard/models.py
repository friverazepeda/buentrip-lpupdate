from django.db import models

class Firm(models.Model):
    name = models.CharField(max_length=255)
    
    def __str__(self):
        return self.name

class Vehicle(models.Model):
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name='vehicles')
    name = models.CharField(max_length=255)
    legal_structure = models.CharField(max_length=255, blank=True, null=True)
    total_capital_raised = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    invested_capital = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    moic = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    irr = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    
    def __str__(self):
        return self.name

class Startup(models.Model):
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True, null=True)
    sector = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    business_model = models.CharField(max_length=255, blank=True, null=True)
    sub_segment_niche = models.CharField(max_length=255, blank=True, null=True)
    
    class Meta:
        verbose_name_plural = 'Startups'
        ordering = ['name']
    
    def __str__(self):
        return self.name

class VehicleStartup(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    startup = models.ForeignKey(Startup, on_delete=models.CASCADE)
    thesis = models.TextField(blank=True, null=True)
    role_of_fund = models.TextField(blank=True, null=True)
    exit_strategy = models.CharField(max_length=255, blank=True, null=True)
    stage_of_investment = models.CharField(max_length=255, blank=True, null=True)
    date_of_investment = models.DateField(blank=True, null=True)
    
    class Meta:
        verbose_name_plural = 'Vehicle Companies'
        unique_together = ('vehicle', 'startup')
        
    def __str__(self):
        return f"{self.vehicle.name} -> {self.startup.name}"

class StartupUpdate(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='startup_updates')
    startup = models.ForeignKey(Startup, on_delete=models.CASCADE, related_name='updates', blank=True, null=True)
    quarter = models.CharField(max_length=10) # e.g. Q4
    year = models.IntegerField()
    
    # Text fields for narrative
    opportunities_and_challenges = models.TextField(blank=True, null=True)
    fundraising_updates = models.TextField(blank=True, null=True)
    
    highlights = models.TextField(blank=True, null=True)
    risks = models.TextField(blank=True, null=True)
    asks = models.TextField(blank=True, null=True)
    people = models.TextField(blank=True, null=True)
    
    period_label = models.CharField(max_length=255, blank=True, null=True)
    received_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        unique_together = ('vehicle', 'startup', 'quarter', 'year')
        
    def __str__(self):
        if self.startup:
            return f"{self.startup.name} - {self.vehicle.name} ({self.quarter} {self.year})"
        return f"{self.vehicle.name} ({self.quarter} {self.year})"

class StartupMetric(models.Model):
    update = models.ForeignKey(StartupUpdate, on_delete=models.CASCADE, related_name='metrics')
    name = models.CharField(max_length=255) # e.g. "Total ARR EoQ"
    value = models.CharField(max_length=255) # e.g. "$2.6M"
    change = models.CharField(max_length=255, blank=True, null=True) # e.g. "+15.4% QoQ"
    
    def __str__(self):
        return f"{self.name}: {self.value}"

class QuarterlyLPReport(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='lp_reports')
    quarter = models.CharField(max_length=10) # e.g. Q4
    year = models.IntegerField()
    
    # Fund level narratives
    summary_of_progress = models.TextField(blank=True, null=True)
    new_investments = models.TextField(blank=True, null=True)
    exits_and_distributions = models.TextField(blank=True, null=True)
    governance_and_legal = models.TextField(blank=True, null=True)
    significant_developments = models.TextField(blank=True, null=True)
    asks_by_portfolio_companies = models.TextField(blank=True, null=True)
    esg_updates = models.TextField(blank=True, null=True)
    
    class Meta:
        unique_together = ('vehicle', 'quarter', 'year')
        
    def __str__(self):
        return f"{self.vehicle.name} LP Report ({self.quarter} {self.year})"

class StartupUpdateManager(Startup):
    class Meta:
        proxy = True
        verbose_name = 'Startup Update'
        verbose_name_plural = 'Startup Updates'

