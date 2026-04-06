import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/project_report.dart';

class ReportTile extends StatelessWidget {
  final ProjectReport report;

  const ReportTile({Key? key, required this.report}) : super(key: key);

  @override
  Widget build(BuildContext context) {
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
                Text(report.title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                Text('${(report.progress * 100).toStringAsFixed(0)}%', style: const TextStyle(color: Colors.green, fontWeight: FontWeight.bold)),
              ],
            ),
            const SizedBox(height: 8),
            Text(report.description),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('Spent: \$${report.amountSpent.toStringAsFixed(2)}', style: const TextStyle(fontWeight: FontWeight.w600)),
                Text(DateFormat.yMMMd().format(report.updatedAt), style: const TextStyle(color: Colors.black54, fontSize: 12)),
              ],
            ),
            const SizedBox(height: 8),
            LinearProgressIndicator(value: report.progress, minHeight: 8),
          ],
        ),
      ),
    );
  }
}

