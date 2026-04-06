import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import '../main.dart';
import '../models/ngo_transaction.dart';
import '../widgets/transaction_tile.dart';

class TransactionsScreen extends StatefulWidget {
  const TransactionsScreen({Key? key}) : super(key: key);

  @override
  State<TransactionsScreen> createState() => _TransactionsScreenState();
}

class _TransactionsScreenState extends State<TransactionsScreen> {
  final ImagePicker _picker = ImagePicker();

  void _showAddTransactionDialog() {
    final formKey = GlobalKey<FormState>();
    final descriptionController = TextEditingController();
    final amountController = TextEditingController();
    final projectController = TextEditingController();
    final categoryController = TextEditingController();
    String? imagePath;

    showDialog<void>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Add Transaction'),
          content: Form(
            key: formKey,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextFormField(
                    controller: descriptionController,
                    decoration: const InputDecoration(labelText: 'Description'),
                    validator: (value) => value == null || value.isEmpty ? 'Enter description' : null,
                  ),
                  TextFormField(
                    controller: amountController,
                    decoration: const InputDecoration(labelText: 'Amount'),
                    keyboardType: TextInputType.number,
                    validator: (value) {
                      if (value == null || value.isEmpty) return 'Enter amount';
                      final parsed = double.tryParse(value);
                      return parsed == null ? 'Enter a valid number' : null;
                    },
                  ),
                  TextFormField(
                    controller: categoryController,
                    decoration: const InputDecoration(labelText: 'Category'),
                    validator: (value) => value == null || value.isEmpty ? 'Enter category' : null,
                  ),
                  TextFormField(
                    controller: projectController,
                    decoration: const InputDecoration(labelText: 'Project'),
                    validator: (value) => value == null || value.isEmpty ? 'Enter project name' : null,
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: () async {
                      final pickedFile = await _picker.pickImage(source: ImageSource.camera);
                      if (pickedFile != null) {
                        imagePath = pickedFile.path;
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Image attached')),
                        );
                      }
                    },
                    icon: const Icon(Icons.camera),
                    label: const Text('Attach Receipt'),
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
                  final amount = double.parse(amountController.text);
                  final transaction = NGOTransaction(
                    id: DateTime.now().microsecondsSinceEpoch.toString(),
                    description: descriptionController.text,
                    amount: amount,
                    date: DateTime.now(),
                    category: categoryController.text,
                    project: projectController.text,
                    imagePath: imagePath,
                  );
                  context.read<AppState>().addTransaction(transaction);
                  Navigator.of(context).pop();
                }
              },
              child: const Text('Save'),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    return Scaffold(
      appBar: AppBar(
        title: const Text('Transactions'),
        actions: [
          IconButton(
            icon: const Icon(Icons.sync),
            onPressed: () async {
              await state.syncData();
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Data synced')),
              );
            },
          ),
        ],
      ),
      body: state.isLoading
          ? const Center(child: CircularProgressIndicator())
          : state.transactions.isEmpty
              ? const Center(child: Text('No transactions yet. Add one using the button below.'))
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  itemCount: state.transactions.length,
                  itemBuilder: (context, index) => TransactionTile(transaction: state.transactions[index]),
                ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showAddTransactionDialog,
        child: const Icon(Icons.add),
      ),
    );
  }
}
