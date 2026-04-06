import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../main.dart';
import '../utils/routes.dart';
import '../widgets/summary_card.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final totalSpent = state.transactions.fold<double>(0, (sum, item) => sum + item.amount);
    final totalBudget = state.budgets.fold<double>(0, (sum, item) => sum + item.limit);
    final spentBudget = state.budgets.fold<double>(0, (sum, item) => sum + item.spent);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Dashboard'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => Navigator.pushNamed(context, Routes.settings),
          )
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(vertical: 16),
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  Expanded(
                    child: Card(
                      elevation: 2,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Welcome, ${state.user?.name ?? 'Manager'}', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                            const SizedBox(height: 8),
                            Text('Last synced ${DateFormat.yMMMd().format(DateTime.now())}', style: const TextStyle(color: Colors.black54)),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Column(
                children: [
                  SummaryCard(title: 'Transactions', value: state.transactions.length.toString(), subtitle: 'Recent entries recorded'),
                  SummaryCard(title: 'Budgets', value: state.budgets.length.toString(), subtitle: '$spentBudget of $totalBudget tracked'),
                  SummaryCard(title: 'Reports', value: state.reports.length.toString(), subtitle: 'Project updates available'),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Column(
                children: [
                  _NavigationTile(
                    icon: Icons.account_balance_wallet,
                    label: 'Manage Transactions',
                    destination: Routes.transactions,
                  ),
                  _NavigationTile(
                    icon: Icons.attach_money,
                    label: 'Review Budgets',
                    destination: Routes.budgets,
                  ),
                  _NavigationTile(
                    icon: Icons.insert_chart,
                    label: 'View Project Reports',
                    destination: Routes.reports,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NavigationTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final String destination;

  const _NavigationTile({
    Key? key,
    required this.icon,
    required this.label,
    required this.destination,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      child: ListTile(
        leading: Icon(icon, color: Theme.of(context).colorScheme.primary),
        title: Text(label),
        trailing: const Icon(Icons.arrow_forward_ios, size: 18),
        onTap: () => Navigator.pushNamed(context, destination),
      ),
    );
  }
}
