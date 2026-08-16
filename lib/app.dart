import 'package:trademind_ai/core/theme/app_theme.dart';
import 'package:trademind_ai/features/auth/login_screen.dart';
import 'package:trademind_ai/features/home/trading_shell.dart';
import 'package:trademind_ai/providers/auth_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class TradeMindApp extends ConsumerWidget {
  const TradeMindApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authStateProvider);
    return MaterialApp(
      title: 'TradeMind AI',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme(),
      home: authState.maybeWhen(
        data: (session) => session == null ? const LoginScreen() : const TradingShell(),
        orElse: () => const Scaffold(
          body: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('TradeMind AI', style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold)),
                SizedBox(height: 8),
                Text('Preparing your session...'),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
