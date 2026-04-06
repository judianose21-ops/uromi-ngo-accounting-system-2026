import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../main.dart';
import '../utils/routes.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({Key? key}) : super(key: key);

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  String? _errorMessage;
  bool _isLoading = false;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    final success = await context.read<AppState>().signIn(
          _emailController.text.trim(),
          _passwordController.text.trim(),
        );

    setState(() {
      _isLoading = false;
    });

    if (success) {
      if (!mounted) return;
      Navigator.pushReplacementNamed(context, Routes.dashboard);
    } else {
      setState(() {
        _errorMessage = 'Invalid credentials. Use admin@ngo.org / ngo1234';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 24),
              const Text('NGO Accounting', style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              const Text('Log in to manage transactions, budgets, and reports.', style: TextStyle(fontSize: 16, color: Colors.black54)),
              const SizedBox(height: 32),
              Form(
                key: _formKey,
                child: Column(
                  children: [
                    TextFormField(
                      controller: _emailController,
                      decoration: const InputDecoration(labelText: 'Email', prefixIcon: Icon(Icons.email)),
                      keyboardType: TextInputType.emailAddress,
                      validator: (value) => value == null || value.isEmpty ? 'Enter your email' : null,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _passwordController,
                      decoration: const InputDecoration(labelText: 'Password', prefixIcon: Icon(Icons.lock)),
                      obscureText: true,
                      validator: (value) => value == null || value.isEmpty ? 'Enter your password' : null,
                    ),
                    const SizedBox(height: 16),
                    if (_errorMessage != null)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 16),
                        child: Text(_errorMessage!, style: const TextStyle(color: Colors.red)),
                      ),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: _isLoading ? null : _submit,
                        child: _isLoading
                            ? const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                            : const Text('Sign In'),
                      ),
                    ),
                  ],
                ),
              ),
              const Spacer(),
              const Text('Tip: Use admin@ngo.org and password ngo1234', style: TextStyle(color: Colors.black54)),
            ],
          ),
        ),
      ),
    );
  }
}
