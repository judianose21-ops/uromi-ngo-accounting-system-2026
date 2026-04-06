class Budget {
  final String id;
  final String name;
  final double limit;
  final double spent;

  Budget({
    required this.id,
    required this.name,
    required this.limit,
    required this.spent,
  });

  Budget copyWith({String? id, String? name, double? limit, double? spent}) {
    return Budget(
      id: id ?? this.id,
      name: name ?? this.name,
      limit: limit ?? this.limit,
      spent: spent ?? this.spent,
    );
  }
}
