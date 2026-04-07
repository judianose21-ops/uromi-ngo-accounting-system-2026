import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../main.dart';
import '../widgets/report_tile.dart';
import '../models/project_report.dart';

class ReportsScreen extends StatefulWidget {
  const ReportsScreen({Key? key}) : super(key: key);

  @override
  State<ReportsScreen> createState() => _ReportsScreenState();
}

class _ReportsScreenState extends State<ReportsScreen> {
  final List<String> currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD'];

  void _showAddReportDialog() {
    final formKey = GlobalKey<FormState>();
    final titleController = TextEditingController();
    final descriptionController = TextEditingController();
    final progressController = TextEditingController();
    final amountSpentController = TextEditingController();
    String selectedCurrency = 'USD';

    showDialog<void>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setState) {
            return AlertDialog(
              title: const Text('Add Project Report'),
              content: Form(
                key: formKey,
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      TextFormField(
                        controller: titleController,
                        decoration: const InputDecoration(labelText: 'Title'),
                        validator: (value) => value == null || value.isEmpty ? 'Enter title' : null,
                      ),
                      TextFormField(
                        controller: descriptionController,
                        decoration: const InputDecoration(labelText: 'Description'),
                        validator: (value) => value == null || value.isEmpty ? 'Enter description' : null,
                      ),
                      TextFormField(
                        controller: progressController,
                        decoration: const InputDecoration(labelText: 'Progress (0-1)'),
                        keyboardType: TextInputType.number,
                        validator: (value) {
                          if (value == null || value.isEmpty) return 'Enter progress';
                          final parsed = double.tryParse(value);
                          if (parsed == null) return 'Enter a valid number';
                          if (parsed < 0 || parsed > 1) return 'Enter a value between 0 and 1';
                          return null;
                        },
                      ),
                      TextFormField(
                        controller: amountSpentController,
                        decoration: const InputDecoration(labelText: 'Amount Spent'),
                        keyboardType: TextInputType.number,
                        validator: (value) {
                          if (value == null || value.isEmpty) return 'Enter amount';
                          return double.tryParse(value) == null ? 'Enter a valid number' : null;
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
              ),
              actions: [
                TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
                ElevatedButton(
                  onPressed: () {
                    if (formKey.currentState!.validate()) {
                      final report = ProjectReport(
                        id: DateTime.now().microsecondsSinceEpoch.toString(),
                        title: titleController.text,
                        description: descriptionController.text,
                        progress: double.parse(progressController.text),
                        amountSpent: double.parse(amountSpentController.text),
                        updatedAt: DateTime.now(),
                        currency: selectedCurrency,
                      );
                      context.read<AppState>().addReport(report);
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
    final reports = context.watch<AppState>().reports;

    return Scaffold(
      appBar: AppBar(title: const Text('Project Reports')),
      body: reports.isEmpty
          ? const Center(child: Text('No reports yet. Create project summaries to start tracking project progress.'))
          : ListView.builder(
              padding: const EdgeInsets.symmetric(vertical: 16),
              itemCount: reports.length,
              itemBuilder: (context, index) => ReportTile(report: reports[index]),
            ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showAddReportDialog,
        child: const Icon(Icons.add),
      ),
    );
  }
}

