class NGOTransaction {
  final String id;
  final String description;
  final double amount;
  final DateTime date;
  final String category;
  final String project;
  final String? imagePath;
  final String currency;

  NGOTransaction({
    required this.id,
    required this.description,
    required this.amount,
    required this.date,
    required this.category,
    required this.project,
    this.imagePath,
    this.currency = 'USD',
  });
}
