import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../main.dart';
import '../widgets/report_tile.dart';

class ReportsScreen extends StatelessWidget {
  const ReportsScreen({Key? key}) : super(key: key);

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
    );
  }
}

