import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:trademind_ai/core/config/app_config.dart';
import 'package:trademind_ai/features/admin/admin_dashboard_screen.dart';
import 'package:trademind_ai/features/education/admin_lesson_editor_screen.dart';
import 'package:trademind_ai/providers/app_providers.dart';
import 'package:trademind_ai/providers/auth_provider.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(authStateProvider).valueOrNull;
    final profileAsync = ref.watch(currentUserProfileProvider);
    final profile = profileAsync.valueOrNull;
    final role = profile?['role']?.toString() ?? 'user';
    final subscription = profile?['subscription']?.toString() ?? 'free';

    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('User: ${session?.user.email ?? 'Guest'}', style: const TextStyle(fontSize: 16)),
            const SizedBox(height: 8),
            Text('Role: ${role.toUpperCase()}'),
            const SizedBox(height: 8),
            Text('Plan: ${subscription.toUpperCase()}'),
            const SizedBox(height: 8),
            Text('Supabase configured: ${AppConfig.supabaseConfigured ? 'Yes' : 'No'}'),
            const SizedBox(height: 8),
            if (role == 'admin')
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Chip(label: Text('Admin access enabled')),
                  const SizedBox(height: 12),
                  FilledButton.tonal(
                    onPressed: () {
                      Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => const AdminLessonEditorScreen(),
                        ),
                      );
                    },
                    child: const Text('Create Lesson'),
                  ),
                  const SizedBox(height: 8),
                  FilledButton.tonal(
                    onPressed: () {
                      Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => const AdminDashboardScreen(),
                        ),
                      );
                    },
                    child: const Text('Open Admin Dashboard'),
                  ),
                ],
              ),
            const SizedBox(height: 20),
            FilledButton.tonal(
              onPressed: () async {
                final messenger = ScaffoldMessenger.of(context);
                try {
                  final pushService = ref.read(pushNotificationServiceProvider);
                  final initialized = await pushService.initialize();
                  if (!initialized) {
                    messenger.showSnackBar(
                      const SnackBar(content: Text('Firebase not available. Re-check firebase config.')),
                    );
                    return;
                  }
                  final token = await pushService.getToken();
                  if (token == null) {
                    messenger.showSnackBar(
                      const SnackBar(content: Text('Unable to retrieve FCM token')),
                    );
                    return;
                  }
                  await ref.read(deviceServiceProvider).registerFcmToken(
                        token: token,
                        platform: pushService.platformName(),
                      );
                  if (context.mounted) {
                    messenger.showSnackBar(const SnackBar(content: Text('Push notifications enabled')));
                  }
                } catch (e) {
                  if (context.mounted) {
                    messenger.showSnackBar(SnackBar(content: Text('Registration failed: $e')));
                  }
                }
              },
              child: const Text('Enable Push Notifications'),
            ),
            const SizedBox(height: 12),
            FilledButton.tonal(
              onPressed: () => ref.invalidate(currentUserProfileProvider),
              child: const Text('Refresh Profile'),
            ),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: () async => ref.read(authServiceProvider).signOut(),
              child: const Text('Logout'),
            ),
          ],
        ),
      ),
    );
  }
}
