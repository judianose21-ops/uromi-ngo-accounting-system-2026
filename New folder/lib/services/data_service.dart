import 'dart:async';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';
import '../models/budget.dart';
import '../models/ngo_transaction.dart';
import '../models/project_report.dart';

class DataService {
  static Database? _database;
  static List<NGOTransaction> _memoryTransactions = [];
  static List<Budget> _memoryBudgets = [];
  static List<ProjectReport> _memoryReports = [];

  static Future<Database> get database async {
    if (!kIsWeb && (Platform.isAndroid || Platform.isIOS)) {
      if (_database != null) return _database!;
      _database = await _initDatabase();
      return _database!;
    }
    throw UnsupportedError('Database not supported on this platform');
  }

  static Future<Database> _initDatabase() async {
    final path = join(await getDatabasesPath(), 'ngo_accounting.db');
    return await openDatabase(
      path,
      version: 2,
      onCreate: _onCreate,
      onUpgrade: _onUpgrade,
    );
  }

  static Future<void> _onUpgrade(Database db, int oldVersion, int newVersion) async {
    if (oldVersion < 2) {
      // Add currency column to existing tables
      await db.execute('ALTER TABLE transactions ADD COLUMN currency TEXT DEFAULT "USD"');
      await db.execute('ALTER TABLE budgets ADD COLUMN currency TEXT DEFAULT "USD"');
      await db.execute('ALTER TABLE reports ADD COLUMN currency TEXT DEFAULT "USD"');
    }
  }

  static Future<void> _onCreate(Database db, int version) async {
    await db.execute('''
      CREATE TABLE transactions(
        id TEXT PRIMARY KEY,
        description TEXT,
        amount REAL,
        date TEXT,
        category TEXT,
        project TEXT,
        imagePath TEXT,
        currency TEXT DEFAULT 'USD'
      )
    ''');
    await db.execute('''
      CREATE TABLE budgets(
        id TEXT PRIMARY KEY,
        name TEXT,
        limit REAL,
        spent REAL,
        currency TEXT DEFAULT 'USD'
      )
    ''');
    await db.execute('''
      CREATE TABLE reports(
        id TEXT PRIMARY KEY,
        title TEXT,
        description TEXT,
        progress REAL,
        amountSpent REAL,
        updatedAt TEXT,
        currency TEXT DEFAULT 'USD'
      )
    ''');
    // Seed initial data
    await _seedData(db);
  }

  static Future<void> _seedData(Database db) async {
    final transactions = [
      {
        'id': 'txn-1',
        'description': 'Water well repair',
        'amount': 850.0,
        'date': DateTime.now().subtract(const Duration(days: 2)).toIso8601String(),
        'category': 'Infrastructure',
        'project': 'Clean Water Initiative',
        'imagePath': null,
        'currency': 'USD',
      },
      {
        'id': 'txn-2',
        'description': 'School supplies purchase',
        'amount': 420.5,
        'date': DateTime.now().subtract(const Duration(days: 4)).toIso8601String(),
        'category': 'Education',
        'project': 'Child Education Program',
        'imagePath': null,
        'currency': 'USD',
      },
      {
        'id': 'txn-3',
        'description': 'Community health outreach',
        'amount': 1200.0,
        'date': DateTime.now().subtract(const Duration(days: 7)).toIso8601String(),
        'category': 'Health',
        'project': 'Health Awareness Week',
        'imagePath': null,
        'currency': 'USD',
      },
    ];
    for (var txn in transactions) {
      await db.insert('transactions', txn);
    }

    final budgets = [
      {'id': 'budget-1', 'name': 'Education Fund', 'limit': 5000.0, 'spent': 2120.0, 'currency': 'USD'},
      {'id': 'budget-2', 'name': 'Water Projects', 'limit': 7500.0, 'spent': 4300.0, 'currency': 'USD'},
      {'id': 'budget-3', 'name': 'Medical Supplies', 'limit': 3600.0, 'spent': 1785.0, 'currency': 'USD'},
    ];
    for (var budget in budgets) {
      await db.insert('budgets', budget);
    }

    final reports = [
      {
        'id': 'report-1',
        'title': 'Clean Water Initiative',
        'description': 'Completed phase 1 drilling and community training.',
        'progress': 0.72,
        'amountSpent': 4300.0,
        'updatedAt': DateTime.now().subtract(const Duration(days: 1)).toIso8601String(),
        'currency': 'USD',
      },
      {
        'id': 'report-2',
        'title': 'Child Education Program',
        'description': 'Distributed materials to 120 students and started mentorship.',
        'progress': 0.55,
        'amountSpent': 2800.0,
        'updatedAt': DateTime.now().subtract(const Duration(days: 3)).toIso8601String(),
        'currency': 'USD',
      },
      {
        'id': 'report-3',
        'title': 'Health Awareness Week',
        'description': 'Reached six communities with preventive care campaigns.',
        'progress': 0.80,
        'amountSpent': 5000.0,
        'updatedAt': DateTime.now().subtract(const Duration(days: 2)).toIso8601String(),
        'currency': 'USD',
      },
    ];
    for (var report in reports) {
      await db.insert('reports', report);
    }
  }

  static Future<List<NGOTransaction>> getTransactions() async {
    if (kIsWeb) {
      if (_memoryTransactions.isEmpty) {
        _memoryTransactions = [
          NGOTransaction(
            id: 'txn-1',
            description: 'Water well repair',
            amount: 850.0,
            date: DateTime.now().subtract(const Duration(days: 2)),
            category: 'Infrastructure',
            project: 'Clean Water Initiative',
            currency: 'USD',
          ),
          NGOTransaction(
            id: 'txn-2',
            description: 'School supplies purchase',
            amount: 420.5,
            date: DateTime.now().subtract(const Duration(days: 4)),
            category: 'Education',
            project: 'Child Education Program',
            currency: 'USD',
          ),
          NGOTransaction(
            id: 'txn-3',
            description: 'Community health outreach',
            amount: 1200.0,
            date: DateTime.now().subtract(const Duration(days: 7)),
            category: 'Health',
            project: 'Health Awareness Week',
            currency: 'USD',
          ),
        ];
      }
      return _memoryTransactions;
    }
    final db = await database;
    final maps = await db.query('transactions');
    return maps.map((map) => NGOTransaction(
      id: map['id'] as String,
      description: map['description'] as String,
      amount: map['amount'] as double,
      date: DateTime.parse(map['date'] as String),
      category: map['category'] as String,
      project: map['project'] as String,
      imagePath: map['imagePath'] as String?,
      currency: map['currency'] as String? ?? 'USD',
    )).toList();
  }

  static Future<void> addTransaction(NGOTransaction transaction) async {
    if (kIsWeb) {
      _memoryTransactions.insert(0, transaction);
      return;
    }
    final db = await database;
    await db.insert('transactions', {
      'id': transaction.id,
      'description': transaction.description,
      'amount': transaction.amount,
      'date': transaction.date.toIso8601String(),
      'category': transaction.category,
      'project': transaction.project,
      'imagePath': transaction.imagePath,
      'currency': transaction.currency,
    });
  }

  static Future<List<Budget>> getBudgets() async {
    if (kIsWeb) {
      if (_memoryBudgets.isEmpty) {
        _memoryBudgets = [
          Budget(id: 'budget-1', name: 'Education Fund', limit: 5000, spent: 2120, currency: 'USD'),
          Budget(id: 'budget-2', name: 'Water Projects', limit: 7500, spent: 4300, currency: 'USD'),
          Budget(id: 'budget-3', name: 'Medical Supplies', limit: 3600, spent: 1785, currency: 'USD'),
        ];
      }
      return _memoryBudgets;
    }
    final db = await database;
    final maps = await db.query('budgets');
    return maps.map((map) => Budget(
      id: map['id'] as String,
      name: map['name'] as String,
      limit: map['limit'] as double,
      spent: map['spent'] as double,
      currency: map['currency'] as String? ?? 'USD',
    )).toList();
  }

  static Future<void> addBudget(Budget budget) async {
    if (kIsWeb) {
      _memoryBudgets.insert(0, budget);
      return;
    }
    final db = await database;
    await db.insert('budgets', {
      'id': budget.id,
      'name': budget.name,
      'limit': budget.limit,
      'spent': budget.spent,
      'currency': budget.currency,
    });
  }

  static Future<void> updateBudgetSpent(String id, double spent) async {
    if (kIsWeb) {
      final index = _memoryBudgets.indexWhere((b) => b.id == id);
      if (index >= 0) {
        _memoryBudgets[index] = _memoryBudgets[index].copyWith(spent: spent);
      }
      return;
    }
    final db = await database;
    await db.update('budgets', {'spent': spent}, where: 'id = ?', whereArgs: [id]);
  }

  static Future<List<ProjectReport>> getReports() async {
    if (kIsWeb) {
      if (_memoryReports.isEmpty) {
        _memoryReports = [
          ProjectReport(
            id: 'report-1',
            title: 'Clean Water Initiative',
            description: 'Completed phase 1 drilling and community training.',
            progress: 0.72,
            amountSpent: 4300,
            updatedAt: DateTime.now().subtract(const Duration(days: 1)),
            currency: 'USD',
          ),
          ProjectReport(
            id: 'report-2',
            title: 'Child Education Program',
            description: 'Distributed materials to 120 students and started mentorship.',
            progress: 0.55,
            amountSpent: 2800,
            updatedAt: DateTime.now().subtract(const Duration(days: 3)),
            currency: 'USD',
          ),
          ProjectReport(
            id: 'report-3',
            title: 'Health Awareness Week',
            description: 'Reached six communities with preventive care campaigns.',
            progress: 0.80,
            amountSpent: 5000,
            updatedAt: DateTime.now().subtract(const Duration(days: 2)),
            currency: 'USD',
          ),
        ];
      }
      return _memoryReports;
    }
    final db = await database;
    final maps = await db.query('reports');
    return maps.map((map) => ProjectReport(
      id: map['id'] as String,
      title: map['title'] as String,
      description: map['description'] as String,
      progress: map['progress'] as double,
      amountSpent: map['amountSpent'] as double,
      updatedAt: DateTime.parse(map['updatedAt'] as String),
      currency: map['currency'] as String? ?? 'USD',
    )).toList();
  }

  static Future<void> addReport(ProjectReport report) async {
    if (kIsWeb) {
      _memoryReports.insert(0, report);
      return;
    }
    final db = await database;
    await db.insert('reports', {
      'id': report.id,
      'title': report.title,
      'description': report.description,
      'progress': report.progress,
      'amountSpent': report.amountSpent,
      'updatedAt': report.updatedAt.toIso8601String(),
      'currency': report.currency,
    });
  }
}