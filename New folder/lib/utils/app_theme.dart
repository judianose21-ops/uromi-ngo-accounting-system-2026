import 'package:flutter/material.dart';

class AppTheme {
  static const Color primary = Color(0xFF1B5E20);
  static const Color accent = Color(0xFF81C784);

  static final ThemeData lightTheme = ThemeData(
    primaryColor: primary,
    colorScheme: ColorScheme.fromSwatch(primarySwatch: Colors.green).copyWith(secondary: accent),
    scaffoldBackgroundColor: Colors.grey.shade50,
    appBarTheme: const AppBarTheme(
      elevation: 0,
      backgroundColor: primary,
      foregroundColor: Colors.white,
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: primary,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    ),
    cardTheme: CardThemeData(
      elevation: 2,
      margin: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
    ),
  );
}
