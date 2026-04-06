import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/budget.dart';
import '../models/ngo_transaction.dart';
import '../models/project_report.dart';

class ApiService {
  static const String baseUrl = 'https://jsonplaceholder.typicode.com'; // Mock API

  static Future<List<NGOTransaction>> fetchTransactions() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/posts'));
      if (response.statusCode == 200) {
        final data = json.decode(response.body) as List;
        return data.take(3).map((item) => NGOTransaction(
          id: 'api-${item['id']}',
          description: item['title'],
          amount: 100.0 + (item['id'] as int) * 50.0,
          date: DateTime.now().subtract(Duration(days: item['id'] as int)),
          category: 'API',
          project: 'Synced Project',
        )).toList();
      }
    } catch (e) {
      print('API Error: $e');
    }
    return [];
  }

  static Future<void> syncTransaction(NGOTransaction transaction) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/posts'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'title': transaction.description,
          'body': 'Amount: ${transaction.amount}',
          'userId': 1,
        }),
      );
      if (response.statusCode == 201) {
        print('Transaction synced successfully');
      }
    } catch (e) {
      print('Sync Error: $e');
    }
  }

  static Future<List<Budget>> fetchBudgets() async {
    // Similar to transactions, but for budgets
    return [];
  }

  static Future<List<ProjectReport>> fetchReports() async {
    return [];
  }
}