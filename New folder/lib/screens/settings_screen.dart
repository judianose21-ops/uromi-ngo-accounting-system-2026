import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../main.dart';
import '../utils/routes.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Account', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            Card(
              child: ListTile(
                leading: const CircleAvatar(child: Icon(Icons.person)),
                title: Text(state.user?.name ?? 'Unknown User'),
                subtitle: Text(state.user?.email ?? ''),
              ),
            ),
            const SizedBox(height: 24),
            Text('Actions', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            Card(
              child: ListTile(
                leading: const Icon(Icons.logout),
                title: const Text('Sign out'),
                onTap: () {
                  context.read<AppState>().signOut();
                  Navigator.pushNamedAndRemoveUntil(context, Routes.login, (_) => false);
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
