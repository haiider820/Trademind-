import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:trademind_ai/services/trademind_api_service.dart';

class NotificationsScreen extends StatelessWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final service = TrademindApiService();
    return Scaffold(
      appBar: AppBar(title: const Text('Notifications')),
      body: FutureBuilder<List<dynamic>>(
        future: service.getNotifications(),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(child: Text('Failed to load notifications: ${snapshot.error}'));
          }
          final items = snapshot.data ?? const [];
          if (items.isEmpty) {
            return const Center(child: Text('No notifications yet.'));
          }
          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: items.length,
            separatorBuilder: (_, __) => const SizedBox(height: 12),
            itemBuilder: (context, index) {
              final item = Map<String, dynamic>.from(items[index] as Map);
              final read = item['is_read'] == true;
              final title = item['title']?.toString() ?? '';
              final body = item['body']?.toString() ?? '';
              final createdAt = DateTime.tryParse(item['created_at']?.toString() ?? '') ?? DateTime.now();
              return Card(
                child: ListTile(
                  leading: Icon(read ? Icons.notifications_none : Icons.notifications_active),
                  title: Text(title),
                  subtitle: Text('$body\n${DateFormat('yMMMd HH:mm').format(createdAt)}'),
                  isThreeLine: true,
                ),
              );
            },
          );
        },
      ),
    );
  }
}
