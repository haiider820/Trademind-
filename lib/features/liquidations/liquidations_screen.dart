import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:trademind_ai/services/trademind_api_service.dart';

class LiquidationsScreen extends StatelessWidget {
  const LiquidationsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Liquidation Tracking')),
      body: FutureBuilder<List<dynamic>>(
        future: TrademindApiService().getLiquidations(),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(child: Text('Failed to load liquidations: ${snapshot.error}'));
          }
          final items = snapshot.data ?? const [];
          if (items.isEmpty) {
            return const Center(child: Text('No liquidation data available yet.'));
          }
          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: items.length,
            separatorBuilder: (_, __) => const SizedBox(height: 12),
            itemBuilder: (context, index) {
              final item = Map<String, dynamic>.from(items[index] as Map);
              final side = (item['side']?.toString() ?? '').toUpperCase();
              return Card(
                child: ListTile(
                  title: Text('${item['coin'] ?? ''} $side'),
                  subtitle: Text(
                    '${NumberFormat.compact().format((item['amount'] as num?)?.toDouble() ?? 0)} liquidated\n'
                    '${DateTime.tryParse(item['created_at']?.toString() ?? '') ?? DateTime.now()}',
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}
