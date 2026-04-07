import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../main.dart';
import '../models/budget.dart';
import '../widgets/budget_tile.dart';

class BudgetsScreen extends StatefulWidget {
  const BudgetsScreen({Key? key}) : super(key: key);

  @override
  State<BudgetsScreen> createState() => _BudgetsScreenState();
}

class _BudgetsScreenState extends State<BudgetsScreen> {
  final List<String> currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD'];

  void _showAddBudgetDialog() {
    final formKey = GlobalKey<FormState>();
    final nameController = TextEditingController();
    final limitController = TextEditingController();
    String selectedCurrency = 'USD';

    showDialog<void>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setState) {
            return AlertDialog(
              title: const Text('Add Budget'),
              content: Form(
                key: formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextFormField(
                      controller: nameController,
                      decoration: const InputDecoration(labelText: 'Budget name'),
                      validator: (value) => value == null || value.isEmpty ? 'Enter budget name' : null,
                    ),
                    TextFormField(
                      controller: limitController,
                      decoration: const InputDecoration(labelText: 'Budget limit'),
                      keyboardType: TextInputType.number,
                      validator: (value) {
                        if (value == null || value.isEmpty) return 'Enter a number';
                        return double.tryParse(value) == null ? 'Enter a valid amount' : null;
                      },
                    ),
                    DropdownButtonFormField<String>(
                      value: selectedCurrency,
                      decoration: const InputDecoration(labelText: 'Currency'),
                      items: currencies.map((currency) {
                        return DropdownMenuItem<String>(
                          value: currency,
                          child: Text(currency),
                        );
                      }).toList(),
                      onChanged: (value) {
                        setState(() {
                          selectedCurrency = value!;
                        });
                      },
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
                ElevatedButton(
                  onPressed: () {
                    if (formKey.currentState!.validate()) {
                      final budget = Budget(
                        id: DateTime.now().microsecondsSinceEpoch.toString(),
                        name: nameController.text,
                        limit: double.parse(limitController.text),
                        spent: 0,
                        currency: selectedCurrency,
                      );
                      context.read<AppState>().addBudget(budget);
                      Navigator.of(context).pop();
                    }
                  },
                  child: const Text('Add'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final budgets = context.watch<AppState>().budgets;
    return Scaffold(
      appBar: AppBar(title: const Text('Budgets')),
      body: budgets.isEmpty
          ? const Center(child: Text('No budgets available. Add one to track spending.'))
          : ListView.builder(
              padding: const EdgeInsets.symmetric(vertical: 16),
              itemCount: budgets.length,
              itemBuilder: (context, index) => BudgetTile(budget: budgets[index]),
            ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showAddBudgetDialog,
        child: const Icon(Icons.add_chart),
      ),
    );
  }
}
