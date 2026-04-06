import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:ngo_accounting_app/screens/budgets_screen.dart';
import 'package:ngo_accounting_app/screens/dashboard_screen.dart';
import 'package:ngo_accounting_app/screens/login_screen.dart';
import 'package:ngo_accounting_app/screens/reports_screen.dart';
import 'package:ngo_accounting_app/screens/settings_screen.dart';
import 'package:ngo_accounting_app/screens/transactions_screen.dart';
import 'package:ngo_accounting_app/utils/app_theme.dart';
import 'package:ngo_accounting_app/utils/routes.dart';
import 'models/budget.dart';
import 'models/ngo_transaction.dart';
import 'models/project_report.dart';
import 'models/user_profile.dart';
import 'services/auth_service.dart';
import 'services/data_service.dart';
import 'services/api_service.dart';

void main() {
  runApp(const NGOAccountingApp());
}

class NGOAccountingApp extends StatelessWidget {
  const NGOAccountingApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider<AppState>(
      create: (_) => AppState(),
      child: Consumer<AppState>(
        builder: (context, state, child) {
          return MaterialApp(
            title: 'NGO Accounting',
            theme: AppTheme.lightTheme,
            initialRoute: state.isAuthenticated ? Routes.dashboard : Routes.login,
            routes: {
              Routes.login: (_) => const LoginScreen(),
              Routes.dashboard: (_) => const DashboardScreen(),
              Routes.transactions: (_) => const TransactionsScreen(),
              Routes.budgets: (_) => const BudgetsScreen(),
              Routes.reports: (_) => const ReportsScreen(),
              Routes.settings: (_) => const SettingsScreen(),
            },
          );
        },
      ),
    );
  }
}

class AppState extends ChangeNotifier {
  UserProfile? _user;
  List<NGOTransaction> _transactions = [];
  List<Budget> _budgets = [];
  List<ProjectReport> _reports = [];
  bool _isLoading = true;

  UserProfile? get user => _user;
  bool get isAuthenticated => _user != null;
  List<NGOTransaction> get transactions => List.unmodifiable(_transactions);
  List<Budget> get budgets => List.unmodifiable(_budgets);
  List<ProjectReport> get reports => List.unmodifiable(_reports);
  bool get isLoading => _isLoading;

  AppState() {
    _loadData();
  }

  Future<void> _loadData() async {
    _transactions = await DataService.getTransactions();
    _budgets = await DataService.getBudgets();
    _reports = await DataService.getReports();
    _isLoading = false;
    notifyListeners();
  }

  Future<bool> signIn(String email, String password) async {
    final foundUser = await AuthService.signIn(email, password);
    if (foundUser != null) {
      _user = foundUser;
      notifyListeners();
      return true;
    }
    return false;
  }

  void signOut() {
    _user = null;
    notifyListeners();
  }

  Future<void> addTransaction(NGOTransaction transaction) async {
    await DataService.addTransaction(transaction);
    _transactions.insert(0, transaction);
    // Sync to API
    await ApiService.syncTransaction(transaction);
    notifyListeners();
  }

  Future<void> addBudget(Budget budget) async {
    await DataService.addBudget(budget);
    _budgets.insert(0, budget);
    notifyListeners();
  }

  Future<void> updateBudgetSpent(String budgetId, double amount) async {
    final index = _budgets.indexWhere((item) => item.id == budgetId);
    if (index >= 0) {
      final newSpent = _budgets[index].spent + amount;
      await DataService.updateBudgetSpent(budgetId, newSpent);
      _budgets[index] = _budgets[index].copyWith(spent: newSpent);
      notifyListeners();
    }
  }

  Future<void> addReport(ProjectReport report) async {
    await DataService.addReport(report);
    _reports.insert(0, report);
    notifyListeners();
  }

  Future<void> syncData() async {
    final apiTransactions = await ApiService.fetchTransactions();
    for (var txn in apiTransactions) {
      if (!_transactions.any((t) => t.id == txn.id)) {
        await addTransaction(txn);
      }
    }
    notifyListeners();
  }
}
