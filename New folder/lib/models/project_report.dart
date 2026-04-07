class ProjectReport {
  final String id;
  final String title;
  final String description;
  final double progress;
  final double amountSpent;
  final DateTime updatedAt;
  final String currency;

  ProjectReport({
    required this.id,
    required this.title,
    required this.description,
    required this.progress,
    required this.amountSpent,
    required this.updatedAt,
    this.currency = 'USD',
  });
}
