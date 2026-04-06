import 'dart:async';
import '../models/user_profile.dart';

class AuthService {
  static final List<UserProfile> _users = [
    UserProfile(id: 'user-1', name: 'Amina Patel', email: 'admin@ngo.org'),
    UserProfile(id: 'user-2', name: 'Samuel Okoro', email: 'finance@ngo.org'),
  ];

  static Future<UserProfile?> signIn(String email, String password) async {
    await Future.delayed(const Duration(milliseconds: 500));
    if (password != 'ngo1234') {
      return null;
    }
    return _users.firstWhere(
      (user) => user.email.toLowerCase() == email.toLowerCase(),
      orElse: () => _users.first,
    );
  }
}
