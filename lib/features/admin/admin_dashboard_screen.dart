import 'package:flutter/material.dart';
import 'package:trademind_ai/features/education/admin_lesson_editor_screen.dart';
import 'package:trademind_ai/features/liquidations/liquidations_screen.dart';
import 'package:trademind_ai/features/signals/signals_screen.dart';
import 'package:trademind_ai/features/whales/whale_tracking_screen.dart';

class AdminDashboardScreen extends StatelessWidget {
  const AdminDashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Admin Dashboard')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _AdminCard(
            title: 'Signals',
            subtitle: 'Create and manage live signals',
            icon: Icons.candlestick_chart,
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const SignalsScreen()),
            ),
          ),
          const SizedBox(height: 12),
          _AdminCard(
            title: 'Lessons',
            subtitle: 'Publish learn trading content',
            icon: Icons.school_outlined,
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const AdminLessonEditorScreen()),
            ),
          ),
          const SizedBox(height: 12),
          _AdminCard(
            title: 'Whale Alerts',
            subtitle: 'Review whale tracking feed',
            icon: Icons.water_outlined,
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const WhaleTrackingScreen()),
            ),
          ),
          const SizedBox(height: 12),
          _AdminCard(
            title: 'Liquidations',
            subtitle: 'Monitor liquidation flow',
            icon: Icons.warning_amber_outlined,
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const LiquidationsScreen()),
            ),
          ),
        ],
      ),
    );
  }
}

class _AdminCard extends StatelessWidget {
  const _AdminCard({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        onTap: onTap,
        leading: Icon(icon),
        title: Text(title),
        subtitle: Text(subtitle),
        trailing: const Icon(Icons.chevron_right),
      ),
    );
  }
}
