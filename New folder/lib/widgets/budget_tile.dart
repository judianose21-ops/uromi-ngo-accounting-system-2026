import 'package:flutter/material.dart';
import '../models/budget.dart';

class BudgetTile extends StatelessWidget {
  final Budget budget;

  const BudgetTile({Key? key, required this.budget}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final percent = budget.limit <= 0 ? 0.0 : (budget.spent / budget.limit).clamp(0.0, 1.0);
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(budget.name, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                Text('\$${budget.spent.toStringAsFixed(0)} / ${budget.limit.toStringAsFixed(0)}', style: const TextStyle(fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 12),
            LinearProgressIndicator(value: percent, minHeight: 8),
            const SizedBox(height: 8),
            Text('${(percent * 100).toStringAsFixed(0)}% used', style: const TextStyle(color: Colors.black54)),
          ],
        ),
      ),
    );
  }
}

