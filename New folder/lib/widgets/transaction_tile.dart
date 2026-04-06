import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'dart:io';
import '../models/ngo_transaction.dart';

class TransactionTile extends StatelessWidget {
  final NGOTransaction transaction;

  const TransactionTile({Key? key, required this.transaction}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final dateLabel = DateFormat.yMMMd().format(transaction.date);
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: ListTile(
        leading: transaction.imagePath != null
            ? Image.file(File(transaction.imagePath!), width: 50, height: 50, fit: BoxFit.cover)
            : const Icon(Icons.receipt),
        title: Text(transaction.description),
        subtitle: Text('${transaction.project} • ${transaction.category}'),
        trailing: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text('\$${transaction.amount.toStringAsFixed(2)}', style: const TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            Text(dateLabel, style: const TextStyle(fontSize: 12, color: Colors.black54)),
          ],
        ),
      ),
    );
  }
}
