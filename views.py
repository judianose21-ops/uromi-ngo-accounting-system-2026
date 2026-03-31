from datetime import datetime
from django.shortcuts import render, redirect
from .models import Transaction, Project, ChartOfAccount

def add_transaction(request):
    if request.method == 'POST':
        date = request.POST.get('date')
        pv_number = request.POST.get('pv_number')
        description = request.POST.get('description')
        transaction_type = request.POST.get('transaction_type')
        gross_amount = request.POST.get('gross_amount')
        month = request.POST.get('month')
        project_id = request.POST.get('project')
        vendor_tin = request.POST.get('vendor_tin')
        vendor_account_details = request.POST.get('vendor_account_details')
        main_account_id = request.POST.get('main_account')
        sub_account_id = request.POST.get('sub_account')
        deduct_wht = True if request.POST.get('deduct_wht') == 'on' else False

        project = Project.objects.filter(id=project_id).first() if project_id else None
        main_account = ChartOfAccount.objects.filter(id=main_account_id).first()
        sub_account = ChartOfAccount.objects.filter(id=sub_account_id).first() if sub_account_id else None

        # Auto month from date if empty
        if not month and date:
            parsed_date = datetime.strptime(date, '%Y-%m-%d')
            month = parsed_date.strftime('%B %Y')

        Transaction.objects.create(
            date=date,
            pv_number=pv_number,
            description=description,
            transaction_type=transaction_type,
            gross_amount=gross_amount,
            month=month,
            project=project,
            vendor_tin=vendor_tin,
            vendor_account_details=vendor_account_details,
            main_account=main_account,
            sub_account=sub_account,
            deduct_wht=deduct_wht
        )

        return redirect('transaction_list')

    projects = Project.objects.all()
    main_accounts = ChartOfAccount.objects.filter(parent__isnull=True)
    return render(request, 'add_transaction.html', {
        'projects': projects,
        'main_accounts': main_accounts
    })
def transaction_list(request):
    transactions = Transaction.objects.select_related(
        'project', 'main_account', 'sub_account'
    ).order_by('-date', '-id')

    return render(request, 'transaction_list.html', {
        'transactions': transactions
    })