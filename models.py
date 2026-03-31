from django.db import models

class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('donation', 'Donation'),
        ('expense', 'Expense'),
        ('income', 'Income'),
        ('transfer', 'Transfer'),
    ]

    date = models.DateField()
    pv_number = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField()
    transaction_type = models.CharField(max_length=50, choices=TRANSACTION_TYPES)
    gross_amount = models.DecimalField(max_digits=15, decimal_places=2)

    month = models.CharField(max_length=20, blank=True, null=True)

    project = models.ForeignKey('Project', on_delete=models.SET_NULL, blank=True, null=True)
    vendor_tin = models.CharField(max_length=100, blank=True, null=True)
    vendor_account_details = models.CharField(max_length=255, blank=True, null=True)

    main_account = models.ForeignKey('ChartOfAccount', related_name='main_transactions', on_delete=models.SET_NULL, null=True)
    sub_account = models.ForeignKey('ChartOfAccount', related_name='sub_transactions', on_delete=models.SET_NULL, blank=True, null=True)

    deduct_wht = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.date} - {self.description}"