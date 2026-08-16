import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:trademind_ai/providers/app_providers.dart';

class NewsScreen extends ConsumerWidget {
  const NewsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final newsAsync = ref.watch(newsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Market News')),
      body: RefreshIndicator(
        onRefresh: () async => ref.refresh(newsProvider.future),
        child: ListView(
          padding: const EdgeInsets.all(12),
          children: [
            if (newsAsync.isLoading)
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('News is syncing in the background.'),
                ),
              )
            else if (newsAsync.hasError)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text('Failed to load news: ${newsAsync.error}'),
                ),
              )
            else if (newsAsync.valueOrNull == null || newsAsync.valueOrNull!.isEmpty)
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('No news available yet.'),
                ),
              )
            else
              ...newsAsync.valueOrNull!.map(
                (item) => Card(
                  margin: const EdgeInsets.symmetric(horizontal: 0, vertical: 6),
                  child: ListTile(
                    title: Text(item.title),
                    subtitle: Text(
                      '${item.category.toUpperCase()} • ${item.source}\n${DateFormat('yMMMd HH:mm').format(item.publishedAt)}',
                    ),
                    isThreeLine: true,
                    trailing: Text(item.sentiment.toUpperCase()),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
